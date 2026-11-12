#!/bin/sh
# @File    : entrypoint.sh
# @Desc    : 容器入口。先确认 Python 3.12，再等待依赖、迁移、种子，最后按角色启动进程
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化 web、worker、beat、mock 四种启动角色

set -eu

python - <<'PY'
import sys
version = sys.version_info
if (version.major, version.minor) != (3, 12):
    raise SystemExit(
        f"xuetang-api 只允许 Python 3.12，当前是 {version.major}.{version.minor}，禁止 3.13"
    )
PY

role="${1:-web}"

python -m app.db.wait_for_deps

attempt=0
until alembic upgrade head; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 10 ]; then
    echo "alembic upgrade head 连续失败，停止启动"
    exit 1
  fi
  echo "迁移未完成，3 秒后重试（第 ${attempt} 次）"
  sleep 3
done

python -m app.seed

case "$role" in
  web)
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    # 进程并发保持 2。阶段 4 的线程池在进程内部，默认 10，不靠这里堆进程
    exec celery -A app.workers.celery_app.celery_app worker -Q p0,p1,p2,p3,perf --loglevel=info --concurrency=2
    ;;
  beat)
    exec celery -A app.workers.celery_app.celery_app beat --loglevel=info
    ;;
  mock)
    exec uvicorn app.mock_server.main:app --host 0.0.0.0 --port 8001
    ;;
  *)
    echo "未知角色: $role"
    exit 1
    ;;
esac
