"""HTTP 接口集成测试。

使用 Flask 自带的测试客户端，真实地走完
「HTTP 请求 -> 控制器 -> 服务 -> 数据库」整条链路。

数据库有两种跑法：

* **默认（SQLite）**：每个用例创建一个独立的临时 SQLite 文件，互不干扰::

      python -m unittest discover -s tests -v

* **PostgreSQL**：设置 ``CALC_TEST_DATABASE_URL`` 后，同一套用例会改跑在
  PostgreSQL 上（用于验证"永久部署"所用的数据库路径）::

      set CALC_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/calculator
      python -m unittest discover -s tests -v

  此时用一个共用的测试库，每条用例开始前清空 ``calculation_history`` 表。
"""

import json
import os
import shutil
import sys
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import create_app  # noqa: E402
from src.config import Config  # noqa: E402

#: 测试用的临时目录放在项目内部，避免依赖操作系统临时目录的写权限。
TEMPORARY_ROOT = PROJECT_ROOT / ".tmp-tests"

#: 设置该环境变量后，整套接口测试改为跑在 PostgreSQL 上。
POSTGRES_TEST_URL = os.environ.get("CALC_TEST_DATABASE_URL") or None

TABLE_NAME = "calculation_history"


class ApiTestCase(unittest.TestCase):
    """所有接口测试的公共基类。

    默认每个测试用独立的临时 SQLite 数据库；
    配置了 ``CALC_TEST_DATABASE_URL`` 时改用共享的 PostgreSQL 测试库。
    """

    def setUp(self) -> None:
        if POSTGRES_TEST_URL:
            self.temp_directory = None
            self.database_path = None
            self.config = Config(database_url=POSTGRES_TEST_URL, debug=False)
            self.app = create_app(self.config)
            self.client = self.app.test_client()
            self._truncate_table()
        else:
            TEMPORARY_ROOT.mkdir(parents=True, exist_ok=True)
            self.temp_directory = TEMPORARY_ROOT / f"case-{uuid.uuid4().hex[:8]}"
            self.temp_directory.mkdir(parents=True, exist_ok=True)
            self.database_path = str(self.temp_directory / "test.db")
            self.config = Config(database_path=self.database_path, debug=False)
            self.app = create_app(self.config)
            self.client = self.app.test_client()

    def tearDown(self) -> None:
        if self.temp_directory is not None:
            shutil.rmtree(str(self.temp_directory), ignore_errors=True)
        else:
            self._truncate_table()

    def _truncate_table(self) -> None:
        """清空共享测试库中的历史表，保证用例之间互不影响。"""
        from src.model.database import create_connection

        connection = create_connection(database_url=POSTGRES_TEST_URL)
        try:
            connection.execute(f"DELETE FROM {TABLE_NAME}")
            connection.commit()
        finally:
            connection.close()

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    def post_json(self, url: str, payload: dict):
        """发送 JSON POST 请求。"""
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )

    def calculate(self, expression: str, persist: bool = True):
        """调用计算接口并返回响应。"""
        return self.post_json("/api/calculate", {"expression": expression, "persist": persist})


