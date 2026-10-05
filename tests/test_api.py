"""接口集成测试。

用 FastAPI 自带的 ``TestClient`` 打真实的 HTTP 请求（走完整的中间件、
异常处理器、路由），验证 ``docs/API_CONTRACT.md`` 里承诺的每一条行为。

覆盖作业四个核心功能的接口层面：

- Feature 1/2：``POST /api/calculate``（含全部错误分支）
- Feature 3：``GET /api/history``（含"换一个客户端连接仍能读到数据"的持久化验证）
- Feature 4：``DELETE /api/history/{id}``（含"数据库中确实被删除"的验证）
- 扩展功能：收藏、清空、统计、进制转换、单位换算
"""

from __future__ import annotations

import pytest

# ===================================================================== #
# 一、计算接口
# ===================================================================== #
class TestCalculateEndpoint:
    """``POST /api/calculate``"""

    def test_success_returns_201_and_envelope(self, client) -> None:
        """成功计算返回 201，并带上历史记录 ID。"""
        response = client.post("/api/calculate", json={"expression": "12+8"})
        assert response.status_code == 201

        body = response.json()
        assert body["success"] is True
        assert body["code"] == 0
        assert body["message"] == "OK"
        assert body["expression"] == "12+8"
        assert body["normalizedExpression"] == "12+8"
        assert body["result"] == 20
        assert body["resultText"] == "20"
        assert isinstance(body["historyId"], int)
        assert body["historyId"] > 0
        assert body["createdAt"]
        assert "elapsedMs" in body

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("12+8", "20"),
            ("12-8", "4"),
            ("12*8", "96"),
            ("12/8", "1.5"),
            ("1+2*3", "7"),
            ("(1+2)*3", "9"),
            ("10/2+7", "12"),
            ("8-3*2", "2"),
            ("-5+8", "3"),
            ("3*-2", "-6"),
            ("0.1+0.2", "0.3"),
            ("12×8", "96"),
        ],
    )
    def test_calculation_results(self, client, expression: str, expected: str) -> None:
        """作业要求的所有表达式类型都由后端算出正确结果。"""
        body = client.post("/api/calculate", json={"expression": expression}).json()
        assert body["success"] is True
        assert body["resultText"] == expected

    def test_angle_mode_is_passed_through(self, client) -> None:
        """角度制参数生效。"""
        deg = client.post(
            "/api/calculate", json={"expression": "sin(30)", "angleMode": "deg"}
        ).json()
        rad = client.post(
            "/api/calculate", json={"expression": "sin(30)", "angleMode": "rad"}
        ).json()
        assert deg["resultText"] == "0.5"
        assert rad["resultText"] == "-0.988031624093"

    @pytest.mark.parametrize(
        ("expression", "status", "code"),
        [
            ("1/0", 400, 40003),
            ("1+", 400, 40002),
            ("(1+2", 400, 40002),
            ("", 400, 40001),
            ("@", 400, 40009),
            ("foo(1)", 400, 40005),
            ("sqrt(-1)", 400, 40006),
        ],
    )
    def test_error_responses(self, client, expression: str, status: int, code: int) -> None:
        """错误响应同样是标准信封，且 message 可直接展示。"""
        response = client.post("/api/calculate", json={"expression": expression})
        assert response.status_code == status

        body = response.json()
        assert body["success"] is False
        assert body["code"] == code
        assert isinstance(body["message"], str)
        assert body["message"]

    def test_failed_calculation_is_not_saved(self, client) -> None:
        """失败的计算不写历史，避免污染历史列表。"""
        client.post("/api/calculate", json={"expression": "1/0"})
        client.post("/api/calculate", json={"expression": "1+"})
        history = client.get("/api/history").json()
        assert history["total"] == 0

    def test_missing_field_returns_422(self, client) -> None:
        """请求体缺字段 → 422，走统一信封。"""
        response = client.post("/api/calculate", json={})
        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["code"] == 42201

    def test_wrong_type_returns_422(self, client) -> None:
        response = client.post("/api/calculate", json={"expression": 123})
        assert response.status_code == 422
        assert response.json()["code"] == 42201


