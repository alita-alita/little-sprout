"""One private household per deployment. TLS is terminated by the hosting proxy."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import urlsplit

from server import Handler, ThreadingHTTPServer, initialize, connect

COOKIE = '__Host-sprout_session'
SESSION_SECONDS = 14 * 86400


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def prepare_auth(db):
    with connect(db) as c:
        c.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires INTEGER NOT NULL, credential TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS login_limit (id INTEGER PRIMARY KEY CHECK(id=1), failures INTEGER NOT NULL, reset_at INTEGER NOT NULL)')
        c.execute('INSERT OR IGNORE INTO login_limit VALUES (1,0,0)')
        c.execute('CREATE TABLE IF NOT EXISTS auth_config (id INTEGER PRIMARY KEY CHECK(id=1), salt BLOB NOT NULL)')
        c.execute('INSERT OR IGNORE INTO auth_config VALUES (1,?)', (secrets.token_bytes(32),))


class CloudHandler(Handler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def do_HEAD(self):
        self.send_response(405)
        self.end_headers()

    def expected_origin(self):
        return self.server.origin

    def allowed(self):
        return self.headers.get('Host') == urlsplit(self.server.origin).netloc

    def end_headers(self):
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Strict-Transport-Security', 'max-age=31536000')
        super().end_headers()

    def session(self):
        if hasattr(self, '_session'):
            return self._session
        self._session = None
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            value = cookie[COOKIE].value if COOKIE in cookie else ''
            if not value or len(value) > 100:
                return None
            with connect(self.server.db) as c:
                row = c.execute('SELECT csrf FROM sessions WHERE id=? AND expires>? AND credential=?',
                                (digest(value), int(time.time()), self.server.credential)).fetchone()
            if row:
                self._session = (digest(value), row[0])
        except (ValueError, CookieError, sqlite3.Error):
            pass
        return self._session

    @property
    def request_token(self):
        session = self.session()
        return session[1] if session else ''

    def authenticated(self):
        if not self.allowed():
            self.json_response(403, {'error': '请使用正式应用地址'})
            return False
        if not self.session():
            self.json_response(401, {'error': '请先登录家庭账号', 'loginRequired': True})
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/healthz':
            try:
                with connect(self.server.db) as c:
                    c.execute('SELECT revision FROM state WHERE id=1').fetchone()
                return self.json_response(200, {'ok': True})
            except sqlite3.Error:
                return self.json_response(503, {'ok': False})
        if path.startswith('/api/') and not self.authenticated():
            return
        super().do_GET()

    def do_PUT(self):
        if self.authenticated():
            if self.headers.get('Origin') != self.server.origin:
                return self.json_response(403, {'error': '请从应用内操作'})
            super().do_PUT()

    def do_POST(self):
        if self.path == '/api/login':
            return self.login()
        if not self.authenticated():
            return
        if self.path == '/api/logout':
            if self.headers.get('Origin') != self.server.origin or self.headers.get('X-Sprout-Token') != self.request_token:
                return self.json_response(403, {'error': '请刷新页面后重试'})
            with connect(self.server.db) as c:
                c.execute('DELETE FROM sessions WHERE id=?', (self.session()[0],))
            return self.auth_response({'ok': True}, '', 0)
        # An authenticated cloud mutation always requires a browser Origin.
        if self.headers.get('Origin') != self.server.origin:
            return self.json_response(403, {'error': '请从应用内操作'})
        super().do_POST()

    def login(self):
        if not self.allowed() or self.headers.get('Origin') != self.server.origin or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.json_response(403, {'error': '请从应用登录页操作'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 2048:
                raise ValueError()
            body = json.loads(self.rfile.read(length))
            username, password = body.get('username'), body.get('password')
            if not isinstance(username, str) or not isinstance(password, str) or len(username) > 80 or len(password) > 256:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            return self.json_response(400, {'error': '请输入家庭账号和密码'})
        now = int(time.time())
        with connect(self.server.db) as c:
            c.execute('BEGIN IMMEDIATE')
            failures, reset_at = c.execute('SELECT failures,reset_at FROM login_limit WHERE id=1').fetchone()
            if reset_at <= now:
                failures, reset_at = 0, now + 300
            if failures >= 8:
                return self.json_response(429, {'error': '尝试次数较多，请5分钟后再试'})
            derived = hashlib.pbkdf2_hmac('sha256', password.encode(), self.server.password_salt, 600000)
            correct = hmac.compare_digest(derived, self.server.password_hash) & hmac.compare_digest(username.encode(), self.server.username.encode())
            if not correct:
                c.execute('UPDATE login_limit SET failures=?,reset_at=? WHERE id=1', (failures + 1, reset_at))
                result = None
            else:
                c.execute('UPDATE login_limit SET failures=0,reset_at=0 WHERE id=1')
                c.execute('DELETE FROM sessions WHERE expires<=? OR credential!=?', (now, self.server.credential))
                value, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                c.execute('INSERT INTO sessions VALUES (?,?,?,?)', (digest(value), csrf, now + SESSION_SECONDS, self.server.credential))
                result = value
        if result is None:
            return self.json_response(401, {'error': '家庭账号或密码不正确'})
        return self.auth_response({'ok': True}, result, SESSION_SECONDS)

    def auth_response(self, body, value, max_age):
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header('Set-Cookie', f'{COOKIE}={value}; Path=/; Max-Age={max_age}; Secure; HttpOnly; SameSite=Lax')
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def configure(server, origin, username, password):
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('PUBLIC_ORIGIN 必须是 HTTPS 站点根地址，不带路径或尾部斜线')
    if not username or len(username) > 80 or len(password) < 12 or len(password) > 256:
        raise ValueError('请配置 FAMILY_USERNAME 和至少12位的 FAMILY_PASSWORD')
    server.cloud, server.origin, server.username = True, origin, username
    prepare_auth(server.db)
    with connect(server.db) as c:
        server.password_salt = c.execute('SELECT salt FROM auth_config WHERE id=1').fetchone()[0]
    server.password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), server.password_salt, 600000)
    # Bind sessions to credentials, so changing the password revokes all old logins.
    server.credential = digest(username + '\0' + server.password_hash.hex())


def serve():
    os.umask(0o077)
    root = Path(os.environ.get('SPROUT_DATA_DIR', '/var/data/sprout'))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = root / 'sprout.sqlite3'
    initialize(str(db))
    os.chmod(db, 0o600)
    origin = os.environ.get('PUBLIC_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL', '')
    server = ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '10000'))), CloudHandler)
    server.db = str(db)
    configure(server, origin, os.environ.get('FAMILY_USERNAME', ''), os.environ.get('FAMILY_PASSWORD', ''))
    print('小芽家庭在线服务已启动', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    serve()
