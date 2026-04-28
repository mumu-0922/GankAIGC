#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/restore-postgres.sh <dump-file>

Requires DATABASE_URL, for example:
  export DATABASE_URL='postgresql://ai_polish:password@127.0.0.1:5432/ai_polish'

Restore uses: pg_restore --clean --if-exists
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

DUMP_FILE="${1:-}"
DATABASE_URL_VALUE="${DATABASE_URL:-}"

if [[ -z "$DUMP_FILE" ]]; then
  usage >&2
  exit 1
fi

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "Dump file not found: $DUMP_FILE" >&2
  exit 1
fi

if [[ -z "$DATABASE_URL_VALUE" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi

eval "$(
  python3 - "$DATABASE_URL_VALUE" <<'PY'
import shlex
import sys
from urllib.parse import unquote, urlparse

url = urlparse(sys.argv[1])
if url.scheme not in {"postgresql", "postgresql+psycopg"}:
    raise SystemExit("DATABASE_URL must start with postgresql:// or postgresql+psycopg://")
if not url.username or url.password is None:
    raise SystemExit("DATABASE_URL must include username and password")

values = {
    "PGHOST_VALUE": url.hostname or "127.0.0.1",
    "PGPORT_VALUE": str(url.port or 5432),
    "PGDATABASE_VALUE": (url.path or "/").lstrip("/"),
    "PGUSER_VALUE": unquote(url.username),
    "PGPASSWORD_VALUE": unquote(url.password),
}
for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"

PGPASSWORD="$PGPASSWORD_VALUE" pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --host="$PGHOST_VALUE" \
  --port="$PGPORT_VALUE" \
  --username="$PGUSER_VALUE" \
  --dbname="$PGDATABASE_VALUE" \
  "$DUMP_FILE"

echo "Restore completed into database: $PGDATABASE_VALUE"
