#!/usr/bin/env python3
"""Migrate GankAIGC data from the local SQLite database to PostgreSQL."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List

from sqlalchemy import Integer, create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import Column, Table

from app.database import Base, normalize_database_url
from app.models import models  # noqa: F401 - register SQLAlchemy models


BACKEND_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = BACKEND_DIR.parent
DEFAULT_SQLITE_DB = PACKAGE_DIR / "ai_polish.db"


def _sqlite_connect_args(database_url: str) -> Dict[str, bool]:
    return {"check_same_thread": False} if database_url.startswith("sqlite") else {}


def create_database_engine(database_url: str) -> Engine:
    normalized_url = normalize_database_url(database_url)
    return create_engine(normalized_url, connect_args=_sqlite_connect_args(normalized_url))


def sqlite_source_url(source: str | None = None) -> str:
    if not source:
        return f"sqlite:///{DEFAULT_SQLITE_DB.as_posix()}"
    if source.startswith("sqlite:"):
        return source
    return f"sqlite:///{Path(source).resolve().as_posix()}"


def migration_tables() -> List[Table]:
    return list(Base.metadata.sorted_tables)


def migration_table_names() -> List[str]:
    return [table.name for table in migration_tables()]


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _integer_primary_key(table: Table) -> Column | None:
    primary_keys = list(table.primary_key.columns)
    if len(primary_keys) != 1:
        return None
    primary_key = primary_keys[0]
    if not isinstance(primary_key.type, Integer):
        return None
    return primary_key


def build_postgres_sequence_reset_sql(table: Table) -> str:
    primary_key = _integer_primary_key(table)
    if primary_key is None:
        return ""

    table_name = _sql_literal(table.name)
    column_name = _sql_literal(primary_key.name)
    quoted_table = _quote_identifier(table.name)
    quoted_column = _quote_identifier(primary_key.name)
    sequence_expr = f"pg_get_serial_sequence({table_name}, {column_name})"

    return (
        "SELECT CASE "
        f"WHEN {sequence_expr} IS NOT NULL THEN "
        f"setval({sequence_expr}, "
        f"COALESCE((SELECT MAX({quoted_column}) FROM {quoted_table}), 1), "
        f"(SELECT COUNT(*) FROM {quoted_table}) > 0"
        ") ELSE NULL END"
    )


def _existing_table_columns(engine: Engine) -> Dict[str, set[str]]:
    inspector = inspect(engine)
    return {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in inspector.get_table_names()
    }


def _table_counts(engine: Engine) -> Dict[str, int]:
    existing_tables = set(inspect(engine).get_table_names())
    counts: Dict[str, int] = {}
    with engine.connect() as conn:
        for table in migration_tables():
            if table.name not in existing_tables:
                continue
            counts[table.name] = conn.execute(select(func.count()).select_from(table)).scalar_one()
    return counts


def _non_empty_tables(engine: Engine) -> Dict[str, int]:
    return {table: count for table, count in _table_counts(engine).items() if count > 0}


def _copy_table(source_conn, target_conn, table: Table, source_columns: Iterable[str]) -> int:
    copy_column_names = [column.name for column in table.columns if column.name in source_columns]
    if not copy_column_names:
        return 0

    select_columns = [table.c[column_name] for column_name in copy_column_names]
    rows = source_conn.execute(select(*select_columns)).mappings().all()
    if not rows:
        return 0

    target_conn.execute(table.insert(), [dict(row) for row in rows])
    return len(rows)


def _reset_postgres_sequences(target_conn) -> None:
    for table in migration_tables():
        reset_sql = build_postgres_sequence_reset_sql(table)
        if reset_sql:
            target_conn.execute(text(reset_sql))


def migrate_sqlite_to_target(
    source_url: str,
    target_url: str,
    *,
    replace_target: bool = False,
    allow_sqlite_target: bool = False,
) -> Dict[str, int]:
    source_engine = create_database_engine(sqlite_source_url(source_url))
    target_engine = create_database_engine(target_url)

    try:
        if source_engine.dialect.name != "sqlite":
            raise ValueError("源数据库必须是 SQLite")
        if target_engine.dialect.name == "sqlite" and not allow_sqlite_target:
            raise ValueError("目标数据库必须是 PostgreSQL")
        if target_engine.dialect.name not in {"postgresql", "sqlite"}:
            raise ValueError("目标数据库必须是 PostgreSQL")

        if replace_target:
            Base.metadata.drop_all(bind=target_engine)
        Base.metadata.create_all(bind=target_engine)

        non_empty_tables = _non_empty_tables(target_engine)
        if non_empty_tables and not replace_target:
            details = ", ".join(f"{table}={count}" for table, count in sorted(non_empty_tables.items()))
            raise RuntimeError(f"目标数据库不是空库，请先备份并清空，或使用 --replace-target。当前非空表: {details}")

        source_columns_by_table = _existing_table_columns(source_engine)
        migrated_counts: Dict[str, int] = {}

        with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
            for table in migration_tables():
                if table.name not in source_columns_by_table:
                    migrated_counts[table.name] = 0
                    continue
                migrated_counts[table.name] = _copy_table(
                    source_conn,
                    target_conn,
                    table,
                    source_columns_by_table[table.name],
                )

            if target_engine.dialect.name == "postgresql":
                _reset_postgres_sequences(target_conn)

        return migrated_counts
    finally:
        source_engine.dispose()
        target_engine.dispose()


def _print_plan(source_url: str, target_url: str, replace_target: bool) -> None:
    print("SQLite -> PostgreSQL 数据迁移")
    print(f"源数据库: {source_url}")
    print(f"目标数据库: {normalize_database_url(target_url)}")
    print(f"目标处理: {'先删除并重建项目表' if replace_target else '要求目标项目表为空'}")
    print("迁移表顺序:")
    for index, table_name in enumerate(migration_table_names(), start=1):
        print(f"  {index:02d}. {table_name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate GankAIGC SQLite data to PostgreSQL.")
    parser.add_argument(
        "--source",
        default=None,
        help=f"SQLite 文件路径或 sqlite:/// URL，默认 {DEFAULT_SQLITE_DB}",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="PostgreSQL DATABASE_URL，例如 postgresql://ai_polish:password@localhost:5432/ai_polish",
    )
    parser.add_argument(
        "--replace-target",
        action="store_true",
        help="删除并重建目标库里的项目表后再导入。会清空目标库中这些表的数据。",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="跳过交互确认，直接执行迁移。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_url = sqlite_source_url(args.source)
    target_url = normalize_database_url(args.target)

    _print_plan(source_url, target_url, args.replace_target)
    print("\n执行前请确保后端服务已停止，并已备份 SQLite 数据库文件。")

    if not args.yes:
        confirmation = input("输入 MIGRATE 继续: ").strip()
        if confirmation != "MIGRATE":
            print("已取消迁移。")
            return 1

    counts = migrate_sqlite_to_target(
        source_url=source_url,
        target_url=target_url,
        replace_target=args.replace_target,
    )

    print("\n迁移完成:")
    for table_name, count in counts.items():
        print(f"  {table_name}: {count}")
    print("\n请核对数据后，再把 .env 的 DATABASE_URL 切换到 PostgreSQL。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
