"""计算历史服务：查询、分页、搜索、删除、收藏。

这一层负责三件事：

1. **参数兜底与归一化**：页码非法、每页条数越界在这里被夹到合理区间，
   而不是抛错——查询类接口容错比严格更有用；
2. **组装分页元信息**：``total`` / ``page`` / ``pageSize`` / ``totalPages``
   由后端算好，前端不需要自己推导（避免前后端各算一遍算法不一致）；
3. **把"记录不存在"翻译成业务异常**，由异常处理器统一转 404。
"""

from __future__ import annotations

from math import ceil
from typing import Any

from ..common.exceptions import NotFoundError
from ..config import settings
from ..model.entities import HistoryRecord
from ..repository.history_repository import HistoryRepository


class HistoryService:
    """计算历史业务服务。"""

    def __init__(self, repository: HistoryRepository | None = None) -> None:
        self._repository = repository or HistoryRepository()

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def list_history(
        self,
        *,
        keyword: str = "",
        page: int = 1,
        page_size: int = 10,
        only_favorite: bool = False,
        order: str = "desc",
    ) -> dict[str, Any]:
        """分页查询历史。

        :returns: 可直接展开进 API 响应的字典：
            ``{total, page, pageSize, totalPages, items}``
        """
        page = max(int(page), 1)
        page_size = max(1, min(int(page_size), settings.max_page_size))
        keyword = (keyword or "").strip()
        order = order if order.lower() in ("asc", "desc") else "desc"

        total = self._repository.count(keyword=keyword, only_favorite=only_favorite)
        total_pages = max(ceil(total / page_size), 1) if total else 0

        # 页码越界时夹到最后一页，避免前端翻过头看到空列表却不知道原因
        if total_pages and page > total_pages:
            page = total_pages

        records = self._repository.find_page(
            keyword=keyword,
            page=page,
            page_size=page_size,
            only_favorite=only_favorite,
            order=order,
        )

        return {
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": total_pages,
            "items": [record.to_dict() for record in records],
        }

    # ------------------------------------------------------------------ #
    # 删除
    # ------------------------------------------------------------------ #
    def delete_history(self, record_id: int) -> dict[str, Any]:
        """删除指定历史记录。

        :raises NotFoundError: 记录不存在（HTTP 404）
        """
        deleted = self._repository.delete_by_id(record_id)
        if deleted == 0:
            raise NotFoundError(f"历史记录不存在：id={record_id}")
        return {"deleted": deleted, "id": record_id}

    def clear_history(self) -> dict[str, Any]:
        """清空全部历史（扩展功能）。

        :returns: ``{"deleted": N}``；N 可能为 0（本来就空）
        """
        return {"deleted": self._repository.delete_all()}

    # ------------------------------------------------------------------ #
    # 收藏（扩展功能）
    # ------------------------------------------------------------------ #
    def set_favorite(self, record_id: int, favorite: bool | None) -> dict[str, Any]:
        """设置或切换收藏状态。

        :raises NotFoundError: 记录不存在
        """
        record = self._repository.set_favorite(record_id, favorite)
        if record is None:
            raise NotFoundError(f"历史记录不存在：id={record_id}")
        return {"id": record.id, "favorite": record.favorite}

    def get_record(self, record_id: int) -> HistoryRecord:
        """按 ID 取实体。

        :raises NotFoundError: 记录不存在
        """
        record = self._repository.find_by_id(record_id)
        if record is None:
            raise NotFoundError(f"历史记录不存在：id={record_id}")
        return record
