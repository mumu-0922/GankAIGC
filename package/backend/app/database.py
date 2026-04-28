from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


DATABASE_URL = normalize_database_url(settings.DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """数据库会话依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库 - 安全地创建或更新数据库结构"""
    try:
        # 导入所有模型以确保它们被注册到 Base.metadata
        from app.models import models  # noqa: F401
        
        # 创建所有表（如果不存在）
        Base.metadata.create_all(bind=engine)
        
        # 检查并添加可能缺失的列（用于数据库迁移）
        _migrate_database_schema()
        
        # 自动添加性能优化索引
        _add_performance_indexes()
        
        print("✓ 数据库初始化成功")
        return True
    except Exception as e:
        print(f"✗ 数据库初始化失败: {str(e)}")
        raise


def _add_column_safely(conn, table_name, column_name, column_def):
    """安全地添加列（如果不存在）"""
    try:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))
        conn.commit()
        return True
    except Exception as e:
        # 列可能已存在或其他错误
        conn.rollback()
        return False


def _sqlite_select_expression(existing_columns, column_name, fallback_sql, coalesce_sql=None):
    if column_name not in existing_columns:
        return fallback_sql
    if coalesce_sql is not None:
        return f"COALESCE({column_name}, {coalesce_sql})"
    return column_name


def _rebuild_sqlite_users_table_without_card_keys(conn, existing_columns):
    """SQLite 通过重建 users 表来移除旧卡密字段。"""
    column_names = [
        "id",
        "username",
        "nickname",
        "password_hash",
        "access_link",
        "is_active",
        "is_unlimited",
        "credit_balance",
        "created_at",
        "last_used",
        "last_login_at",
        "usage_limit",
        "usage_count",
    ]
    select_expressions = {
        "id": _sqlite_select_expression(existing_columns, "id", "NULL"),
        "username": _sqlite_select_expression(existing_columns, "username", "NULL"),
        "nickname": _sqlite_select_expression(
            existing_columns,
            "nickname",
            "username" if "username" in existing_columns else "NULL",
        ),
        "password_hash": _sqlite_select_expression(existing_columns, "password_hash", "NULL"),
        "access_link": _sqlite_select_expression(existing_columns, "access_link", "''"),
        "is_active": _sqlite_select_expression(existing_columns, "is_active", "1", "1"),
        "is_unlimited": _sqlite_select_expression(existing_columns, "is_unlimited", "0", "0"),
        "credit_balance": _sqlite_select_expression(existing_columns, "credit_balance", "0", "0"),
        "created_at": _sqlite_select_expression(existing_columns, "created_at", "CURRENT_TIMESTAMP"),
        "last_used": _sqlite_select_expression(existing_columns, "last_used", "NULL"),
        "last_login_at": _sqlite_select_expression(existing_columns, "last_login_at", "NULL"),
        "usage_limit": _sqlite_select_expression(
            existing_columns,
            "usage_limit",
            str(settings.DEFAULT_USAGE_LIMIT),
            str(settings.DEFAULT_USAGE_LIMIT),
        ),
        "usage_count": _sqlite_select_expression(existing_columns, "usage_count", "0", "0"),
    }
    insert_columns_sql = ", ".join(column_names)
    select_sql = ", ".join(
        f"{expression} AS {column_name}" for column_name, expression in select_expressions.items()
    )

    try:
        conn.commit()
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()
        conn.execute(text("DROP TABLE IF EXISTS users__migration"))
        conn.execute(text(
            """
            CREATE TABLE users__migration (
                id INTEGER PRIMARY KEY,
                username VARCHAR(100),
                nickname VARCHAR(100),
                password_hash VARCHAR(255),
                access_link VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                is_unlimited BOOLEAN DEFAULT 0,
                credit_balance INTEGER DEFAULT 0,
                created_at DATETIME,
                last_used DATETIME,
                last_login_at DATETIME,
                usage_limit INTEGER DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                UNIQUE (username),
                UNIQUE (access_link)
            )
            """
        ))
        conn.execute(text(
            f"""
            INSERT INTO users__migration ({insert_columns_sql})
            SELECT {select_sql}
            FROM users
            """
        ))
        conn.execute(text("DROP TABLE users"))
        conn.execute(text("ALTER TABLE users__migration RENAME TO users"))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        try:
            conn.execute(text("DROP TABLE IF EXISTS users__migration"))
            conn.commit()
        except Exception:
            conn.rollback()
        return False
    finally:
        try:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
        except Exception:
            conn.rollback()


