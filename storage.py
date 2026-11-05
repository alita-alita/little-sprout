"""Small DB-API boundary: local SQLite or server-only PostgreSQL.

Queries are application constants using qmark parameters; values are always bound.
Cloud tables live in a private schema, outside CloudBase's public REST schema.
"""
import os
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from cloudbase_http import CloudBaseError, HttpConnection

try:
    import psycopg
except ImportError:
    psycopg = None

DB_ERRORS = (sqlite3.Error, CloudBaseError) + ((psycopg.Error,) if psycopg else ())


def is_postgres(database):
    return str(database).startswith(('postgresql://', 'postgres://'))


class PostgresConnection:
    def __init__(self, database):
        if psycopg is None:
            raise RuntimeError('请先安装 requirements-cloudbase.txt 中的服务端依赖')
        mode = parse_qs(urlsplit(database).query).get('sslmode', ['verify-full'])[-1]
        if mode not in ('verify-full', 'verify-ca', 'require'):
            host = urlsplit(database).hostname
            socket = parse_qs(urlsplit(database).query).get('host', [''])[-1]
            local_socket = bool(socket) and Path(socket).is_absolute() and Path(socket).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
            local = host in ('127.0.0.1', 'localhost') or not host and local_socket
            if not (os.environ.get('SPROUT_TEST_DATABASE') == '1' and local):
                raise ValueError('云数据库连接必须使用 TLS；请配置 sslmode=verify-full 及所需证书')
        self.raw = psycopg.connect(database, sslmode=mode, connect_timeout=5,
                                   prepare_threshold=None,
                                   options='-c search_path=sprout -c statement_timeout=2500 -c lock_timeout=1800')

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        return self.raw.__exit__(kind, value, traceback)

    def execute(self, query, params=()):
        if query == 'BEGIN IMMEDIATE':
            # One household per deployment. All mutating transactions serialize
            # on the state row, including login throttles and replay event IDs.
            return self.raw.execute('SELECT id FROM state WHERE id=1 FOR UPDATE')
        return self.raw.execute(query.replace('?', '%s'), params)

    def rollback(self):
        return self.raw.rollback()


def connect(database):
    if database == 'cloudbase+https':
        return HttpConnection()
    if is_postgres(database):
        return PostgresConnection(database)
    connection = sqlite3.connect(database, timeout=10)
    connection.execute('PRAGMA journal_mode=WAL')
    return connection
