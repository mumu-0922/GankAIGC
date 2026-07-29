#!/usr/bin/env sh
set -eu
umask 077

load_secret_file() {
  variable_name="$1"
  case "$variable_name" in
    RESTIC_PASSWORD) file_path="${RESTIC_PASSWORD_FILE:-}" ;;
    AWS_ACCESS_KEY_ID) file_path="${AWS_ACCESS_KEY_ID_FILE:-}" ;;
    AWS_SECRET_ACCESS_KEY) file_path="${AWS_SECRET_ACCESS_KEY_FILE:-}" ;;
    *) echo "unsupported secret variable" >&2; exit 1 ;;
  esac
  file_variable_name="${variable_name}_FILE"
  [ -n "$file_path" ] || return 0
  [ -f "$file_path" ] || {
    echo "$file_variable_name must point to a regular file" >&2
    exit 1
  }
  file_mode="$(stat -c '%a' "$file_path")"
  [ "$file_mode" = "600" ] || [ "$file_mode" = "400" ] || {
    echo "$file_variable_name must have mode 0600 or 0400" >&2
    exit 1
  }
  secret_value="$(cat "$file_path")"
  [ -n "$secret_value" ] || {
    echo "$file_variable_name is empty" >&2
    exit 1
  }
  export "$variable_name=$secret_value"
}

load_secret_file RESTIC_PASSWORD
load_secret_file AWS_ACCESS_KEY_ID
load_secret_file AWS_SECRET_ACCESS_KEY

RESTIC_INTERVAL_SECONDS="${RESTIC_INTERVAL_SECONDS:-86400}"
RESTIC_KEEP_DAILY="${RESTIC_KEEP_DAILY:-14}"
RESTIC_KEEP_WEEKLY="${RESTIC_KEEP_WEEKLY:-8}"
RESTIC_KEEP_MONTHLY="${RESTIC_KEEP_MONTHLY:-12}"
VERIFY_UPLOADS_RESTORE="${VERIFY_UPLOADS_RESTORE:-false}"

if [ -z "${RESTIC_REPOSITORY:-}" ] || [ -z "${RESTIC_PASSWORD:-}" ]; then
  echo "RESTIC_REPOSITORY and RESTIC_PASSWORD(_FILE) are required" >&2
  exit 1
fi

if ! restic snapshots >/dev/null 2>&1; then
  restic init
fi

run_offsite_backup() {
  # Only validated final dumps/checksums match these include rules; .partial
  # files are never uploaded as successful restore points.
  restic backup /backups \
    --tag gankaigc-postgres \
    --exclude '*.partial.*'
  restic backup /uploads \
    --tag gankaigc-uploads \
    --exclude '*.partial.*'
  restic forget \
    --tag gankaigc-postgres \
    --keep-daily "$RESTIC_KEEP_DAILY" \
    --keep-weekly "$RESTIC_KEEP_WEEKLY" \
    --keep-monthly "$RESTIC_KEEP_MONTHLY"
  restic forget \
    --tag gankaigc-uploads \
    --keep-daily "$RESTIC_KEEP_DAILY" \
    --keep-weekly "$RESTIC_KEEP_WEEKLY" \
    --keep-monthly "$RESTIC_KEEP_MONTHLY"
  restic prune
  restic check --read-data-subset=5%

  if [ "$VERIFY_UPLOADS_RESTORE" = "true" ]; then
    restore_root="$(mktemp -d /tmp/gankaigc-uploads-restore.XXXXXX)"
    source_manifest="$(mktemp /tmp/gankaigc-uploads-source.XXXXXX)"
    restored_manifest="$(mktemp /tmp/gankaigc-uploads-restored.XXXXXX)"
    trap 'rm -rf "$restore_root" "$source_manifest" "$restored_manifest"' EXIT HUP INT TERM
    restic restore latest \
      --tag gankaigc-uploads \
      --target "$restore_root" \
      --include /uploads
    (
      cd /uploads
      find . -type f -exec sha256sum {} + | LC_ALL=C sort
    ) > "$source_manifest"
    (
      cd "$restore_root/uploads"
      find . -type f -exec sha256sum {} + | LC_ALL=C sort
    ) > "$restored_manifest"
    cmp -s "$source_manifest" "$restored_manifest" || {
      echo "uploads isolated restore SHA-256 verification failed" >&2
      exit 1
    }
    echo "uploads isolated restore SHA-256 verification passed"
    rm -rf "$restore_root" "$source_manifest" "$restored_manifest"
    trap - EXIT HUP INT TERM
  fi
}

if [ "${RUN_ONCE:-false}" = "true" ]; then
  run_offsite_backup
  exit 0
fi

while true; do
  run_offsite_backup
  sleep "$RESTIC_INTERVAL_SECONDS"
done
