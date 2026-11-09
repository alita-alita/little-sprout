"""Local-only Little Sprout application. Python standard library, SQLite persistence."""
import argparse
import datetime as dt
import errno
import json
import os
from pathlib import Path
import secrets
import re
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import learning
from learning import apply_event, validate_study
import course_builder
from practice import apply_practice_event, validate_practice
import course_editor
import course_images
from storage import connect, DB_ERRORS, is_postgres
from cloudbase_http import CloudBaseConflict

ROOT = Path(__file__).resolve().parent
KINDS = {'english', 'math', 'chinese', 'sport'}
EMPTY = {'version': 1, 'child': None, 'plans': [], 'selectedPlanId': None}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def text(value, limit):
    return isinstance(value, str) and len(value) <= limit

def valid_date(value):
    try:
        return isinstance(value, str) and dt.date.fromisoformat(value).isoformat() == value
    except (ValueError, TypeError):
        return False

def validate(state):
    require(isinstance(state, dict) and state.get('version') == 1, '备份版本不支持')
    child = state.get('child')
    if child is not None:
        require(isinstance(child, dict) and text(child.get('name'), 12) and child['name'].strip(), '孩子昵称需为1—12字')
        require(type(child.get('months')) is int and 48 <= child['months'] <= 59, '本版适用于48—59个月孩子')
        require(child.get('avatar') in ['bear', 'sun', 'leaf', 'rabbit'], '头像无效')
        require(isinstance(child.get('interests'), list) and len(child['interests']) <= 4 and all(x in ['动物', '颜色', '故事', '音乐'] for x in child['interests']), '兴趣无效')
    plans = state.get('plans')
    require(isinstance(plans, list) and len(plans) <= 500, '计划格式无效或数量过多')
    require(child is not None or not plans, '请先建立孩子档案')
    ids = set()
    for p in plans:
        require(isinstance(p, dict) and text(p.get('id'), 80) and p['id'] and p['id'] not in ids, '计划标识无效或重复')
        ids.add(p['id'])
        require(type(p.get('duration')) is int and 1 <= p['duration'] <= 90, '周期须为1—90天')
        require(valid_date(p.get('start')), '开始日期无效')
        require(text(p.get('name'), 30) and p['name'].strip(), '计划名称无效')
        require(p.get('status') in ['active', 'archived'], '计划状态无效')
        if p['status'] == 'archived':
            require(valid_date(p.get('archivedDate')), '归档日期无效')
        require(isinstance(p.get('days'), list) and len(p['days']) == p['duration'], '每日安排不完整')
        for day in p['days']:
            require(isinstance(day, list) and len(day) == 2, '每天需要两项活动')
            require(day[0].get('type') in KINDS - {'sport'} and day[1].get('type') == 'sport', '活动方向无效')
            for task in day:
                require(isinstance(task, dict) and text(task.get('id'), 80) and task['id'], '任务标识无效')
                for key, limit in [('title', 60), ('subtitle', 120), ('materials', 240), ('tip', 400), ('condition', 240), ('word', 80)]:
                    require(text(task.get(key, ''), limit), '任务内容无效')
                require(type(task.get('minutes')) is int and 1 <= task['minutes'] <= 20, '活动时长无效')
                for key in ['steps', 'easy']:
                    require(isinstance(task.get(key), list) and 1 <= len(task[key]) <= 5 and all(text(x, 300) for x in task[key]), '任务步骤无效')
        records = p.get('records')
        require(isinstance(records, dict) and len(records) <= p['duration'], '记录无效')
        for key, record in records.items():
            require(key.isdigit() and str(int(key)) == key and 1 <= int(key) <= p['duration'] and isinstance(record, dict), '记录日期无效')
            require(text(record.get('note', ''), 300), '观察最多300字')
            for slot in ['learning', 'sport']:
                value = record.get(slot)
                if value is not None:
                    require(isinstance(value, dict) and type(value.get('done')) is bool, '完成状态无效')
                    require(value.get('mode') in ['standard', 'easy'], '玩法无效')
                    require(value.get('reaction', '') in ['', '很喜欢', '一般', '有点难'], '反馈无效')
                    require(text(value.get('time', ''), 60), '记录时间无效')
        validate_study(p)
        validate_practice(p)
    assignments = state.get('courseAssignments', [])
    require(isinstance(assignments, list) and len(assignments) <= 500 and (not assignments or child), '自编课安排无效')
    assignment_ids = set()
    for item in assignments:
        require(isinstance(item, dict) and text(item.get('id'), 80) and item['id'] and item['id'] not in assignment_ids
                and valid_date(item.get('date')), '自编课日期或标识无效')
        assignment_ids.add(item['id'])
        entry = item.get('entry')
        require(isinstance(entry, dict), '自编课记录无效')
        lesson = learning.LESSONS.get(entry.get('lessonId'), {})
        subject = lesson.get('type')
        require(lesson.get('courseId') and subject in ('chinese', 'math'), '缺少自编课程版本')
        require(text(item.get('startedAt', ''), 60) and (item.get('startedAt') or not entry.get('steps')),
                '自编课开始记录无效')
        validate_study({'duration': 1, 'study': {'version': 1, 'startDay': 1, 'subjects': [subject]},
                        'records': {'1': {'study': {subject: entry}}}})
    require(state.get('selectedPlanId') is None or state['selectedPlanId'] in ids, '所选计划不存在')
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    active = [p for p in plans if p['status'] == 'active' and dt.date.fromisoformat(p['start']) + dt.timedelta(days=p['duration']) > today]
    require(len(active) <= 1, '只能有一个待开始或进行中的计划')
    return state

