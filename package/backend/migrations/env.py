from logging.config import fileConfig
import os
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool


config = context.config

BACKEND_DIR = Path(__file__).resolve().parents[1]
PACKAGE_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

runtime_env_file = PACKAGE_DIR / ".env"
if "GANKAIGC_ENV_FILE" not in os.environ and runtime_env_file.exists():
    os.environ["GANKAIGC_ENV_FILE"] = str(runtime_env_file)

from app.config import settings  # noqa: E402
from app.database import Base, normalize_database_url  # noqa: E402
from app.models import models  # noqa: F401,E402


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata

MANAGED_PERFORMANCE_INDEX_PREFIXES = (
    "idx_opt_",
    "idx_change_log_",
    "idx_registration_invites_",
)


def get_database_url() -> str:
    return normalize_database_url(settings.DATABASE_URL).replace("%", "%%")


config.set_main_option("sqlalchemy.url", get_database_url())


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "index" and reflected and name:
        return not name.startswith(MANAGED_PERFORMANCE_INDEX_PREFIXES)
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
