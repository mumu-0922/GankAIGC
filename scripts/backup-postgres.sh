#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-backups}"
DATABASE_URL_VALUE="${DATABASE_URL:-}"

if [[ -z "$DATABASE_URL_VALUE" ]]; then
  echo "DATABASE_URL is required" >&2
  echo "Example: export DATABASE_URL='postgresql://ai_polish:password@127.0.0.1:5432/ai_polish'" >&2
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

mkdir -p "$OUTPUT_DIR"
timestamp="$(date +"%Y%m%d_%H%M%S")"
dump_file="$OUTPUT_DIR/gankaigc_${PGDATABASE_VALUE}_${timestamp}.dump"

PGPASSWORD="$PGPASSWORD_VALUE" pg_dump \
  --format=custom \
  --file="$dump_file" \
  --host="$PGHOST_VALUE" \
  --port="$PGPORT_VALUE" \
  --username="$PGUSER_VALUE" \
  --dbname="$PGDATABASE_VALUE"

echo "Backup created: $dump_file"
