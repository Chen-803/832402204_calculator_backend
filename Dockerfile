# ---------------------------------------------------------------------------
# 前后端分离计算器 · 后端镜像
#
# 构建：docker build -t calculator-backend .
# 运行：docker run -p 8000:8000 -e DATABASE_URL="postgresql://..." calculator-backend
#
# 镜像里同时装好了 PostgreSQL 驱动与 gunicorn，
# 因此同一个镜像既能连 SQLite（不传 DATABASE_URL），也能连 PostgreSQL。
# 建表由应用启动时自动完成（CREATE TABLE IF NOT EXISTS，幂等）。
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CALC_HOST=0.0.0.0 \
    CALC_PORT=8000

WORKDIR /app

# 先装依赖，利用 Docker 层缓存：依赖没变时改代码不会重新装包
COPY requirements.txt requirements-postgres.txt requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

EXPOSE 8000

# 生产级 WSGI 服务器；平台若注入 $PORT 则优先使用
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile -"]
