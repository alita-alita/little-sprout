"""Server-only HTTPS SQL transport for CloudBase shared PostgreSQL.

Reads are optimistic. One database function locks, rechecks all read values and
commits the complete write set atomically. No transaction spans HTTP requests.
"""
import json
import os
import re
import urllib.request
from urllib.error import URLError, HTTPError


class CloudBaseError(Exception):
    pass


class CloudBaseConflict(CloudBaseError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an administrator key to a redirected origin.
        return None


def request_bridge(body):
    env = os.environ.get('CLOUDBASE_ENV_ID', '')
    key = os.environ.get('CLOUDBASE_API_KEY', '')
    if not re.fullmatch(r'[a-zA-Z0-9-]{1,100}', env) or not key:
        raise CloudBaseError('请配置服务端 CloudBase 环境 ID 和 API Key')
    request = urllib.request.Request(
        f'https://{env}.api.tcloudbasegateway.com/v1/rdb/rest/rpc/sprout_server_bridge',
        data=json.dumps({'request': body}, ensure_ascii=False).encode(),
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
            raw = response.read(24 * 1024 * 1024 + 1)
            if len(raw) > 24 * 1024 * 1024:
                raise ValueError()
            data = json.loads(raw)
        result = data
        if not isinstance(result, dict):
            raise TypeError()
        return result
    except HTTPError as error:
        code = ''
        try:
            candidate = json.loads(error.read(65536)).get('code', '')
            if isinstance(candidate, str) and re.fullmatch(r'(DATABASE_[0-9]{5}|[0-9]{5}|PGRST[0-9]{3}|UNAUTHORIZED|ACTION_FORBIDDEN|INVALID_PARAM|INTERNAL_ERROR)', candidate):
                code = candidate
        except (ValueError, TypeError, AttributeError, OSError):
            pass
        raise CloudBaseError(f'CloudBase RPC 接口 HTTP {error.code} {code}；请核对服务端 API Key 及 cloudbase_rpc_bridge.sql 初始化状态') from None
    except (URLError, TimeoutError, OSError):
        raise CloudBaseError('CloudBase HTTPS 网络连接失败或超时；请核对函数公网访问开关') from None
    except (ValueError, TypeError, KeyError, IndexError):
        # No SQL, child data, credentials or provider response in errors/logs.
        raise CloudBaseError('CloudBase RPC 接口返回格式不符合预期') from None


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class HttpConnection:
    def __init__(self):
        self.reads = []
        self.writes = []
        self.cancelled = False

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        if kind is None and not self.cancelled and self.writes:
            result = request_bridge({'action': 'commit', 'reads': self.reads, 'writes': self.writes})
            if result.get('ok') is not True:
                raise CloudBaseConflict('其他设备已更新，请读取最新进度后重试')

    def rollback(self):
        self.cancelled = True
        self.writes.clear()

    def execute(self, query, params=()):
        if query == 'BEGIN IMMEDIATE':
            return Cursor([])
        operation = {'sql': query, 'params': list(params)}
        if query.startswith('SELECT '):
            if self.writes:
                raise CloudBaseError('HTTP 模式不支持写入后的事务内查询')
            rows = request_bridge(dict(operation, action='read')).get('rows')
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise CloudBaseError('数据库返回格式异常')
            self.reads.append(dict(operation, rows=rows))
            # Runtime SELECTs use explicit, simple column names in known order.
            columns = query.removeprefix('SELECT ').split(' FROM ', 1)[0].split(',')
            try:
                values = [tuple(row[name.strip()] for name in columns) for row in rows]
            except KeyError:
                raise CloudBaseError('数据库返回格式异常') from None
            if columns == ['salt']:
                try:
                    values = [(bytes.fromhex(row[0].removeprefix('\\x')), ) for row in values]
                except (ValueError, AttributeError):
                    raise CloudBaseError('数据库返回格式异常') from None
            return Cursor(values)
        if not query.startswith(('INSERT ', 'UPDATE ', 'DELETE ')):
            raise CloudBaseError('HTTP 模式请通过 SQL 编辑器初始化数据库')
        self.writes.append(operation)
        return Cursor([])