# ===================================================================== #
# 二、历史查询接口（Feature 3）
# ===================================================================== #
class TestHistoryEndpoint:
    """``GET /api/history``"""

    def test_empty_history(self, client) -> None:
        body = client.get("/api/history").json()
        assert body["success"] is True
        assert body["total"] == 0
        assert body["items"] == []
        assert body["totalPages"] == 0

    def test_records_are_returned_newest_first(self, client) -> None:
        for expression in ("1+1", "2+2", "3+3"):
            client.post("/api/calculate", json={"expression": expression})

        items = client.get("/api/history").json()["items"]
        assert [item["expression"] for item in items] == ["3+3", "2+2", "1+1"]
        assert all(item["resultText"] for item in items)
        assert all(item["createdAt"] for item in items)
        assert all(item["id"] for item in items)

    def test_pagination(self, client) -> None:
        for index in range(25):
            client.post("/api/calculate", json={"expression": f"{index}+1"})

        first = client.get("/api/history", params={"page": 1, "pageSize": 10}).json()
        assert first["total"] == 25
        assert first["page"] == 1
        assert first["pageSize"] == 10
        assert first["totalPages"] == 3
        assert len(first["items"]) == 10

        last = client.get("/api/history", params={"page": 3, "pageSize": 10}).json()
        assert len(last["items"]) == 5

    def test_page_out_of_range_is_clamped(self, client) -> None:
        """页码超出范围时夹到最后一页，而不是返回空列表。"""
        for index in range(5):
            client.post("/api/calculate", json={"expression": f"{index}+1"})
        body = client.get("/api/history", params={"page": 99, "pageSize": 10}).json()
        assert body["page"] == 1
        assert len(body["items"]) == 5

    def test_search_by_keyword(self, client) -> None:
        for expression in ("1+1", "2+2", "100*3", "7-4"):
            client.post("/api/calculate", json={"expression": expression})

        body = client.get("/api/history", params={"keyword": "100"}).json()
        assert body["total"] == 1
        assert body["items"][0]["expression"] == "100*3"

    def test_search_by_result(self, client) -> None:
        client.post("/api/calculate", json={"expression": "6*7"})
        client.post("/api/calculate", json={"expression": "1+1"})
        body = client.get("/api/history", params={"keyword": "42"}).json()
        assert body["total"] == 1
        assert body["items"][0]["expression"] == "6*7"

    def test_search_escapes_wildcards(self, client) -> None:
        """搜索 ``%`` 不应匹配到所有记录（LIKE 通配符必须转义）。"""
        for expression in ("1+1", "2+2"):
            client.post("/api/calculate", json={"expression": expression})
        body = client.get("/api/history", params={"keyword": "%"}).json()
        assert body["total"] == 0

    def test_order_ascending(self, client) -> None:
        for expression in ("1+1", "2+2"):
            client.post("/api/calculate", json={"expression": expression})
        items = client.get("/api/history", params={"order": "asc"}).json()["items"]
        assert [item["expression"] for item in items] == ["1+1", "2+2"]

    def test_history_survives_new_client_session(self, client) -> None:
        """**作业关键要求**：历史存在后端数据库里，换一个客户端连接依然能读到。

        这里模拟"刷新/重开前端"：先用一个客户端写数据，
        再用一个全新的 ``TestClient``（相当于新的 HTTP 连接）读取。
        """
        from fastapi.testclient import TestClient

        from app.main import app

        client.post("/api/calculate", json={"expression": "(2+3)*4"})

        with TestClient(app) as second_client:
            body = second_client.get("/api/history").json()
            assert body["total"] == 1
            assert body["items"][0]["expression"] == "(2+3)*4"
            assert body["items"][0]["resultText"] == "20"

    def test_history_is_read_from_database_not_memory(self, client, test_db_path) -> None:
        """直接查数据库文件，确认数据真的落盘了。"""
        client.post("/api/calculate", json={"expression": "5*8"})

        import sqlite3

        connection = sqlite3.connect(str(test_db_path))
        try:
            row = connection.execute(
                "SELECT expression, result FROM calculation_history"
            ).fetchone()
        finally:
            connection.close()

        assert row is not None
        assert row[0] == "5*8"
        assert row[1] == "40"


