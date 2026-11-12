# xuetang-api

学堂在线接口自动化测试平台。当前可以一键启动，用账号登录，维护接口定义，调试请求，并按规则返回 Mock。

## 环境依赖

- Docker 与 Docker Compose，用于一键启动。
- 后端镜像内的解释器是 Python 3.12。不要使用 Python 3.13。
- 本机直接跑测试时，使用 `python3.12`。
- 前端构建使用 Node 20，已写在前端镜像里。

## 启动

在仓库根目录执行：

```bash
docker compose up -d --build
```

不需要手工建库或建表。MySQL 镜像会创建 `xuetang_api`，后端启动时执行 `alembic upgrade head`，再执行 `python -m app.seed`。

启动后访问：

- 前端：http://localhost:8080
- 主服务健康检查：http://localhost:8000/api/v1/health
- 主服务文档：http://localhost:8000/api/v1/docs
- Mock 健康检查：http://localhost:8001/health

登录会校验用户名和密码，并签发访问令牌。种子管理员是 `admin`，初始密码见 `.env.example` 的 `ADMIN_PASSWORD`。首次登录需要修改密码。管理员已经存在时，再次启动不会覆盖密码。

开发默认值已经写在 `docker-compose.yml`。要覆盖时，把 `.env.example` 复制为 `.env` 后再改。

## 现在能做什么

接口测试顶部固定为「调试、定义、场景、报告」，默认进入调试。

- **调试**：左侧是模块树，可以展开、重命名、拖动排序，并把接口移进模块。右侧按页签编辑请求。请求头、Query、REST 支持勾选、删除和批量添加。粘贴 curl 会拆进 URL、请求头、Query、REST 和请求体。执行由浏览器直接请求填写的地址。
- **定义**：维护接口目录和接口，支持五种请求体，以及响应示例。可以导入 OpenAPI 2、OpenAPI 3、Postman v2.1 和 HAR，导出 JSON 与 Excel。
- **场景**：展示已有场景列表。场景编排还没有做。
- **报告**：可以按类型筛选，当前没有报告数据。
- **Mock**：`/mock/{项目编码}/{路径}` 按优先级匹配规则，支持变量、延迟和异常模拟。未命中返回「没有匹配的 Mock 规则」。
- **系统设置**：用户、角色、项目、环境、变量、脚本和数据源。系统默认管理员不能删除或禁用，四个内置角色不能删除。

工作台可以查看 MySQL 和 Redis 状态。

## 服务

| 服务 | 端口 | 作用 |
| --- | --- | --- |
| frontend | 8080 | Vue 3 页面，反代 `/api` 和 `/mock` |
| backend | 8000 | FastAPI |
| mock | 8001 | 按规则匹配的 Mock 进程 |
| mysql | 3306 | MySQL 8.0 |
| redis | 6379 | Redis 7.0 |
| celery-worker | 无 | 消费 p0–p3 和 perf 队列 |
| celery-beat | 无 | 每分钟触发一次占位 ping |

Redis 分库：0 缓存与锁，1 Celery broker，2 任务结果，3 预留给执行状态。

## 常见问题

**健康检查里 MySQL 或 Redis 是 unavailable。** 看 `docker compose logs backend`。迁移会重试 10 次。如果端口 3306 或 6379 被本机占用，在 `.env` 里改 `MYSQL_PUBLISH_PORT` 和 `REDIS_PUBLISH_PORT`。容器内部主机名仍然是 `mysql` 和 `redis`。

**本机 Python 是 3.13。** 不要用它安装依赖或启动服务。镜像和 `backend/pyproject.toml` 都限制为 `>=3.12,<3.13`，进程启动时还会再检查一次。

**页面能开，工作台连不上接口。** 确认 backend 容器健康。前端容器通过服务名 `backend` 访问 8000，不要把浏览器直接指到容器内部地址。

**改了前端却还是旧页面。** 执行 `docker compose up -d --build --no-deps frontend`，再刷新浏览器。

**重复启动会不会重置密码。** 不会。管理员已经存在时，种子不会覆盖密码。

## 本地测试

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

前端类型检查和构建：

```bash
cd frontend
npm install
npm run build
```