def _add_performance_indexes():
    """添加性能优化索引"""
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # 定义需要的索引
        indexes = [
            # OptimizationSession indexes
            ("idx_opt_session_user_id", "optimization_sessions", "user_id"),
            ("idx_opt_session_status", "optimization_sessions", "status"),
            ("idx_opt_session_created_at", "optimization_sessions", "created_at"),
            
            # OptimizationSegment indexes
            ("idx_opt_segment_session_id", "optimization_segments", "session_id"),
            ("idx_opt_segment_index", "optimization_segments", "segment_index"),
            ("idx_opt_segment_status", "optimization_segments", "status"),
            
            # ChangeLog indexes
            ("idx_change_log_session_id", "change_logs", "session_id"),
            ("idx_change_log_segment_index", "change_logs", "segment_index"),
            ("idx_change_log_stage", "change_logs", "stage"),

            # RegistrationInvite indexes
            ("idx_registration_invites_created_by_user_id", "registration_invites", "created_by_user_id"),
        ]
        
        with engine.connect() as conn:
            for index_name, table_name, column_name in indexes:
                # 检查表是否存在
                if table_name not in tables:
                    continue
                
                try:
                    # 获取表上现有的索引
                    existing_indexes = inspector.get_indexes(table_name)
                    index_names = {idx['name'] for idx in existing_indexes}
                    
                    # 如果索引已存在，跳过
                    if index_name in index_names:
                        continue
                    
                    # 创建索引（SQLite 和 PostgreSQL 都支持相同语法）
                    conn.execute(text(
                        f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
                    ))
                    conn.commit()
                    print(f"  ✓ 添加索引: {index_name}")
                    
                except Exception as e:
                    # 索引可能已存在或其他错误
                    conn.rollback()
                    # 静默失败，不阻止应用启动
                    pass
    
    except Exception as e:
        print(f"  ⚠ 添加性能索引警告: {str(e)}")
        # 失败不应该阻止应用启动


