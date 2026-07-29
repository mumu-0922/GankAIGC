from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_default_docker_compose_does_not_grant_app_docker_control():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    app_section = compose.split("\n  app:", 1)[1].split("\n  worker:", 1)[0]

    assert "target: /app/source" not in app_section
    assert "/var/run/docker.sock" not in app_section
    assert "source: ${GANKAIGC_HOST_PROJECT_DIR:-${PWD:-.}}/.env.docker" in compose
    assert "target: /app/config/.env.docker" in compose
    assert "- ./:/app/source" not in compose
    assert "/var/run/docker.sock" not in compose
    assert "updater:" not in compose
    assert "source: ${GANKAIGC_HOST_PROJECT_DIR:-${PWD:-.}}/backups" in app_section
    assert "target: /backups" in app_section
    assert "read_only: true" in app_section


def test_default_docker_compose_includes_postgres_backup_service():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "  backup:" in compose
    assert "docker-postgres-backup.sh" in compose
    assert "source: ${GANKAIGC_HOST_PROJECT_DIR:-${PWD:-.}}/backups" in compose
    assert "target: /backups" in compose
    assert "BACKUP_RETENTION_DAYS" in compose
    assert "BACKUP_INTERVAL_SECONDS" in compose
    assert "condition: service_healthy" in compose


def test_postgres_backup_is_validated_checksummed_and_atomically_published():
    script = (PROJECT_ROOT / "scripts" / "docker-postgres-backup.sh").read_text(
        encoding="utf-8"
    )

    assert "umask 077" in script
    assert 'partial_file="${dump_file}.partial.$$"' in script
    assert 'pg_restore --list "$partial_file"' in script
    assert 'mv "$partial_file" "$dump_file"' in script
    assert 'sha256sum "$(basename "$dump_file")"' in script
    assert 'mv "$checksum_partial" "$checksum_file"' in script


def test_optional_offsite_backup_uses_encrypted_restic_repository():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "scripts" / "docker-restic-offsite.sh").read_text(
        encoding="utf-8"
    )
    offsite_section = compose.split("\n  backup-offsite:", 1)[1].split("\nvolumes:", 1)[0]

    assert "restic/restic:0.17.3@sha256:" in offsite_section
    assert "- offsite" in offsite_section
    assert "RESTIC_REPOSITORY" in offsite_section
    assert "RESTIC_PASSWORD" in offsite_section
    assert "read_only: true" in offsite_section
    assert "env_file:" not in offsite_section
    assert "restic backup /backups" in script
    assert "restic backup /uploads" in script
    assert "--tag gankaigc-uploads" in script
    assert "target: /uploads" in offsite_section
    assert "VERIFY_UPLOADS_RESTORE" in offsite_section
    assert "restic restore latest" in script
    assert "cmp -s \"$source_manifest\" \"$restored_manifest\"" in script
    assert "--exclude '*.partial.*'" in script
    assert "restic check --read-data-subset=5%" in script


def test_default_docker_compose_persists_uploads_outside_container_layer():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    app_section = compose.split("\n  app:", 1)[1].split("\n  worker:", 1)[0]

    assert "GANKAIGC_UPLOAD_ROOT: /app/state/uploads" in app_section
    assert "source: ${GANKAIGC_HOST_PROJECT_DIR:-${PWD:-.}}/package/uploads" in app_section
    assert "target: /app/state/uploads" in app_section


def test_default_docker_compose_binds_app_to_loopback_for_reverse_proxy():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_example = (PROJECT_ROOT / ".env.docker.example").read_text(encoding="utf-8")

    assert '"${APP_BIND_IP:-127.0.0.1}:${APP_PORT:-9800}:9800"' in compose
    assert "APP_BIND_IP=127.0.0.1" in env_example