# ===================================================================== #
# 三、删除接口（Feature 4）
# ===================================================================== #
class TestDeleteEndpoint:
    """``DELETE /api/history/{id}``"""

    def test_delete_specified_record(self, client, test_db_path) -> None:
        first = client.post("/api/calculate", json={"expression": "1+1"}).json()
        second = client.post("/api/calculate", json={"expression": "2+2"}).json()

        response = client.delete(f"/api/history/{first['historyId']}")
        assert response.status_code == 200

        body = response.json()
        assert body["success"] is True
        assert body["deleted"] == 1
        assert body["id"] == first["historyId"]

        # API 层面确认
        remaining = client.get("/api/history").json()
        assert remaining["total"] == 1
        assert remaining["items"][0]["id"] == second["historyId"]

        # 数据库层面确认（作业要求"记录确实被删除"）
        import sqlite3

        connection = sqlite3.connect(str(test_db_path))
        try:
            rows = connection.execute("SELECT id FROM calculation_history").fetchall()
        finally:
            connection.close()
        assert [row[0] for row in rows] == [second["historyId"]]

    def test_delete_missing_record_returns_404(self, client) -> None:
        response = client.delete("/api/history/999999")
        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["code"] == 40401
        assert "999999" in body["message"]

    def test_delete_twice_returns_404(self, client) -> None:
        created = client.post("/api/calculate", json={"expression": "9-4"}).json()
        assert client.delete(f"/api/history/{created['historyId']}").status_code == 200
        assert client.delete(f"/api/history/{created['historyId']}").status_code == 404

    def test_clear_all_history(self, client, test_db_path) -> None:
        for index in range(4):
            client.post("/api/calculate", json={"expression": f"{index}+1"})

        response = client.delete("/api/history")
        assert response.status_code == 200
        assert response.json()["deleted"] == 4
        assert client.get("/api/history").json()["total"] == 0

        import sqlite3

        connection = sqlite3.connect(str(test_db_path))
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM calculation_history"
            ).fetchone()[0]
        finally:
            connection.close()
        assert count == 0


# ===================================================================== #
# 四、收藏（扩展功能）
# ===================================================================== #
class TestFavoriteEndpoint:
    """``PATCH /api/history/{id}/favorite``"""

    def test_set_favorite_explicitly(self, client) -> None:
        created = client.post("/api/calculate", json={"expression": "8*8"}).json()
        record_id = created["historyId"]

        body = client.patch(
            f"/api/history/{record_id}/favorite", json={"favorite": True}
        ).json()
        assert body["favorite"] is True

        items = client.get("/api/history").json()["items"]
        assert items[0]["favorite"] is True

    def test_toggle_favorite(self, client) -> None:
        created = client.post("/api/calculate", json={"expression": "8*8"}).json()
        record_id = created["historyId"]

        first = client.patch(f"/api/history/{record_id}/favorite", json={}).json()
        assert first["favorite"] is True
        second = client.patch(f"/api/history/{record_id}/favorite", json={}).json()
        assert second["favorite"] is False

    def test_filter_only_favorite(self, client) -> None:
        a = client.post("/api/calculate", json={"expression": "1+1"}).json()
        client.post("/api/calculate", json={"expression": "2+2"})
        client.patch(f"/api/history/{a['historyId']}/favorite", json={"favorite": True})

        body = client.get("/api/history", params={"onlyFavorite": True}).json()
        assert body["total"] == 1
        assert body["items"][0]["expression"] == "1+1"

    def test_favorite_missing_record_returns_404(self, client) -> None:
        response = client.patch("/api/history/999999/favorite", json={"favorite": True})
        assert response.status_code == 404


# ===================================================================== #
# 五、统计（扩展功能）
# ===================================================================== #
class TestStatsEndpoint:
    """``GET /api/stats``"""

    def test_stats_shape(self, client) -> None:
        for expression in ("1+2", "3*4", "5-1", "8/2", "1+2"):
            client.post("/api/calculate", json={"expression": expression})

        body = client.get("/api/stats").json()
        assert body["success"] is True
        assert body["totalCount"] == 5
        assert body["todayCount"] == 5
        assert body["favoriteCount"] == 0
        assert len(body["recentSevenDays"]) == 7
        assert body["topExpressions"][0] == {"expression": "1+2", "count": 2}

        operators = {item["operator"] for item in body["operatorUsage"]}
        assert {"+", "*", "-", "/"} <= operators

    def test_unary_minus_is_not_counted_as_subtraction(self, client) -> None:
        """``3*-2`` 里的 ``-`` 是一元负号，不应被统计成减法。

        这正是"复用 AST 而不是数字符"的价值所在。
        """
        client.post("/api/calculate", json={"expression": "3*-2"})
        body = client.get("/api/stats").json()
        operators = {item["operator"]: item["count"] for item in body["operatorUsage"]}
        assert operators.get("*") == 1
        assert "-" not in operators


