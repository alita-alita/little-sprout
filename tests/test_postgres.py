"""Real PostgreSQL tests, entirely local. Optional test-only pgserver wheels."""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

import test_cloud as base
from test_learning import fixture, finish, event
from server import initialize, connect
from cloud_server import CloudHandler, ThreadingHTTPServer, configure
from migrate_cloudbase import initialize_cloud, import_backup
from learning import LESSONS, questions

try:
    import pgserver
    import psycopg
except ImportError:
    pgserver = psycopg = None


@unittest.skipUnless(pgserver and psycopg, 'Install requirements-test-postgres.txt for real PostgreSQL tests')
class PostgresCloudTests(base.CloudTests):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix='sprout-pg-')
        cls.pg = pgserver.get_server(Path(cls.folder.name)/'db', cleanup_mode='stop')
        cls.database = cls.pg.get_uri()
        cls.database += ('&' if '?' in cls.database else '?') + 'sslmode=disable'
        cls.old_test_mode = os.environ.get('SPROUT_TEST_DATABASE')
        os.environ['SPROUT_TEST_DATABASE'] = '1'
        initialize_cloud(cls.database)

    @classmethod
    def tearDownClass(cls):
        cls.pg.cleanup()
        cls.folder.cleanup()
        if cls.old_test_mode is None:
            os.environ.pop('SPROUT_TEST_DATABASE', None)
        else:
            os.environ['SPROUT_TEST_DATABASE'] = cls.old_test_mode

    def setUp(self):
        with connect(self.database) as c:
            c.execute('TRUNCATE state, revisions, learning_events, sessions, login_limit, auth_config')
        initialize_cloud(self.database)
        self.server = ThreadingHTTPServer(('127.0.0.1',0), CloudHandler)
        self.server.db = self.database
        self.origin = 'https://family.example'
        configure(self.server, self.origin, 'family','test-only-password-123', initialize_auth=False)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def seed(self, completed=True):
        now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
        state=fixture(start=now.date().isoformat())
        if completed:
            for subject in ('english','chinese','math'):
                finish(state,subject,now)
        import_backup(self.database,{'app':'little-sprout','version':1,'state':state})
        return state

    def test_replay_retries_restart_conflicts_and_restore_across_devices(self):
        original=self.seed()
        a,b=self.login(),self.login()
        def send(body,cookie=a):
            data=self.call(cookie=cookie)[1]
            return self.call('/api/practice-event','POST',dict(body,revision=data['revision']),cookie=cookie,csrf=data['token'])
        start={'planId':'p1','day':1,'subject':'english','action':'start','eventId':secrets.token_hex(16)}
        self.assertEqual(send(start)[0],200)
        data=self.call(cookie=b)[1]
        entry=data['state']['plans'][0]['records']['1']['practice']['english']
        q=questions(LESSONS['english-1'])[0]
        answer=dict(start,action='answer',questionId=q['id'],answer=q['answer'],roundId=entry['roundId'],eventId=secrets.token_hex(16))
        code,result,_=send(answer,b)
        self.assertEqual(code,200)
        revision=result['revision']
        self.assertEqual(send(answer)[1]['revision'],revision)
        repeated=dict(answer,action='repeat',transcript=q['speech'],eventId=secrets.token_hex(16))
        repeated.pop('answer')
        self.assertEqual(send(repeated)[0],200)
        # A fresh process configuration sees the same sessions and replay steps.
        configure(self.server,self.origin,'family','test-only-password-123',initialize_auth=False)
        data=self.call(cookie=b)[1]
        record=data['state']['plans'][0]['records']['1']
        self.assertTrue(record['practice']['english']['steps']['w0']['correct'])
        self.assertEqual(record['study'],original['plans'][0]['records']['1']['study'])
        self.assertFalse(result['result']['autoChecked'])
        forged=copy.deepcopy(data['state'])
        forged['plans'][0]['records']['1']['practice']['english']['steps']['w0']['attempts']+=1
        self.assertEqual(self.call(method='PUT',body={'revision':data['revision'],'state':forged},cookie=b,csrf=data['token'])[0],400)
        backup={'revision':data['revision'],'state':data['state'],'restore':True}
        self.assertEqual(self.call(method='PUT',body=backup,cookie=b,csrf=data['token'])[0],200)
        self.assertTrue(self.call(cookie=a)[1]['state']['plans'][0]['records']['1']['practice']['english']['steps']['w0']['correct'])

    def test_simultaneous_formal_writes_have_one_winner_and_retry_is_idempotent(self):
        self.seed(completed=False)
        a,b=self.login(),self.login()
        data_a,data_b=self.call(cookie=a)[1],self.call(cookie=b)[1]
        body_a=dict(event('math'),revision=data_a['revision'],eventId=secrets.token_hex(16))
        body_b=dict(event('english'),revision=data_b['revision'],eventId=secrets.token_hex(16))
        def send(cookie,body,token):
            return self.call('/api/study-event','POST',body,cookie=cookie,csrf=token)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(send,a,body_a,data_a['token'])
            second=pool.submit(send,b,body_b,data_b['token'])
            results=[first.result(),second.result()]
        self.assertEqual(sorted(r[0] for r in results),[200,409])
        i=next(i for i,r in enumerate(results) if r[0]==200)
        self.assertEqual(send([a,b][i],[body_a,body_b][i],[data_a,data_b][i]['token'])[1]['revision'],results[i][1]['revision'])
        i=1-i
        fresh=self.call(cookie=[a,b][i])[1]
        self.assertEqual(send([a,b][i],dict([body_a,body_b][i],revision=fresh['revision']),fresh['token'])[0],200)

    def test_schema_is_private_and_failed_import_rolls_back(self):
        with connect(self.database) as c:
            tables=c.execute("SELECT tablename,rowsecurity FROM pg_tables WHERE schemaname='sprout'").fetchall()
            self.assertEqual(len(tables),6)
            self.assertTrue(all(row[1] for row in tables))
            self.assertEqual(c.execute("SELECT count(*) FROM pg_namespace n, LATERAL aclexplode(n.nspacl) a WHERE n.nspname='sprout' AND a.grantee=0").fetchone()[0],0)
        self.seed()
        before=self.call(cookie=self.login())[1]
        with self.assertRaises(ValueError):
            self.seed()
        self.assertEqual(self.call(cookie=self.login())[1]['revision'],before['revision'])

    def test_day_patch_and_unchanged_probe_avoid_full_history_but_retries_reconcile_all(self):
        self.seed()
        cookie=self.login()
        data=self.call(cookie=cookie)[1]
        same=self.call(cookie=cookie,extra_headers={'X-Sprout-Revision':str(data['revision'])})
        self.assertEqual(same[1],{'revision':data['revision'],'unchanged':True})
        self.assertEqual(self.call(extra_headers={'X-Sprout-Revision':str(data['revision'])})[0],401)
        body={'planId':'p1','day':1,'subject':'math','action':'start','eventId':secrets.token_hex(16),'revision':data['revision']}
        code,result,_=self.call('/api/practice-event','POST',body,cookie=cookie,csrf=data['token'],extra_headers={'X-Sprout-Delta':'1'})
        self.assertEqual(code,200)
        self.assertNotIn('state',result)
        self.assertEqual(result['patch']['planId'],'p1')
        self.assertIn('practice',result['patch']['record'])
        retry=self.call('/api/practice-event','POST',body,cookie=cookie,csrf=data['token'],extra_headers={'X-Sprout-Delta':'1'})
        self.assertIn('state',retry[1])
        self.assertEqual(retry[1]['revision'],result['revision'])

    def test_formal_math_completes_and_auto_checks_once_visible_on_other_device(self):
        now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
        state=fixture(start=now.date().isoformat(),subjects=['math'])
        import_backup(self.database,{'app':'little-sprout','version':1,'state':state})
        a,b=self.login(),self.login()
        def send(payload):
            data=self.call(cookie=a)[1]
            return self.call('/api/study-event','POST',dict(payload,revision=data['revision'],eventId=secrets.token_hex(16)),cookie=a,csrf=data['token'])
        self.assertEqual(send(event('math'))[0],200)
        for q in questions(LESSONS['math-1']):
            result=send(event('math','answer',q['id'],q['answer']))
            self.assertEqual(result[0],200)
        self.assertTrue(result[1]['result']['autoChecked'])
        other=self.call(cookie=b)[1]
        self.assertTrue(all(s['correct'] for s in other['state']['plans'][0]['records']['1']['study']['math']['steps'].values()))
        self.assertEqual(other['revision'],result[1]['revision'])

    def test_console_sql_initialization_is_repeatable_and_matches_application_schema(self):
        sql=(Path(__file__).resolve().parents[1]/'sql'/'init_cloudbase.sql').read_text(encoding='utf-8')
        with psycopg.connect(self.database,autocommit=True) as c:
            c.execute('DROP SCHEMA sprout CASCADE')  # isolated local test database only
            c.execute(sql,prepare=False)
            salt=c.execute('SELECT salt FROM sprout.auth_config WHERE id=1').fetchone()[0]
            self.assertEqual(len(salt),32)
            c.execute("UPDATE sprout.state SET revision=9,payload='{}' WHERE id=1")
            c.execute(sql,prepare=False)
            self.assertEqual(c.execute('SELECT revision,payload FROM sprout.state').fetchone(),(9,'{}'))
            self.assertEqual(c.execute('SELECT salt FROM sprout.auth_config WHERE id=1').fetchone()[0],salt)
            tables=c.execute("SELECT tablename,rowsecurity FROM pg_tables WHERE schemaname='sprout'").fetchall()
            self.assertEqual(len(tables),6)
            self.assertTrue(all(row[1] for row in tables))


if __name__ == '__main__':
    unittest.main()