def initialize(db):
    with connect(db) as connection:
        if is_postgres(db):
            connection.execute('CREATE SCHEMA IF NOT EXISTS sprout')
            connection.execute('REVOKE ALL ON SCHEMA sprout FROM PUBLIC')
        connection.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL, updated TEXT NOT NULL)')
        connection.execute('CREATE TABLE IF NOT EXISTS revisions (revision INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL)')
        connection.execute('CREATE TABLE IF NOT EXISTS learning_events (id TEXT PRIMARY KEY, request TEXT NOT NULL, result TEXT NOT NULL)')
        connection.execute('INSERT INTO state VALUES (1,0,?,?) ON CONFLICT (id) DO NOTHING', (json.dumps(EMPTY), dt.datetime.now(dt.timezone.utc).isoformat()))
        if db != 'cloudbase+https' and not is_postgres(db):
            course_builder.initialize(connection)
            learning.LESSONS.update(course_builder.releases(connection))
        if is_postgres(db):
            for table in ('state', 'revisions', 'learning_events'):
                connection.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
                connection.execute(f'REVOKE ALL ON TABLE {table} FROM PUBLIC')

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        # Do not log names, notes, backup bodies, or request headers.
        pass

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def json_response(self, code, body):
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    @property
    def request_token(self):
        return self.server.token

    def expected_origin(self):
        return f'http://{self.headers.get("Host", "")}'

    def allowed(self):
        return self.headers.get('Host') in [f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}']

    def do_GET(self):
        if not self.allowed():
            return self.json_response(403, {'error': '仅支持本机访问'})
        path = urlsplit(self.path).path
        if path == '/api/state':
            with connect(self.server.db) as connection:
                known = self.headers.get('X-Sprout-Revision')
                if known is not None:
                    current = connection.execute('SELECT revision FROM state WHERE id=1').fetchone()[0]
                    if str(current) == known:
                        return self.json_response(200, {'unchanged': True, 'revision': current})
                revision, payload, updated = connection.execute('SELECT revision,payload,updated FROM state WHERE id=1').fetchone()
            return self.json_response(200, {'revision': revision, 'state': json.loads(payload), 'updated': updated, 'token': self.request_token, 'cloud': bool(getattr(self.server, 'cloud', False))})
        if path == '/api/course-images':
            if getattr(self.server,'cloud',False):return self.json_response(501,{'error':'图片生成目前在本机使用'})
            try:
                ident=parse_qs(urlsplit(self.path).query).get('id',[None])[0]
                return self.json_response(200,course_images.job(ident) if ident else course_images.status())
            except ValueError as error:return self.json_response(400,{'error':str(error)})
        if path == '/api/course-builder':
            if getattr(self.server, 'cloud', False):
                return self.json_response(501, {'error': '请在本机版创建和安排课程'})
            ident = parse_qs(urlsplit(self.path).query).get('id', [None])[0]
            try:
                with connect(self.server.db) as connection:
                    result = course_builder.get(connection, ident) if ident else course_builder.summary(connection)
                return self.json_response(200, result)
            except ValueError as error:
                return self.json_response(400, {'error': str(error)})
        if path == '/curriculum.json' and not getattr(self.server, 'cloud', False):
            with connect(self.server.db) as connection:
                authored = course_builder.releases(connection)
            lessons = {key: value for key, value in learning.LESSONS.copy().items() if not value.get('courseId')}
            return self.json_response(200, {**learning.CATALOG, 'lessons': {**lessons, **authored}})
        if path == '/api/courses':
            if getattr(self.server,'cloud',False):return self.json_response(501,{'error':'课程编辑目前在本机使用，云端管理尚未启用'})
            try:
                base=parse_qs(urlsplit(self.path).query).get('id',['english-1'])[0]
                with connect(self.server.db) as connection:return self.json_response(200,course_editor.get(connection,base))
            except ValueError as error:return self.json_response(400,{'error':str(error)})
        # Explicit static allowlist prevents serving the database or Python source.
        picture=bool(re.fullmatch(r'/assets/pictures/[a-f0-9]{24}\.(png|jpg)',path))
        if not picture and not re.fullmatch(r'/assets/audio/(?:en|zh)/[a-f0-9]{24}\.(?:wav|mp3)', path) and path not in ['/', '/index.html', '/styles.css', '/v1.css', '/study.css', '/icons.js', '/content.js', '/curriculum.json', '/study-model.js', '/study-ui.js', '/speech.js', '/repeat.js', '/english-audio.js', '/chinese-audio.js', '/model.js', '/sync-model.js', '/app.js', '/course-editor.js', '/course-builder.js', '/tabletop.js', '/assets/course-fruits.png', '/course-editor.css', '/image-options.js', '/image-generator.js', '/assets/garden.png', '/assets/sprout.png', '/favicon.ico']:
            return self.json_response(404, {'error': '页面不存在'})
        if path == '/favicon.ico':
            self.send_response(204)
            return self.end_headers()
        super().do_GET()

    def do_PUT(self):
        expected_origin = self.expected_origin()
        if not self.allowed() or self.headers.get('Origin', expected_origin) != expected_origin or self.headers.get('X-Sprout-Token') != self.request_token:
            return self.json_response(403, {'error': '请从本机应用重新打开后保存'})
        if self.path != '/api/state':
            return self.json_response(404, {'error': '接口不存在'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            require(0 < length <= 8 * 1024 * 1024, '备份文件过大或为空')
            body = json.loads(self.rfile.read(length))
            require(type(body.get('revision')) is int, '保存版本无效')
            state = validate(body.get('state'))
            payload = json.dumps(state, ensure_ascii=False)
            updated = dt.datetime.now(dt.timezone.utc).isoformat()
            with connect(self.server.db) as connection:
                connection.execute('BEGIN IMMEDIATE')
                revision, old_payload, old_updated = connection.execute('SELECT revision,payload,updated FROM state WHERE id=1').fetchone()
                if body['revision'] != revision:
                    connection.rollback()
                    return self.json_response(409, {'error': '另一页面已更新记录，请重新加载后再试'})
                if not body.get('restore'):
                    old_state = json.loads(old_payload)
                    require(state.get('courseAssignments', []) == old_state.get('courseAssignments', []), '请通过课程管理修改安排')
                    old_plans = {p['id']: p for p in old_state['plans']}
                    for plan in state['plans']:
                        old = old_plans.get(plan['id'], {})
                        require(plan.get('courseQueue', []) == old.get('courseQueue', []), '课程安排请通过课程管理保存')
                        if old.get('study'):
                            require(plan.get('study') == old['study'], '进行中的自主学习设置不能直接改写')
                        for day in set(old.get('records', {})) | set(plan['records']):
                            before = old.get('records', {}).get(day, {}).get('study', {})
                            after = plan['records'].get(day, {}).get('study', {})
                            require(before == after, '学习进度须通过互动完成；恢复备份请使用恢复入口')
                            require(old.get('records', {}).get(day, {}).get('practice', {}) == plan['records'].get(day, {}).get('practice', {}), '复习进度须通过复习入口保存')
                connection.execute('INSERT INTO revisions VALUES (?,?,?) ON CONFLICT (revision) DO UPDATE SET payload=excluded.payload,updated=excluded.updated', (revision, old_payload, old_updated))
                connection.execute('DELETE FROM revisions WHERE revision < ?', (revision - 29,))
                connection.execute('UPDATE state SET revision=?,payload=?,updated=? WHERE id=1', (revision + 1, payload, updated))
            return self.json_response(200, {'revision': revision + 1, 'updated': updated})
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return self.json_response(400, {'error': str(exc) if isinstance(exc, ValueError) else '数据格式不正确'})
        except CloudBaseConflict:
            return self.json_response(409, {'error': '另一页面已更新记录，请重新加载后再试'})
        except DB_ERRORS:
            return self.json_response(503, {'error': '数据库暂时无法保存，请稍后重试；当前输入仍保留'})

    def do_POST(self):
        expected_origin = self.expected_origin()
        if not self.allowed() or self.headers.get('Origin', expected_origin) != expected_origin or self.headers.get('X-Sprout-Token') != self.request_token:
            return self.json_response(403, {'error': '请重新打开本机应用后继续学习'})
        if self.path == '/api/course-images':
            if getattr(self.server,'cloud',False):return self.json_response(501,{'error':'图片生成目前在本机使用'})
            try:
                length=int(self.headers.get('Content-Length',0));require(0<length<=4096,'图片请求无效')
                body=json.loads(self.rfile.read(length))
                if body.get('action')=='configure':result=course_images.configure(body)
                elif body.get('action')=='approve':result=course_images.approve(body.get('id'))
                elif body.get('action')=='generate':result=course_images.start(body)
                else:raise ValueError('图片操作无效')
                return self.json_response(200,result)
            except (ValueError,TypeError,KeyError,AttributeError) as error:return self.json_response(400,{'error':str(error)})
        if self.path == '/api/course-builder':
            if getattr(self.server, 'cloud', False):
                return self.json_response(501, {'error': '请在本机版创建和安排课程'})
            try:
                length = int(self.headers.get('Content-Length', 0))
                require(0 < length <= 262144, '课程内容过大')
                body = json.loads(self.rfile.read(length))
                with connect(self.server.db) as connection:
                    if body.get('action') != 'audio':
                        connection.execute('BEGIN IMMEDIATE')
                    result = course_builder.act(connection, body)
                    if body.get('action') == 'publish':
                        learning.LESSONS.update(course_builder.releases(connection))
                return self.json_response(200, result)
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                return self.json_response(400, {'error': str(error) if isinstance(error, ValueError) else '课程内容格式不正确'})
            except DB_ERRORS:
                return self.json_response(503, {'error': '暂时无法保存课程，请重试'})
        if self.path == '/api/courses':
            if getattr(self.server,'cloud',False):return self.json_response(501,{'error':'课程编辑目前在本机使用，云端管理尚未启用'})
            try:
                length=int(self.headers.get('Content-Length',0))
                require(0<length<=262144,'课程内容过大')
                body=json.loads(self.rfile.read(length))
                with connect(self.server.db) as connection:result=course_editor.act(connection,body)
                return self.json_response(200,result)
            except (ValueError,TypeError,KeyError,AttributeError) as error:return self.json_response(400,{'error':str(error)})
            except DB_ERRORS:return self.json_response(503,{'error':'草稿暂时没有保存，请重试'})
        if self.path not in ['/api/study-event', '/api/practice-event']:
            return self.json_response(404, {'error': '接口不存在'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            require(0 < length <= 16384, '学习请求无效')
            body = json.loads(self.rfile.read(length))
            require(type(body.get('revision')) is int and text(body.get('eventId'), 80) and body['eventId'], '学习请求标识无效')
            event_data = {k: v for k, v in body.items() if k != 'revision'}
            if self.path == '/api/practice-event':
                event_data['endpoint'] = 'practice'
            event_request = json.dumps(event_data, sort_keys=True)
            with connect(self.server.db) as connection:
                connection.execute('BEGIN IMMEDIATE')
                revision, payload, old_updated = connection.execute('SELECT revision,payload,updated FROM state WHERE id=1').fetchone()
                repeated = connection.execute('SELECT request,result FROM learning_events WHERE id=?', (body['eventId'],)).fetchone()
                if repeated:
                    require(repeated[0] == event_request, '同一个请求标识不能用于不同操作')
                    return self.json_response(200, {'revision': revision, 'state': json.loads(payload), 'updated': old_updated, 'result': json.loads(repeated[1])})
                if revision != body['revision']:
                    return self.json_response(409, {'error': '另一页面更新了记录，请读取最新进度后继续'})
                state = json.loads(payload)
                result = apply_practice_event(state, body) if self.path == '/api/practice-event' else apply_event(state, body)
                validate(state)
                updated = dt.datetime.now(dt.timezone.utc).isoformat()
                connection.execute('INSERT INTO revisions VALUES (?,?,?) ON CONFLICT (revision) DO UPDATE SET payload=excluded.payload,updated=excluded.updated', (revision, payload, old_updated))
                connection.execute('DELETE FROM revisions WHERE revision < ?', (revision - 29,))
                connection.execute('UPDATE state SET revision=?,payload=?,updated=? WHERE id=1', (revision+1, json.dumps(state, ensure_ascii=False), updated))
                connection.execute('INSERT INTO learning_events VALUES (?,?,?)', (body['eventId'], event_request, json.dumps(result)))
            response = {'revision': revision+1, 'updated': updated, 'result': result}
            if self.headers.get('X-Sprout-Delta') == '1' and not body.get('assignmentId'):
                plan = next(p for p in state['plans'] if p['id'] == body['planId'])
                response['patch'] = {'planId': plan['id'], 'day': body['day'],
                                     'record': plan['records'][str(body['day'])],
                                     'selectedPlanId': state['selectedPlanId']}
            else:
                response['state'] = state
            return self.json_response(200, response)
        except (ValueError, TypeError, KeyError, AttributeError, IndexError) as error:
            return self.json_response(400, {'error': str(error) if isinstance(error, ValueError) else '学习数据格式不正确'})
        except CloudBaseConflict:
            return self.json_response(409, {'error': '另一页面更新了记录，请读取最新进度后继续'})
        except DB_ERRORS:
            return self.json_response(503, {'error': '暂时没能保存，先别退出，恢复连接后可以重试'})

def serve(port=4318, db=None):
    os.umask(0o077)
    database = Path(db or ROOT / 'data' / 'sprout.sqlite3')
    database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if database.parent == ROOT / 'data':
        os.chmod(database.parent, 0o700)
    initialize(str(database))
    os.chmod(database, 0o600)
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.db = str(database)
    server.token = secrets.token_urlsafe(32)
    print(f'小芽陪伴已启动：http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=4318)
    parser.add_argument('--db')
    args = parser.parse_args()
    try:
        serve(args.port, args.db)
    except KeyboardInterrupt:
        print('\n小芽陪伴已关闭，记录保留在本机。')
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            print(f'这个地址已被使用。如果小芽已在运行，请打开 http://127.0.0.1:{args.port}/ ，不用重复启动。')
        else:
            raise
