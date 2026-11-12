# xuetang-api

学堂在线接口自动化测试平台。当前是阶段 0：可以一键启动，表由迁移创建，前端能打开工作台和接口测试的四个 Tab。

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

登录页在阶段 0 只检查用户名和密码非空，不向后端校验口令。进入工作台后可以看 MySQL 和 Redis 状态。接口测试顶部固定为「定义、调试、场景、报告」。

种子数据里的管理员是 `admin`，初始密码见 `.env.example` 的 `ADMIN_PASSWORD`。阶段 1 才会真正用这组账号登录，并要求首次改密。

开发默认值已经写在 `docker-compose.yml`。要覆盖时，把 `.env.example` 复制为 `.env` 后再改。

## 服务

| 服务 | 端口 | 作用 |
| --- | --- | --- |
| frontend | 8080 | Vue 3 页面，反代 `/api` 和 `/mock` |
| backend | 8000 | FastAPI |
| mock | 8001 | Mock 进程，规则匹配从阶段 2 开始 |
| mysql | 3306 | MySQL 8.0 |
| redis | 6379 | Redis 7.0 |
| celery-worker | 无 | 消费 p0–p3 和 perf 队列 |
| celery-beat | 无 | 每分钟触发一次占位 ping |

Redis 分库：0 缓存与锁，1 Celery broker，2 任务结果，3 预留给执行状态。

## 常见问题

**健康检查里 MySQL 或 Redis 是 unavailable。** 看 `docker compose logs backend`。迁移会重试 10 次。如果端口 3306 或 6379 被本机占用，在 `.env` 里改 `MYSQL_PUBLISH_PORT` 和 `REDIS_PUBLISH_PORT`。容器内部主机名仍然是 `mysql` 和 `redis`。

**本机 Python 是 3.13。** 不要用它安装依赖或启动服务。镜像和 `backend/pyproject.toml` 都限制为 `>=3.12,<3.13`，进程启动时还会再检查一次。

**页面能开，工作台连不上接口。** 确认 backend 容器健康。前端容器通过服务名 `backend` 访问 8000，不要把浏览器直接指到容器内部地址。

**重复启动会不会重置密码。** 不会。管理员已经存在时，种子不会覆盖密码。

## 阶段 0 范围

已完成的是骨架：编排、配置、日志、健康检查、65 张业务表的初始迁移、演示种子、四个空 Tab 和登录页框架。执行引擎只保留调度接口，提交任务会返回「阶段 4 启用」。Mock 路径会返回「阶段 2 启用」。

本地测试：

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
