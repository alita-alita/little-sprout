"""Explicit, transactional init/import. Never reads the local production DB."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
from server import initialize, validate, connect
from cloud_server import prepare_auth
from storage import is_postgres


def initialize_cloud(database):
    if not is_postgres(database):
        raise ValueError('需要 PostgreSQL DATABASE_URL')
    initialize(database)
    prepare_auth(database)


def import_backup(database, document):
    if document.get('app') != 'little-sprout' or document.get('version') != 1:
        raise ValueError('不是可用的小芽备份')
    state = validate(document.get('state'))
    with connect(database) as c:
        c.execute('BEGIN IMMEDIATE')
        revision, payload = c.execute('SELECT revision,payload FROM state WHERE id=1').fetchone()
        old = json.loads(payload)
        if revision != 0 or old.get('child') or old.get('plans'):
            raise ValueError('目标已有记录，导入已取消；请使用应用内恢复并先导出备份')
        updated = dt.datetime.now(dt.timezone.utc).isoformat()
        c.execute('UPDATE state SET revision=?,payload=?,updated=? WHERE id=1',
                  (1, json.dumps(state, ensure_ascii=False), updated))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['init', 'import'])
    parser.add_argument('--file', type=Path)
    args = parser.parse_args()
    try:
        database = os.environ.get('DATABASE_URL', '')
        if not is_postgres(database):
            raise ValueError('请先在服务端配置 DATABASE_URL')
        if args.action == 'init':
            initialize_cloud(database)
        else:
            if args.file is None or args.file.stat().st_size > 8 * 1024 * 1024:
                raise ValueError('请选择不超过8MB的JSON备份')
            import_backup(database, json.loads(args.file.read_text(encoding='utf-8')))
    except Exception:
        print('操作未完成；请核对配置、初始化状态和备份。未输出密钥或备份内容。', file=sys.stderr)
        sys.exit(1)
    print('操作已完成；已有数据不会被初始化覆盖。')
