import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import cloudbase_http as bridge
from cloud_server import CloudHandler, ThreadingHTTPServer, configure
from storage import connect
import test_postgres as pg


@unittest.skipUnless(pg.pgserver and pg.psycopg, 'Requires local PostgreSQL test dependencies')
class HttpBridgeTests(unittest.TestCase):
    setUpClass = classmethod(pg.PostgresCloudTests.setUpClass.__func__)
    tearDownClass = classmethod(pg.PostgresCloudTests.tearDownClass.__func__)
    tearDown = pg.PostgresCloudTests.tearDown
    call = pg.PostgresCloudTests.call
    login = pg.PostgresCloudTests.login
    seed = pg.PostgresCloudTests.seed
    test_practice_sync = pg.PostgresCloudTests.test_replay_retries_restart_conflicts_and_restore_across_devices
    test_concurrent_devices = pg.PostgresCloudTests.test_simultaneous_formal_writes_have_one_winner_and_retry_is_idempotent
    test_delta_retry = pg.PostgresCloudTests.test_day_patch_and_unchanged_probe_avoid_full_history_but_retries_reconcile_all
    test_auto_check = pg.PostgresCloudTests.test_formal_math_completes_and_auto_checks_once_visible_on_other_device
    test_private_data = pg.PostgresCloudTests.test_private_state_and_files_require_login_or_remain_blocked
    test_csrf = pg.PostgresCloudTests.test_csrf_and_session_tokens_are_bound_to_each_device
    test_outage = pg.PostgresCloudTests.test_database_outage_is_retryable_without_expiring_the_device_session

    def setUp(self):
        with connect(self.database) as c:
            c.execute('TRUNCATE state, revisions, learning_events, sessions, login_limit, auth_config')
        pg.initialize_cloud(self.database)
        with pg.psycopg.connect(self.database, autocommit=True) as c:
            c.execute((Path(__file__).resolve().parents[1]/'sql/cloudbase_http_bridge.sql').read_text(), prepare=False)
            c.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role NOLOGIN BYPASSRLS; CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; END IF; END $$")
            c.execute((Path(__file__).resolve().parents[1]/'sql/cloudbase_rpc_bridge.sql').read_text(), prepare=False)
        def local_gateway(body):
            # Simulates an independent gateway transaction for EVERY request.
            with pg.psycopg.connect(self.database) as c:
                c.execute("SET LOCAL ROLE service_role")
                c.execute("SELECT set_config('request.jwt.claims', %s, true)", (json.dumps({'role': 'service_role'}),))
                return c.execute('SELECT public.sprout_server_bridge(%s::jsonb)', (json.dumps(body),)).fetchone()[0]
        mock = patch.object(bridge, 'request_bridge', side_effect=local_gateway)
        mock.start()
        self.addCleanup(mock.stop)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), CloudHandler)
        self.server.db = 'cloudbase+https'
        self.origin = 'https://family.example'
        configure(self.server, self.origin, 'family', 'test-only-password-123', initialize_auth=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def test_sql_binding_preserves_question_marks_quotes_and_backslashes(self):
        text = "孩子? ' ; DROP TABLE sprout.state; -- \\ 中文"
        with bridge.HttpConnection() as c:
            c.execute('INSERT INTO learning_events VALUES (?,?,?)', ('id?', text, '{}'))
        with bridge.HttpConnection() as c:
            self.assertEqual(c.execute('SELECT request,result FROM learning_events WHERE id=?', ('id?',)).fetchone(), (text, '{}'))

    def test_write_failure_is_atomic_and_functions_are_not_public(self):
        with self.assertRaises(pg.psycopg.Error):
            with bridge.HttpConnection() as c:
                c.execute('UPDATE state SET revision=? WHERE id=1', (15,))
                c.execute('INSERT INTO state VALUES (1,0,?,?)', ('{}', 'now'))
        with connect(self.database) as c:
            self.assertEqual(c.execute('SELECT revision FROM state WHERE id=1').fetchone()[0], 0)
            public = c.execute("SELECT count(*) FROM pg_proc p, LATERAL aclexplode(p.proacl) a WHERE p.pronamespace='sprout'::regnamespace AND a.grantee=0").fetchone()[0]
            self.assertEqual(public, 0)

    def test_rollback_discards_all_buffered_writes(self):
        with bridge.HttpConnection() as c:
            c.execute('UPDATE state SET revision=100 WHERE id=1')
            c.rollback()
        with connect(self.database) as c:
            self.assertEqual(c.execute('SELECT revision FROM state WHERE id=1').fetchone()[0], 0)

    def test_rpc_rejects_missing_anonymous_and_user_claims_even_if_execution_is_allowed(self):
        for claims in ('', '{}', '{"role":"anon"}', '{"role":"authenticated"}'):
            with self.subTest(claims=claims), self.assertRaises(pg.psycopg.errors.InsufficientPrivilege):
                with pg.psycopg.connect(self.database) as c:
                    c.execute("SELECT set_config('request.jwt.claims', %s, true)", (claims,))
                    c.execute('SELECT public.sprout_server_bridge(%s::jsonb)',
                              (json.dumps({'action': 'read', 'sql': 'SELECT salt FROM auth_config WHERE id=1', 'params': []}),))

    def test_anonymous_and_authenticated_roles_cannot_read_private_records(self):
        for role in ('anon', 'authenticated'):
            with self.subTest(role=role), self.assertRaises(pg.psycopg.errors.InsufficientPrivilege):
                with pg.psycopg.connect(self.database) as c:
                    c.execute(f'SET LOCAL ROLE {role}')
                    c.execute('SELECT payload FROM sprout.state')

    def test_manual_repeat_persists_across_devices_and_retry_is_idempotent(self):
        self.seed(completed=False)
        a,b=self.login(),self.login()
        def send(body):
            state=self.call(cookie=a)[1]
            return self.call('/api/study-event','POST',dict(body,revision=state['revision']),cookie=a,csrf=state['token'])
        base=dict(planId='p1',day=1,subject='english')
        self.assertEqual(send(dict(base,action='open',eventId='manual-open'))[0],200)
        q=pg.questions(pg.LESSONS['english-1'])[0]
        self.assertEqual(send(dict(base,action='answer',questionId=q['id'],answer=q['answer'],eventId='manual-answer'))[0],200)
        body=dict(base,action='repeat',questionId=q['id'],method='parent-score-v1',score=65,eventId='manual-score')
        first=send(body)
        self.assertEqual(first[0],200)
        self.assertEqual(send(body)[1]['revision'],first[1]['revision'])
        step=self.call(cookie=b)[1]['state']['plans'][0]['records']['1']['study']['english']['steps'][q['id']]
        self.assertTrue(step['correct'])
        self.assertEqual(step['repeat']['score'],65)
        self.assertEqual(step['repeat']['method'],'parent-score-v1')
        self.assertEqual(step['repeat']['attempts'],1)


class TransportTests(unittest.TestCase):
    def test_secret_is_only_sent_to_fixed_https_gateway_and_not_in_payload(self):
        import io
        class Opener:
            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return io.BytesIO(b'{"rows":[]}')
        opener = Opener()
        with patch.dict(os.environ, {'CLOUDBASE_ENV_ID': 'test-env', 'CLOUDBASE_API_KEY': 'test-server-secret'}), patch('urllib.request.build_opener', return_value=opener):
            self.assertEqual(bridge.request_bridge({'action': 'read'}), {'rows': []})
        self.assertEqual(opener.request.full_url, 'https://test-env.api.tcloudbasegateway.com/v1/rdb/rest/rpc/sprout_server_bridge')
        self.assertEqual(opener.request.get_header('Authorization'), 'Bearer test-server-secret')
        self.assertNotIn(b'test-server-secret', opener.request.data)
        self.assertEqual(json.loads(opener.request.data), {'request': {'action': 'read'}})

    def test_network_errors_do_not_expose_key_or_provider_response(self):
        from urllib.error import URLError
        with patch.dict(os.environ, {'CLOUDBASE_ENV_ID': 'test-env', 'CLOUDBASE_API_KEY': 'secret'}), patch('urllib.request.build_opener', side_effect=URLError('secret SQL child data')):
            with self.assertRaises(bridge.CloudBaseError) as error:
                bridge.request_bridge({})
        self.assertNotIn('secret', str(error.exception))
