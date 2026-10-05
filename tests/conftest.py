"""pytest 全局配置与公共夹具。

**关键点：必须在导入任何 app 模块之前设置 ``CALCULATOR_DB_PATH``。**

``app.config.settings`` 是模块级单例，在第一次 import 时就读取环境变量并固化。
pytest 会先加载 ``conftest.py`` 再加载测试模块，因此在这里设置环境变量，
就能保证所有测试用的是一个**独立的临时数据库**，不会碰开发用的
``data/calculator.db``。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# 1) 在导入 app 之前把数据库指向测试目录
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent
_TMP_DIR = _TESTS_DIR / ".tmp"
_TMP_DIR.mkdir(parents=True, exist_ok=True)
_TEST_DB = _TMP_DIR / "test_calculator.db"

os.environ["CALCULATOR_DB_PATH"] = str(_TEST_DB)
os.environ.setdefault("CALCULATOR_LOG_LEVEL", "WARNING")

# 确保每次测试会话从一个干净数据库开始
for suffix in ("", "-wal", "-shm"):
    stale = Path(str(_TEST_DB) + suffix)
    if stale.exists():
        stale.unlink()

# ---------------------------------------------------------------------------
# 2) 现在才可以安全地导入应用
# ---------------------------------------------------------------------------
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.repository.database import init_database  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    """整个测试会话开始前建库，结束后清理临时文件。"""
    init_database(_TEST_DB)
    yield
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture()
def client():
    """FastAPI 测试客户端。

    直接复用全局 ``app.main:app``，测试的是真实的应用装配
    （中间件、异常处理器、路由前缀全都包含在内），而不是一个"测试专用"的简化应用。
    """
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_history():
    """每个测试用例前清空历史表，保证用例之间互不影响。"""
    from app.repository.database import get_connection

    with get_connection(_TEST_DB) as conn:
        conn.execute("DELETE FROM calculation_history")
    yield


@pytest.fixture()
def test_db_path() -> Path:
    """测试数据库路径。"""
    return _TEST_DB