def _migrate_database_schema():
    """迁移数据库结构 - 添加新列到已存在的表"""
    try:
        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        with engine.connect() as conn:

            if "optimization_sessions" in tables:
                columns = {column["name"] for column in inspector.get_columns("optimization_sessions")}

                if "failed_segment_index" not in columns:
                    if _add_column_safely(conn, "optimization_sessions", "failed_segment_index", "INTEGER"):
                        print("  ✓ 添加字段: optimization_sessions.failed_segment_index")

                if "processing_mode" not in columns:
                    if _add_column_safely(
                        conn,
                        "optimization_sessions",
                        "processing_mode",
                        "VARCHAR(50) DEFAULT 'paper_polish_enhance'",
                    ):
                        print("  ✓ 添加字段: optimization_sessions.processing_mode")

                if "billing_mode" not in columns:
                    if _add_column_safely(
                        conn,
                        "optimization_sessions",
                        "billing_mode",
                        "VARCHAR(20) DEFAULT 'platform'",
                    ):
                        print("  ✓ 添加字段: optimization_sessions.billing_mode")

                if "credential_source" not in columns:
                    if _add_column_safely(
                        conn,
                        "optimization_sessions",
                        "credential_source",
                        "VARCHAR(20) DEFAULT 'system'",
                    ):
                        print("  ✓ 添加字段: optimization_sessions.credential_source")

                if "charge_status" not in columns:
                    if _add_column_safely(
                        conn,
                        "optimization_sessions",
                        "charge_status",
                        "VARCHAR(20) DEFAULT 'not_charged'",
                    ):
                        print("  ✓ 添加字段: optimization_sessions.charge_status")

                if "charged_credits" not in columns:
                    if _add_column_safely(
                        conn,
                        "optimization_sessions",
                        "charged_credits",
                        "INTEGER DEFAULT 0",
                    ):
                        print("  ✓ 添加字段: optimization_sessions.charged_credits")

                if "project_id" not in columns:
                    if _add_column_safely(conn, "optimization_sessions", "project_id", "INTEGER"):
                        print("  ✓ 添加字段: optimization_sessions.project_id")

                if "task_title" not in columns:
                    if _add_column_safely(conn, "optimization_sessions", "task_title", "VARCHAR(255)"):
                        print("  ✓ 添加字段: optimization_sessions.task_title")

                if "emotion_model" not in columns:
                    added = _add_column_safely(conn, "optimization_sessions", "emotion_model", "VARCHAR(100)")
                    _add_column_safely(conn, "optimization_sessions", "emotion_api_key", "VARCHAR(255)")
                    _add_column_safely(conn, "optimization_sessions", "emotion_base_url", "VARCHAR(255)")
                    if added:
                        print("  ✓ 添加字段: optimization_sessions.emotion_* 字段")

            if "users" in tables:
                user_columns = {column["name"]: column for column in inspector.get_columns("users")}

                if engine.dialect.name == "sqlite" and (
                    "card_key" in user_columns or "legacy_card_key" in user_columns
                ):
                    if _rebuild_sqlite_users_table_without_card_keys(conn, user_columns):
                        print("  ✓ 重建 users 表以移除旧卡密字段")
                        Base.metadata.create_all(bind=engine)
                        inspector = inspect(engine)
                        tables = inspector.get_table_names()
                        user_columns = {column["name"]: column for column in inspector.get_columns("users")}

                if "username" not in user_columns:
                    if _add_column_safely(conn, "users", "username", "VARCHAR(100)"):
                        print("  ✓ 添加字段: users.username")

                if "nickname" not in user_columns:
                    if _add_column_safely(conn, "users", "nickname", "VARCHAR(100)"):
                        print("  ✓ 添加字段: users.nickname")

                if "password_hash" not in user_columns:
                    if _add_column_safely(conn, "users", "password_hash", "VARCHAR(255)"):
                        print("  ✓ 添加字段: users.password_hash")

                if "is_unlimited" not in user_columns:
                    if _add_column_safely(conn, "users", "is_unlimited", "BOOLEAN DEFAULT 0"):
                        print("  ✓ 添加字段: users.is_unlimited")

                if "credit_balance" not in user_columns:
                    if _add_column_safely(conn, "users", "credit_balance", "INTEGER DEFAULT 0"):
                        print("  ✓ 添加字段: users.credit_balance")

                if "last_login_at" not in user_columns:
                    if _add_column_safely(conn, "users", "last_login_at", "DATETIME"):
                        print("  ✓ 添加字段: users.last_login_at")

                if "usage_limit" not in user_columns:
                    if _add_column_safely(
                        conn,
                        "users",
                        "usage_limit",
                        f"INTEGER DEFAULT {settings.DEFAULT_USAGE_LIMIT}",
                    ):
                        print("  ✓ 添加字段: users.usage_limit")

                if "usage_count" not in user_columns:
                    if _add_column_safely(conn, "users", "usage_count", "INTEGER DEFAULT 0"):
                        print("  ✓ 添加字段: users.usage_count")

                try:
                    conn.execute(text("UPDATE users SET is_unlimited = 0 WHERE is_unlimited IS NULL"))
                    conn.execute(text("UPDATE users SET credit_balance = 0 WHERE credit_balance IS NULL"))
                    conn.execute(text("UPDATE users SET nickname = username WHERE nickname IS NULL AND username IS NOT NULL"))
                    conn.execute(
                        text(
                            f"UPDATE users SET usage_limit = {settings.DEFAULT_USAGE_LIMIT} WHERE usage_limit IS NULL"
                        )
                    )
                    conn.execute(text("UPDATE users SET usage_count = 0 WHERE usage_count IS NULL"))
                    conn.commit()
                except Exception:
                    conn.rollback()

            if "optimization_segments" in tables:
                segment_columns = {column["name"] for column in inspector.get_columns("optimization_segments")}

                if "is_title" not in segment_columns:
                    if _add_column_safely(conn, "optimization_segments", "is_title", "BOOLEAN DEFAULT 0"):
                        print("  ✓ 添加字段: optimization_segments.is_title")

            if "custom_prompts" in tables:
                prompt_columns = {column["name"] for column in inspector.get_columns("custom_prompts")}

                if "is_system" not in prompt_columns:
                    if _add_column_safely(conn, "custom_prompts", "is_system", "BOOLEAN DEFAULT 0"):
                        print("  ✓ 添加字段: custom_prompts.is_system")

                if "is_active" not in prompt_columns:
                    if _add_column_safely(conn, "custom_prompts", "is_active", "BOOLEAN DEFAULT 1"):
                        print("  ✓ 添加字段: custom_prompts.is_active")

            if "registration_invites" in tables:
                invite_columns = {column["name"] for column in inspector.get_columns("registration_invites")}

                if "created_by_user_id" not in invite_columns:
                    if _add_column_safely(conn, "registration_invites", "created_by_user_id", "INTEGER"):
                        print("  ✓ 添加字段: registration_invites.created_by_user_id")

    except Exception as e:
        print(f"  ⚠ 数据库迁移警告: {str(e)}")
