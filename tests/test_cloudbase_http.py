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
        def local_gateway(body):
            # Simulates an independent gateway transaction for EVERY request.
            with pg.psycopg.connect(self.database) as c:
                return c.execute('SELECT sprout.http_bridge(%s::jsonb)', (json.dumps(body),)).fetchone()[0]
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


class TransportTests(unittest.TestCase):
    def test_secret_is_only_sent_to_fixed_https_gateway_and_not_in_payload(self):
        import io
        class Opener:
            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return io.BytesIO(b'[{"result":{"rows":[]}}]')
        opener = Opener()
        with patch.dict(os.environ, {'CLOUDBASE_ENV_ID': 'test-env', 'CLOUDBASE_API_KEY': 'test-server-secret'}), patch('urllib.request.build_opener', return_value=opener):
            self.assertEqual(bridge.request_bridge({'action': 'read'}), {'rows': []})
        self.assertEqual(opener.request.full_url, 'https://test-env.api.tcloudbasegateway.com/v1/rdb/exec-pgsql')
        self.assertEqual(opener.request.get_header('Authorization'), 'Bearer test-server-secret')
        self.assertNotIn(b'test-server-secret', opener.request.data)
        self.assertIn('parameters', json.loads(opener.request.data))

    def test_network_errors_do_not_expose_key_or_provider_response(self):
        from urllib.error import URLError
        with patch.dict(os.environ, {'CLOUDBASE_ENV_ID': 'test-env', 'CLOUDBASE_API_KEY': 'secret'}), patch('urllib.request.build_opener', side_effect=URLError('secret SQL child data')):
            with self.assertRaises(bridge.CloudBaseError) as error:
                bridge.request_bridge({})
        self.assertNotIn('secret', str(error.exception))
