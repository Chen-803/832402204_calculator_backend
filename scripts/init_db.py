"""数据库初始化脚本。

用法::

    python scripts/init_db.py                 # 按配置初始化（未设 DATABASE_URL 时为 SQLite）
    python scripts/init_db.py --db other.db   # 指定 SQLite 数据库文件
    python scripts/init_db.py --reset         # 先删除旧库再重建（仅 SQLite，谨慎！）

    设置了 DATABASE_URL 环境变量时，会自动改为初始化 PostgreSQL
    （执行 sql/schema_postgres.sql）。

该脚本是幂等的：重复执行不会丢失已有数据（``--reset`` 除外）。
"""

import argparse
import sys
from pathlib import Path

# 允许直接以脚本方式运行：把项目根目录加入模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DIALECT_SQLITE, load_config  # noqa: E402
from src.model.database import init_database, schema_path_for  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="初始化计算器后端数据库")
    parser.add_argument("--db", default=None, help="数据库文件路径（默认取配置）")
    parser.add_argument("--reset", action="store_true", help="删除已有数据库文件后重建")
    return parser.parse_args()


def main() -> int:
    """执行初始化。"""
    arguments = parse_arguments()
    config = load_config()
    dialect = config.dialect
    database_path = arguments.db or config.database_path
    schema_file = schema_path_for(dialect)

    if arguments.reset:
        if dialect != DIALECT_SQLITE:
            print("PostgreSQL 模式不支持 --reset（请到云平台控制台清空表）")
            return 1
        target = Path(database_path)
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{target}{suffix}")
            if candidate.exists():
                candidate.unlink()
                print(f"已删除旧文件：{candidate}")

    if not schema_file.exists():
        print(f"找不到建表脚本：{schema_file}")
        return 1

    if arguments.db:
        init_database(database_path=arguments.db)
    else:
        init_database()

    print("=" * 60)
    print("数据库初始化完成")
    print(f"  数据库类型：{dialect}")
    print(f"  连接目标  ：{config.database_uri}")
    print(f"  建表脚本  ：{schema_file}")
    print("  数据表    ：calculation_history(id, expression, result, created_at, is_favorite)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
