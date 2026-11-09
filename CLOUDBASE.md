# 小芽家庭同步版 · CloudBase PostgreSQL

代码及本地 PostgreSQL 测试已准备。本文件不代表已连接腾讯云、已创建函数或已验证免费环境的请求时限。页面、课程和音频保持原有设计。每个部署服务一个家庭，所有设备使用同一个应用家庭账号；不是多家庭注册产品。

## 保存与同步

- `storage.py` 支持本地 SQLite、PostgreSQL 原生连接或 CloudBase HTTPS RPC 接口。免费共享集群使用 HTTPS，无需开通数据库外网或升级独享实例。
- 正式学习、跟读识别文字及分数、打卡结果、家长观察、复习轮次都保存到数据库。
- 跟读支持家长手动确认（不打分）与0—100整数评分，两者保存后均可继续；分别标记 parent-confirm-v1 / parent-score-v1，不伪造识别文字，不混入自动匹配平均分。沿用原状态 JSON 与事件去重结构，无需新增表或执行 SQL。
- 复习保存在每天记录的 `practice` 字段，与正式 `study` 分开。保存每科最新一轮及轮次计数；开始下一轮后不提供过去每轮的单独浏览。
- 刷新或换设备登录后，打开同一课会接着未完成的复习。已有课程完成记录不受复习影响，不重复计入打卡和成长统计。
- 云端写入用事务、行锁及全局版本号，重复事件以唯一标识去重。冲突需读取最新记录，不自动覆盖其他设备。
- 答题成功返回当天记录补丁；重试去重时返回完整最新状态，避免漏掉其他设备的修改。切回页面用版本探测，没变化不重复传输全部历史。没有每秒轮询，当前打开着的另一设备需切回页面或主动重新读取才能看到新结果。
- 未完成的表单、正在跟读和未确认保存的请求不会被后台同步覆盖。声音设置仍为设备专属，不同步设备声音 URI。
- 本地旧 `sprout-practice:*` 草稿保留。在同一浏览器打开对应已完成课程，且尚无服务端复习记录时，显示「把这台设备的旧复习进度同步到家庭记录」。由家长点击导入；有云端记录时不合并、不覆盖。其他浏览器无法读取这份旧草稿。
- JSON 备份包含新的复习记录，旧版没有复习记录的备份仍可恢复。备份恢复替换整个家庭状态，不是合并。

## 数据安全边界

数据位于 PostgreSQL 私有 schema `sprout`，不写入 CloudBase 公开的 `public` schema。所有表启用 RLS，撤销 `PUBLIC` 权限，不设匿名读写策略；仅后端数据库角色访问，浏览器经家庭登录接口访问。

家庭登录沿用自建单家庭账号和 Secure/HttpOnly Cookie，不依赖 CloudBase 终端用户注册。密钥、数据库密码、会话原始令牌不进入网页源码、Git 或应用日志。登录错误限流、会话到期、当前设备退出及重设密码失效规则保留。

共享集群 HTTPS 模式使用服务端专用 API Key，经 `/v1/rdb/rest/rpc/sprout_server_bridge` 调用事务函数。此前 `exec-pgsql` 在实际环境以带实例后缀的只读角色执行，与文档描述不同；不再使用该接口，也不向平台内置只读角色授予写权限。

公开 schema 仅增加一个 SECURITY INVOKER 的 RPC 包装函数；业务表仍在私有 schema。包装函数显式检查受网关验证的 JWT claims 中 role 必须为 `service_role`，缺失或其他身份一律拒绝，不只依赖网关的函数 EXECUTE 检查。数据库脚本仅向已存在的 `service_role` 授予私有 schema 使用权、六张表的 DML 和两个私有函数执行权。它具备 BYPASSRLS，API Key 只能填云函数环境变量，不能填前端。建议专用 CloudBase 环境，不与其他业务共享。

若使用独享实例原生连接，推荐专用数据库角色拥有 `sprout` schema 及其表；初始化与运行角色不同时需核对权限。

HTTPS 模式使用系统 CA 验证腾讯云网关证书，拒绝重定向，避免转发管理密钥。原生 PostgreSQL 连接的 TLS 默认 `verify-full`，私有 CA 可配置 `PGSSLROOTCERT`。例外开关 `SPROUT_TEST_DATABASE=1` 仅供本地临时数据库测试，线上不可设置。

## 需要的环境配置（暂时不需要发密码）

| 参数 | 用途 |
| --- | --- |
| CloudBase 环境 ID、上海地域 | 确定部署目标、连接和路由 |
| `CLOUDBASE_ENV_ID` | 当前 CloudBase 环境 ID |
| `CLOUDBASE_API_KEY` | 当前环境管理员 API Key；只填服务端，不能用 Publishable Key 替代 |
| `DATABASE_URL`（共享版不填） | 仅独享实例原生连接使用；设置后优先于 HTTPS 模式 |
| `PUBLIC_ORIGIN` | 应用最终 HTTPS 根网址，无尾部斜线；需与浏览器实际访问域名一致 |
| `FAMILY_USERNAME` | 家长自定的应用家庭账号，不是腾讯云登录账号 |
| `FAMILY_PASSWORD` | 至少12位，直接填写在函数服务端环境变量 |
| `PGSSLROOTCERT`（按需） | 服务商 CA 文件路径 |