# ===================================================================== #
# 六、转换（扩展功能）
# ===================================================================== #
class TestConversionEndpoints:
    """``/api/convert/*``"""

    @pytest.mark.parametrize(
        ("value", "from_base", "to_base", "expected"),
        [
            ("255", 10, 16, "FF"),
            ("FF", 16, 10, "255"),
            ("1010", 2, 10, "10"),
            ("255", 10, 2, "11111111"),
            ("777", 8, 16, "1FF"),
            ("-255", 10, 16, "-FF"),
            ("1F.8", 16, 10, "31.5"),
            ("z", 36, 10, "35"),
        ],
    )
    def test_base_conversion(self, client, value, from_base, to_base, expected) -> None:
        body = client.post(
            "/api/convert/base",
            json={"value": value, "fromBase": from_base, "toBase": to_base},
        ).json()
        assert body["success"] is True
        assert body["output"] == expected

    def test_invalid_char_for_base(self, client) -> None:
        response = client.post(
            "/api/convert/base", json={"value": "2", "fromBase": 2, "toBase": 10}
        )
        assert response.status_code == 400
        assert response.json()["code"] == 40007

    def test_invalid_base_number(self, client) -> None:
        response = client.post(
            "/api/convert/base", json={"value": "1", "fromBase": 1, "toBase": 10}
        )
        assert response.status_code == 422

    def test_list_units(self, client) -> None:
        body = client.get("/api/convert/units").json()
        assert body["success"] is True
        keys = {category["key"] for category in body["categories"]}
        assert {"length", "mass", "temperature", "data"} <= keys

    @pytest.mark.parametrize(
        ("category", "from_unit", "to_unit", "value", "expected"),
        [
            ("length", "m", "km", 1000, "1"),
            ("length", "km", "m", 1, "1000"),
            ("length", "in", "cm", 1, "2.54"),
            ("mass", "kg", "g", 1, "1000"),
            ("mass", "jin", "g", 1, "500"),
            ("time", "h", "min", 1, "60"),
            ("data", "KB", "B", 1, "1024"),
            ("temperature", "c", "f", 100, "212"),
            ("temperature", "f", "c", 32, "0"),
            ("temperature", "c", "k", 0, "273.15"),
            ("speed", "km/h", "m/s", 36, "10"),
        ],
    )
    def test_unit_conversion(self, client, category, from_unit, to_unit, value, expected) -> None:
        body = client.post(
            "/api/convert/unit",
            json={
                "category": category, "from": from_unit, "to": to_unit, "value": value,
            },
        ).json()
        assert body["success"] is True
        assert body["outputText"] == expected

    def test_unknown_unit_returns_400(self, client) -> None:
        response = client.post(
            "/api/convert/unit",
            json={"category": "length", "from": "m", "to": "lightyear", "value": 1},
        )
        assert response.status_code == 400
        assert response.json()["code"] == 40008

    def test_unknown_category_returns_400(self, client) -> None:
        response = client.post(
            "/api/convert/unit",
            json={"category": "nope", "from": "m", "to": "km", "value": 1},
        )
        assert response.status_code == 400
        assert response.json()["code"] == 40008


# ===================================================================== #
# 七、健康检查与通用行为
# ===================================================================== #
class TestGeneralBehaviour:
    """健康检查、CORS、未知路由。"""

    def test_health(self, client) -> None:
        body = client.get("/api/health").json()
        assert body["success"] is True
        assert body["database"] == "ok"
        assert body["version"]

    def test_root_endpoint(self, client) -> None:
        body = client.get("/").json()
        assert body["success"] is True
        assert body["apiPrefix"] == "/api"

    def test_unknown_route_uses_envelope(self, client) -> None:
        """未知路由也返回统一信封，而不是 FastAPI 默认的 ``{"detail": ...}``。"""
        response = client.get("/api/does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert "code" in body and "message" in body

    def test_cors_headers_present(self, client) -> None:
        """CORS 中间件生效，浏览器才不会拦下跨域请求。"""
        response = client.get(
            "/api/health", headers={"Origin": "http://localhost:5173"}
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_openapi_schema_is_available(self, client) -> None:
        """自动生成的接口文档可用，方便助教直接调试。"""
        schema = client.get("/openapi.json").json()
        assert "/api/calculate" in schema["paths"]
        assert "/api/history" in schema["paths"]
        assert "/api/history/{record_id}" in schema["paths"]
