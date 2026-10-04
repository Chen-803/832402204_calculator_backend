-- ---------------------------------------------------------------------------
-- 计算器系统数据库表结构（SQLite）
-- 作者：832402204 陈俊洁
--
-- 设计说明：
--   1. 作业要求历史记录至少包含「表达式 / 结果 / 计算时间」三个字段，
--      这里再补一个 ``is_favorite`` 用于"收藏"扩展功能；
--   2. ``result`` 用 TEXT 存储而不是 REAL：计算结果在业务层用高精度
--      Decimal 表示，存成 TEXT 可以原样保留精度，避免浮点入库丢精度；
--   3. ``created_at`` 统一存 ``YYYY-MM-DD HH:MM:SS`` 文本，
--      SQLite 下该格式可以直接用字符串比较做范围筛选与排序；
--   4. 为常用的排序字段与筛选字段建立索引，保证分页与检索的效率。
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS calculation_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,          -- 记录 ID（主键，自增）
    expression  TEXT    NOT NULL,                           -- 归一化后的计算表达式
    result      TEXT    NOT NULL,                           -- 计算结果（高精度文本）
    created_at  TEXT    NOT NULL,                           -- 计算时间 YYYY-MM-DD HH:MM:SS
    is_favorite INTEGER NOT NULL DEFAULT 0                  -- 是否收藏：0 否 / 1 是
);

-- 历史列表默认按时间倒序分页，因此为 created_at 建索引。
CREATE INDEX IF NOT EXISTS idx_history_created_at
    ON calculation_history (created_at DESC);

-- 「仅看收藏」筛选依赖该字段。
CREATE INDEX IF NOT EXISTS idx_history_is_favorite
    ON calculation_history (is_favorite);
