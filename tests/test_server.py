import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location('sprout_server', Path(__file__).resolve().parents[1] / 'server.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class PersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.db = str(Path(cls.temp.name) / 'test.sqlite3')
        app.initialize(cls.db)
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.server.db = cls.db
        cls.server.token = 'test-session-token'
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def call(self, path='/api/state', body=None, token=True, origin=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Sprout-Token'] = self.server.token
        if origin:
            headers['Origin'] = origin
        req = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method='PUT' if body is not None else 'GET')
        try:
            with urlopen(req) as result:
                return result.status, json.load(result)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_atomic_save_reopen_conflict_and_restore(self):
        _, initial = self.call()
        state = copy.deepcopy(initial['state'])
        state['child'] = {'name': '测试', 'months': 50, 'avatar': 'bear', 'interests': ['动物']}
        code, result = self.call(body={'revision': initial['revision'], 'state': state})
        self.assertEqual(code, 200)
        app.initialize(self.db)  # App restart opens the existing state rather than reseeding.
        _, after = self.call()
        self.assertEqual(after['state']['child']['name'], '测试')
        self.assertEqual(after['revision'], result['revision'])
        code, _ = self.call(body={'revision': initial['revision'], 'state': state})
        self.assertEqual(code, 409)
        state['child']['name'] = '修改'
        code, changed = self.call(body={'revision': after['revision'], 'state': state})
        self.assertEqual(code, 200)
        code, _ = self.call(body={'revision': changed['revision'], 'state': after['state']})
        self.assertEqual(code, 200)
        self.assertEqual(self.call()[1]['state']['child']['name'], '测试')
        with sqlite3.connect(self.db) as connection:
            self.assertGreaterEqual(connection.execute('SELECT COUNT(*) FROM revisions').fetchone()[0], 3)

    def test_invalid_restore_does_not_overwrite_saved_data(self):
        _, before = self.call()
        invalid = copy.deepcopy(before['state'])
        invalid['child'] = {'name': '坏数据', 'months': 2, 'avatar': 'bear', 'interests': []}
        self.assertEqual(self.call(body={'revision': before['revision'], 'state': invalid})[0], 400)
        self.assertEqual(self.call()[1]['revision'], before['revision'])

    def test_csrf_and_private_database_protection(self):
        _, before = self.call()
        body = {'revision': before['revision'], 'state': before['state']}
        self.assertEqual(self.call(body=body, token=False)[0], 403)
        self.assertEqual(self.call(body=body, origin='https://unrelated.example')[0], 403)
        self.assertEqual(self.call('/data/sprout.sqlite3')[0], 404)
        self.assertEqual(self.call('/server.py')[0], 404)

if __name__ == '__main__':
    unittest.main()
