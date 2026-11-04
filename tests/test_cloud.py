import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

import cloud_server as cloud
from server import initialize, connect


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = cloud.ThreadingHTTPServer(('127.0.0.1', 0), cloud.CloudHandler)
        self.server.db = str(Path(self.temp.name) / 'test.sqlite3')
        initialize(self.server.db)
        self.origin = 'https://family.example'
        cloud.configure(self.server, self.origin, 'family', 'test-only-password-123')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path='/api/state', method='GET', body=None, cookie='', csrf='', origin=True, host='family.example'):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {'Host': host, 'Content-Type': 'application/json', 'Cookie': cookie, 'X-Sprout-Token': csrf}
        if origin:
            headers['Origin'] = self.origin if origin is True else origin
        c.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = c.getresponse()
        raw, code, cookie_header = response.read(), response.status, response.getheader('Set-Cookie', '')
        c.close()
        try:
            data = json.loads(raw)
        except ValueError:
            data = raw
        return code, data, cookie_header

    def login(self):
        code, _, cookie = self.call('/api/login', 'POST', {'username': 'family', 'password': 'test-only-password-123'})
        self.assertEqual(code, 200)
        self.assertIn('Secure; HttpOnly; SameSite=Lax', cookie)
        return cookie.split(';')[0]

    def test_private_state_and_files_require_login_or_remain_blocked(self):
        self.assertEqual(self.call()[0], 401)
        for path in ['/data/sprout.sqlite3', '/cloud_server.py', '/.env', '/render.yaml']:
            self.assertEqual(self.call(path)[0], 404)
        self.assertEqual(self.call('/healthz', host='internal.health')[0], 200)
        self.assertEqual(self.call(host='evil.example')[0], 403)

    def test_two_devices_share_persisted_state_and_conflicts_are_detected(self):
        first, second = self.login(), self.login()
        _, a, _ = self.call(cookie=first)
        _, b, _ = self.call(cookie=second)
        self.assertTrue(a['cloud'])
        self.assertNotEqual(a['token'], b['token'])
        state = copy.deepcopy(a['state'])
        state['child'] = {'name': '测试', 'months': 50, 'avatar': 'bear', 'interests': []}
        save = {'revision': a['revision'], 'state': state}
        self.assertEqual(self.call(method='PUT', body=save, cookie=first, csrf=a['token'])[0], 200)
        initialize(self.server.db)
        self.assertEqual(self.call(cookie=second)[1]['state']['child']['name'], '测试')
        self.assertEqual(self.call(method='PUT', body=save, cookie=second, csrf=b['token'])[0], 409)

    def test_csrf_and_session_tokens_are_bound_to_each_device(self):
        first, second = self.login(), self.login()
        data = self.call(cookie=first)[1]
        body = {'revision': data['revision'], 'state': data['state']}
        for cookie, token, origin in [(first, '', True), (second, data['token'], True), (first, data['token'], False), (first, data['token'], 'https://evil.example')]:
            self.assertEqual(self.call(method='PUT', body=body, cookie=cookie, csrf=token, origin=origin)[0], 403)
        self.assertEqual(self.call('/api/login', 'POST', {}, origin='https://evil.example')[0], 403)
        self.assertEqual(self.call('/api/study-event', 'POST', {}, cookie=first, csrf=data['token'], origin=False)[0], 403)

    def test_logout_expiry_and_password_change_revoke_sessions(self):
        first, second = self.login(), self.login()
        data = self.call(cookie=first)[1]
        self.assertEqual(self.call('/api/logout', 'POST', {}, cookie=first, csrf=data['token'])[0], 200)
        self.assertEqual(self.call(cookie=first)[0], 401)
        self.assertEqual(self.call(cookie=second)[0], 200)
        # Same credentials across restart preserve login, credential change invalidates it.
        cloud.configure(self.server, self.origin, 'family', 'test-only-password-123')
        self.assertEqual(self.call(cookie=second)[0], 200)
        cloud.configure(self.server, self.origin, 'family', 'new-test-password-456')
        self.assertEqual(self.call(cookie=second)[0], 401)
        with connect(self.server.db) as c:
            c.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.call(cookie=second)[0], 401)

    def test_login_rate_limit_survives_restart(self):
        for _ in range(8):
            self.assertEqual(self.call('/api/login', 'POST', {'username': 'family', 'password': 'wrong'})[0], 401)
        cloud.configure(self.server, self.origin, 'family', 'test-only-password-123')
        self.assertEqual(self.call('/api/login', 'POST', {'username': 'family', 'password': 'test-only-password-123'})[0], 429)
        with connect(self.server.db) as c:
            c.execute('UPDATE login_limit SET reset_at=0')
        self.login()

    def test_cloud_refuses_weak_password_or_insecure_origin(self):
        for origin, password in [('http://family.example', 'test-only-password-123'), (self.origin, 'short')]:
            with self.assertRaises(ValueError):
                cloud.configure(self.server, origin, 'family', password)


if __name__ == '__main__':
    unittest.main()