class HealthAndMetaTests(ApiTestCase):
    """健康检查与元数据接口。"""

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["status"], "ok")

    def test_health_reports_active_database(self):
        """健康检查要如实报告当前连的是哪种数据库（便于部署后核对）。"""
        body = self.client.get("/api/health").get_json()
        expected = "postgresql" if POSTGRES_TEST_URL else "sqlite"
        self.assertEqual(body["data"]["database"], expected)

    def test_service_index(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        endpoints = " ".join(response.get_json()["data"]["endpoints"])
        self.assertIn("/api/calculate", endpoints)
        self.assertIn("/api/history", endpoints)

    def test_meta_functions(self):
        body = self.client.get("/api/meta/functions").get_json()
        names = {item["name"] for item in body["data"]["functions"]}
        self.assertIn("sqrt", names)
        self.assertIn("log", names)
        self.assertEqual({item["name"] for item in body["data"]["constants"]}, {"pi", "e"})

    def test_cors_headers_are_present(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_options_preflight(self):
        """浏览器跨域预检请求应当被接受，并带回跨域响应头。"""
        response = self.client.options("/api/calculate")
        self.assertIn(response.status_code, (200, 204))
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("POST", response.headers["Access-Control-Allow-Methods"])


class CalculateApiTests(ApiTestCase):
    """计算接口。"""

    def test_basic_calculation_returns_result_from_backend(self):
        response = self.calculate("12+8")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["expression"], "12+8")
        self.assertEqual(body["result"], 20)
        self.assertEqual(body["display_result"], "20")
        self.assertIsNotNone(body["record"])
        self.assertEqual(body["record"]["result"], "20")
        # 扁平响应不应再额外携带 data 字段
        self.assertNotIn("data", body)

    def test_compound_expression(self):
        self.assertEqual(self.calculate("(1+2)*3").get_json()["result"], 9)

    def test_preview_does_not_persist(self):
        body = self.calculate("1+2", persist=False).get_json()
        self.assertEqual(body["result"], 3)
        self.assertIsNone(body["record"])
        history = self.client.get("/api/history").get_json()["data"]
        self.assertEqual(history["total"], 0)

    def test_invalid_expression_returns_400(self):
        response = self.calculate("1+")
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error_code"], "INVALID_EXPRESSION")
        # 错误响应回带原始表达式，便于前端回显
        self.assertEqual(body["expression"], "1+")

    def test_division_by_zero_returns_400(self):
        response = self.calculate("1/0")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error_code"], "DIVISION_BY_ZERO")

    def test_empty_expression_returns_400(self):
        self.assertEqual(self.calculate("").get_json()["error_code"], "EMPTY_EXPRESSION")

    def test_expression_field_is_required(self):
        response = self.post_json("/api/calculate", {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error_code"], "VALIDATION_ERROR")

    def test_expression_must_be_string(self):
        response = self.post_json("/api/calculate", {"expression": 123})
        self.assertEqual(response.status_code, 400)

    def test_broken_json_body_returns_400(self):
        response = self.client.post(
            "/api/calculate", data="{not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_failed_calculation_is_not_stored(self):
        self.calculate("1/0")
        self.assertEqual(self.client.get("/api/history").get_json()["data"]["total"], 0)


class HistoryApiTests(ApiTestCase):
    """历史记录接口：查询、持久化、删除、清空、收藏、统计。"""

    def seed(self, expressions):
        """批量写入历史记录。"""
        for expression in expressions:
            self.calculate(expression)

    def test_history_is_returned_in_descending_order(self):
        self.seed(["1+1", "2+2", "3+3"])
        items = self.client.get("/api/history").get_json()["data"]["items"]
        self.assertEqual([item["expression"] for item in items], ["3+3", "2+2", "1+1"])

    def test_history_survives_application_restart(self):
        """重启应用后历史仍在：证明数据来自数据库而不是进程内存。"""
        self.seed(["6*7"])
        restarted_app = create_app(self.config)
        with restarted_app.test_client() as client:
            items = client.get("/api/history").get_json()["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["result"], "42")

    def test_pagination(self):
        self.seed([f"{index}+0" for index in range(1, 13)])
        page_one = self.client.get("/api/history?page=1&page_size=5").get_json()["data"]
        self.assertEqual(page_one["total"], 12)
        self.assertEqual(page_one["total_pages"], 3)
        self.assertEqual(len(page_one["items"]), 5)

    def test_pagination_parameter_validation(self):
        response = self.client.get("/api/history?page=0")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error_code"], "VALIDATION_ERROR")

    def test_keyword_search(self):
        self.seed(["1+2", "7*6"])
        data = self.client.get("/api/history?keyword=7").get_json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["expression"], "7*6")

    def test_date_filter_validation(self):
        response = self.client.get("/api/history?start_date=2026-13-01")
        self.assertEqual(response.status_code, 400)

    def test_get_single_record(self):
        record_id = self.calculate("9-4").get_json()["record"]["id"]
        response = self.client.get(f"/api/history/{record_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["result"], "5")

    def test_delete_specific_record(self):
        first = self.calculate("1+1").get_json()["record"]["id"]
        second = self.calculate("2+2").get_json()["record"]["id"]

        response = self.client.delete(f"/api/history/{first}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["deleted_id"], first)

        remaining = self.client.get("/api/history").get_json()["data"]
        self.assertEqual(remaining["total"], 1)
        self.assertEqual(remaining["items"][0]["id"], second)
        self.assertEqual(self.client.get(f"/api/history/{first}").status_code, 404)

    def test_delete_missing_record_returns_404(self):
        response = self.client.delete("/api/history/999999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error_code"], "RECORD_NOT_FOUND")

    def test_clear_all_history(self):
        self.seed(["1+1", "2+2", "3+3"])
        response = self.client.delete("/api/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["deleted"], 3)
        self.assertEqual(self.client.get("/api/history").get_json()["data"]["total"], 0)

    def test_favorite_toggle_and_filter(self):
        record_id = self.calculate("5*5").get_json()["record"]["id"]

        response = self.client.patch(
            f"/api/history/{record_id}/favorite",
            data=json.dumps({"is_favorite": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["is_favorite"], 1)

        filtered = self.client.get("/api/history?favorite_only=true").get_json()["data"]
        self.assertEqual(filtered["total"], 1)

        toggled = self.client.patch(f"/api/history/{record_id}/favorite")
        self.assertEqual(toggled.get_json()["data"]["is_favorite"], 0)

    def test_favorite_missing_record_returns_404(self):
        self.assertEqual(self.client.patch("/api/history/888888/favorite").status_code, 404)

    def test_statistics(self):
        self.seed(["1+2", "3*4", "8-5"])
        stats = self.client.get("/api/history/statistics").get_json()["data"]
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["today"], 3)
        self.assertIn(stats["most_used_operator"], {"+", "-", "*", "/"})
        self.assertEqual(stats["operator_total"], 3)
        self.assertIsNotNone(stats["last_calculation_at"])


class ErrorFormatTests(ApiTestCase):
    """统一错误格式。"""

    def test_unknown_route_returns_json_404(self):
        response = self.client.get("/api/not-exist")
        self.assertEqual(response.status_code, 404)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error_code"], "NOT_FOUND")

    def test_method_not_allowed(self):
        response = self.client.get("/api/calculate")
        self.assertEqual(response.status_code, 405)


if __name__ == "__main__":
    unittest.main(verbosity=2)