模板见 `.env.example`。代码不会自动读取本机 `.env` 文件；请由运行平台注入环境变量。

## 初始化和迁移

不使用本地终端时，可在 CloudBase「数据库 → SQL 编辑器」打开并整段执行 `sql/init_cloudbase.sql`，再执行 `sql/check_cloudbase.sql` 核对6张表的 RLS 和3项初始化状态。脚本不删除表、不覆盖数据，也不会替换已有登录盐；不需要填写任何密码。后续运行时数据库账号仍需具备该私有 schema 的访问权限。

**免费共享集群还需依次执行 `sql/cloudbase_http_bridge.sql` 和 `sql/cloudbase_rpc_bridge.sql`**，分别返回 `http_bridge_ready=true` 和 `rpc_bridge_ready=true`。脚本可重复执行，不删除或覆盖学习记录。前者增加私有事务函数，后者增加受身份检查的 RPC 包装及 `service_role` 所需权限。所有运行时读取通过 HTTPS RPC 接口；一次保存的写入在单次函数调用中持有行锁、重新核对读取快照后原子提交。若另一设备已修改，返回409，由前端重新读取；网络失败返回503，原事件 ID 可安全重试。不能把跨 HTTP 请求的 BEGIN/COMMIT 当作一个事务。

共享版无需数据库密码、外网地址、安全组或数据库 SSL 开关。不能使用下述原生连接命令直接连接免费共享实例；已有数据用在线版家长空间恢复 JSON 备份。

在能访问数据库的安全终端中安装依赖并设置 `DATABASE_URL`：

```sh
python3 -m pip install -r requirements-cloudbase.txt
python3 migrate_cloudbase.py init
```

初始化只创建缺少的表和初始空状态，不覆盖记录，也不在每次冷启动中做 DDL。运行角色必须有 `sprout` 的权限；建议在单独应用环境初始化。

电脑本地版先在「家长空间」导出 JSON，再选择一种方式迁移：

1. 空数据库可用 `python3 migrate_cloudbase.py import --file /安全路径/小芽备份.json`。如果目标已有记录，该命令会拒绝导入。
2. 或在新部署的家庭在线版登录，建立临时档案后通过家长空间恢复；先导出已有线上副本，确认替换。

命令不会主动寻找或复制本机正式数据库，也不会在日志打印连接串或备份内容。迁移结束后用两台设备核对。持久保存需要环境持续有效；定期导出独立备份，避免试用到期或销毁造成丢失。

## HTTP 云函数部署准备

推荐先验证 Python3.11 HTTP 云函数；`scf_bootstrap` 监听9000端口并从 `third_party` 加载依赖。保持最小实例0、不启用保活任务。代码不常驻数据库连接，不会主动阻止数据库自动暂停。

在与云函数架构匹配的 **Linux / Python3.11** 构建环境执行：

```sh
python3.11 -m pip install -r requirements-cloudbase.txt -t third_party
python3.11 package_cloudbase.py
```

生成 `dist/little-sprout-cloudbase.zip`。包采用文件白名单，包含页面、课程、当前 MP3、后端及依赖，不包含 `.env`、本机数据、Git、测试数据库。不能把 macOS 的 psycopg 二进制包直接部署到 Linux；构建脚本会拒绝含 dylib 的依赖目录。

后续手动或经授权部署到已开通环境，选择 **HTTP 云函数、Python3.11**，配置服务端变量；将应用域名的 `/` 与所有子路径统一转发到同一个函数，保留原路径和外部 Host。不能只转发 `/api` 却未配置同源页面/凭证策略。首次先用新网址验证，再考虑旧 Pages 入口。

共享 HTTPS 适配通过本地独立 PostgreSQL 事务与模拟网关测试，尚未用真实 CloudBase API Key 联调。实际网关角色权限、响应格式、往返延迟以及免费函数3秒限制仍需部署验证；本地测试不代表这些平台条件已通过。不要为调试自动升级或开通收费网络。

CloudBase 暂未完成实机联调：需要核对实际网关是否保留 Host、TLS 证书、数据库连接池和自动暂停行为。免费函数3秒限制可能让数据库唤醒、网络连接或等待行锁失败；接口会返回保存失败供重试，不把失败当成功。应以真实环境的冷启动测试和资源点统计决定能否长期使用免费套餐，不能据本地测试承诺免费额度足够。

## 验证

本机版本无第三方运行依赖：

```sh
node --test tests/*.test.cjs
python3 -m unittest discover -s tests -v
```

完整真实 PostgreSQL 测试需另装测试依赖（只用于开发）：

```sh
python3 -m pip install -r requirements-test-postgres.txt
python3 -m unittest discover -s tests -v
```

`pgserver` 启动独立临时 PostgreSQL，不访问你的腾讯云或正式孩子数据；未安装它时 PostgreSQL 专项会明确跳过。覆盖双设备保存、并发冲突、请求去重、会话、私有 schema/RLS、复习与正式记录隔离、旧草稿导入、备份恢复及回滚。前端测试覆盖保存失败重试、服务端确认前不推进、轮次切换及当天补丁合并。

参考：[CloudBase PostgreSQL 连接](https://docs.cloudbase.net/database/postgresql/connecting-to-postgresql)、[Python HTTP函数](https://docs.cloudbase.net/cloud-function/quickstart/httpfunc/python)。