def test_default_docker_compose_runs_one_shot_schema_migration_before_runtime():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    app_section = compose.split("\n  app:", 1)[1].split("\n  worker:", 1)[0]
    worker_section = compose.split("\n  worker:", 1)[1].split("\n  migrate:", 1)[0]
    migrate_section = compose.split("\n  migrate:", 1)[1].split("\n  postgres:", 1)[0]

    assert "condition: service_completed_successfully" in app_section
    assert "condition: service_completed_successfully" in worker_section
    assert "command: python schema_migrate.py upgrade" in migrate_section
    assert "working_dir: /app/package/backend" in migrate_section
    assert "POSTGRES_MIGRATOR_USER" in migrate_section
    assert "POSTGRES_MIGRATOR_PASSWORD" in migrate_section
    assert 'restart: "no"' in migrate_section


def test_worker_has_bounded_drain_window_and_database_lease_settings():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_example = (PROJECT_ROOT / ".env.docker.example").read_text(encoding="utf-8")
    worker_section = compose.split("\n  worker:", 1)[1].split("\n  migrate:", 1)[0]

    assert "stop_grace_period: ${TASK_WORKER_STOP_GRACE_PERIOD:-10m}" in worker_section
    assert "TASK_WORKER_LEASE_TIMEOUT_SECONDS=120" in env_example
    assert "TASK_WORKER_STALE_TIMEOUT_SECONDS=120" in env_example
    assert "TASK_WORKER_MAX_ATTEMPTS=3" in env_example
    assert "TASK_EVENT_POLL_INTERVAL_SECONDS=1" in env_example
    assert "MAX_CONCURRENT_USERS=5" in env_example
    assert "API_KEY_CONCURRENCY=2" in env_example
    assert "MAX_PENDING_SESSIONS_PER_USER=3" in env_example
    assert "TASK_WORKER_MAX_CONCURRENCY=10" in env_example


def test_app_worker_and_migrator_drop_linux_capabilities():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    app_section = compose.split("\n  app:", 1)[1].split("\n  worker:", 1)[0]
    worker_section = compose.split("\n  worker:", 1)[1].split("\n  migrate:", 1)[0]
    migrate_section = compose.split("\n  migrate:", 1)[1].split("\n  postgres:", 1)[0]

    for service_section in (app_section, worker_section, migrate_section):
        assert 'user: "${GANKAIGC_RUNTIME_UID:-1000}:${GANKAIGC_RUNTIME_GID:-1000}"' in service_section
        assert "no-new-privileges:true" in service_section
        assert "cap_drop:" in service_section
        assert "- ALL" in service_section
        assert "pids_limit:" in service_section
        assert "read_only: true" in service_section
        assert "/tmp:rw,noexec,nosuid" in service_section


def test_migrator_and_backup_do_not_receive_whole_application_env_file():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    migrate_section = compose.split("\n  migrate:", 1)[1].split("\n  postgres:", 1)[0]
    backup_section = compose.split("\n  backup:", 1)[1].split("\n  backup-offsite:", 1)[0]

    assert "env_file:" not in migrate_section
    assert "GANKAIGC_ENV_FILE" not in migrate_section
    assert "env_file:" not in backup_section
    for secret_name in ("SECRET_KEY", "ADMIN_PASSWORD", "POLISH_API_KEY", "ENCRYPTION_KEY"):
        assert secret_name not in migrate_section
        assert secret_name not in backup_section


