"""CloudBase HTTP function / container entry. Migrations run separately."""
import os
import sys
from urllib.parse import urlsplit
from cloud_server import CloudHandler, ThreadingHTTPServer, configure
from storage import is_postgres
from cloudbase_http import CloudBaseError


class StartupError(Exception):
    pass


def build_server():
    for name in ('PUBLIC_ORIGIN', 'FAMILY_USERNAME', 'FAMILY_PASSWORD'):
        if not os.environ.get(name):
            raise StartupError(f'缺少环境变量 {name}')
    database = os.environ.get('DATABASE_URL', '') or 'cloudbase+https'
    if database != 'cloudbase+https' and not is_postgres(database):
        raise StartupError('DATABASE_URL 格式不正确；免费共享版请删除这个变量')
    if database == 'cloudbase+https':
        for name in ('CLOUDBASE_ENV_ID', 'CLOUDBASE_API_KEY'):
            if not os.environ.get(name):
                raise StartupError(f'缺少环境变量 {name}')
    origin = urlsplit(os.environ['PUBLIC_ORIGIN'])
    if origin.scheme != 'https' or not origin.netloc or origin.path or origin.query or origin.fragment or origin.username:
        raise StartupError('PUBLIC_ORIGIN 格式错误：应为 HTTPS 根域名，末尾不带斜线或路径')
    if len(os.environ['FAMILY_USERNAME']) > 80 or not 12 <= len(os.environ['FAMILY_PASSWORD']) <= 256:
        raise StartupError('家庭账号过长或 FAMILY_PASSWORD 不满足12至256位要求')
    try:
        port = int(os.environ.get('PORT', '9000'))
        if not 1 <= port <= 65535:
            raise ValueError()
    except ValueError:
        raise StartupError('PORT 必须是有效端口，本项目填写9000') from None
    server = ThreadingHTTPServer(('0.0.0.0', port), CloudHandler)
    server.db = database
    try:
        configure(server, os.environ['PUBLIC_ORIGIN'],
                  os.environ['FAMILY_USERNAME'], os.environ['FAMILY_PASSWORD'],
                  initialize_auth=False)
    except CloudBaseError:
        server.server_close()
        raise
    except Exception:
        server.server_close()
        raise StartupError('数据库登录配置读取失败；请核对初始化脚本及 auth_config 初始记录') from None
    return server


if __name__ == '__main__':
    try:
        server = build_server()
    except (StartupError, CloudBaseError) as error:
        print(f'启动失败：{error}', file=sys.stderr, flush=True)
        sys.exit(1)
    except Exception:
        # Connection strings and driver diagnostics must not leak into cloud logs.
        print('启动失败：请核对服务端环境变量、TLS、网络与数据库初始化状态。', file=sys.stderr)
        sys.exit(1)
    print('小芽 CloudBase 家庭同步服务已启动', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