def test_production_compose_replaces_shared_env_file_with_service_secrets():
    compose = (PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    app_section = compose.split("\n  app:", 1)[1].split("\n  worker:", 1)[0]
    worker_section = compose.split("\n  worker:", 1)[1].split("\n  migrate:", 1)[0]
    migrate_section = compose.split("\n  migrate:", 1)[1].split("\n  postgres:", 1)[0]
    postgres_section = compose.split("\n  postgres:", 1)[1].split("\n  backup:", 1)[0]
    backup_section = compose.split("\n  backup:", 1)[1].split("\n  backup-offsite:", 1)[0]

    assert "env_file: !reset []" in app_section
    assert "env_file: !reset []" in worker_section
    assert "volumes: !override" in app_section
    assert "target: /app/config/runtime.env" in app_section
    assert "DATABASE_URL_FILE: /run/secrets/database_url" in app_section
    assert "ADMIN_PASSWORD_FILE: /run/secrets/admin_password" in app_section
    assert "SECRET_KEY_FILE: /run/secrets/secret_key" in worker_section
    assert "ADMIN_PASSWORD_FILE: /run/secrets/admin_password" in worker_section
    assert "source: app_admin_password" in worker_section
    assert "DATABASE_SESSION_ROLE:" in migrate_section
    assert "POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password" in postgres_section
    assert "library/postgres:16-alpine@sha256:" in postgres_section
    assert "library/postgres:16-alpine@sha256:" in backup_section
    assert "POSTGRES_USER: ${POSTGRES_BACKUP_ROLE:-gankaigc_backup}" in backup_section

    for section in (app_section, worker_section, migrate_section, postgres_section, backup_section):
        assert "${POSTGRES_PASSWORD:" not in section


def test_production_compose_mounts_only_role_provisioning_secrets_to_bootstrap_job():
    compose = (PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    provision_section = compose.split("\n  provision-roles:", 1)[1].split("\nsecrets:", 1)[0]

    assert "- bootstrap" in provision_section
    assert "python provision_db_roles.py" in provision_section
    assert "DATABASE_URL_FILE: /run/secrets/database_url" in provision_section
    assert "POSTGRES_MIGRATOR_PASSWORD_FILE: /run/secrets/migrator_password" in provision_section
    assert "POSTGRES_APP_PASSWORD_FILE: /run/secrets/app_password" in provision_section
    assert "POSTGRES_BACKUP_PASSWORD_FILE: /run/secrets/backup_password" in provision_section
    assert "POSTGRES_REASSIGN_EXISTING_OBJECTS:" in provision_section
    for application_secret in ("SECRET_KEY", "ADMIN_PASSWORD", "ENCRYPTION_KEY", "API_KEY"):
        assert application_secret not in provision_section


def test_backup_scripts_accept_password_files_without_echoing_secret_values():
    postgres_script = (PROJECT_ROOT / "scripts" / "docker-postgres-backup.sh").read_text(
        encoding="utf-8"
    )
    restic_script = (PROJECT_ROOT / "scripts" / "docker-restic-offsite.sh").read_text(
        encoding="utf-8"
    )

    assert "POSTGRES_PASSWORD_FILE" in postgres_script
    assert "RESTIC_PASSWORD_FILE" in restic_script
    assert "AWS_ACCESS_KEY_ID_FILE" in restic_script
    assert "AWS_SECRET_ACCESS_KEY_FILE" in restic_script
    assert 'cat "$file_path"' in postgres_script
    assert 'cat "$file_path"' in restic_script


def test_docker_compose_documents_manual_update_command_only():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "docker compose --env-file .env.docker pull" not in compose
    assert "--profile update" not in compose


def test_docker_env_example_disables_web_triggered_update():
    env_example = (PROJECT_ROOT / ".env.docker.example").read_text(encoding="utf-8")

    assert "VPS_UPDATE_ENABLED=false" in env_example
    assert "VPS_UPDATE_COMMAND" not in env_example
    assert "docker.sock" not in env_example
    assert "git fetch --tags origin main" in env_example
    assert "git pull --ff-only origin main" in env_example
    assert "docker compose --env-file .env.docker up -d --build" in env_example
    assert "docker compose --env-file .env.docker pull" not in env_example
    assert "BACKUP_RETENTION_DAYS=14" in env_example
    assert "BACKUP_INTERVAL_SECONDS=86400" in env_example
    assert "docker-compose.update.yml" not in env_example


def test_ci_creates_runtime_env_file_before_compose_validation():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "cp .env.docker.example .env.docker" in workflow
    assert "touch .env.runtime" in workflow
    assert "mkdir -p .ci-secrets" in workflow
    assert "GANKAIGC_SECRETS_DIR=.ci-secrets" in workflow
    assert "docker compose --env-file .env.docker config --quiet" in workflow
    assert "docker-compose.prod.yml config --quiet" in workflow


def test_ci_validates_update_profile_and_keeps_frontend_dist_artifact():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "--profile update" not in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "package/frontend/dist" in workflow
