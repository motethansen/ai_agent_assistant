#!/bin/bash
# Rotate logs/cron_sync.log — keep last 7 days, archive older lines to logs/archive/YYYY-MM/
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$REPO_ROOT/logs/cron_sync.log"
ARCHIVE_BASE="$REPO_ROOT/logs/archive"

# Nothing to do if log doesn't exist
if [ ! -f "$LOG_FILE" ]; then
    exit 0
fi

CUTOFF_DATE=$(date -v-7d "+%Y-%m-%d" 2>/dev/null || date -d "7 days ago" "+%Y-%m-%d")

# Temporary files for splitting
TMP_KEEP=$(mktemp)
TMP_ARCHIVE=$(mktemp)

# Track the current "run block" date and lines
current_block_date=""
current_block_lines=()

flush_block() {
    local block_date="$1"
    shift
    local lines=("$@")
    if [ -z "$block_date" ] || [ ${#lines[@]} -eq 0 ]; then
        return
    fi
    if [[ "$block_date" < "$CUTOFF_DATE" ]]; then
        # Archive this block
        local year_month="${block_date:0:7}"
        local archive_dir="$ARCHIVE_BASE/$year_month"
        mkdir -p "$archive_dir"
        local archive_file="$archive_dir/cron_sync_${block_date}.log"
        printf '%s\n' "${lines[@]}" >> "$archive_file"
    else
        # Keep this block
        printf '%s\n' "${lines[@]}" >> "$TMP_KEEP"
    fi
}

# Process the log file line by line, grouping into run blocks
# A new block starts at a "===" separator line that contains a date
declare -a block_lines=()
block_date=""

while IFS= read -r line || [ -n "$line" ]; do
    # Detect block start: "Cron Sync Started at YYYY-MM-DD ..."
    if [[ "$line" =~ Cron\ Sync\ Started\ at\ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
        # Flush previous block
        if [ ${#block_lines[@]} -gt 0 ]; then
            flush_block "$block_date" "${block_lines[@]}"
        fi
        block_date="${BASH_REMATCH[1]}"
        block_lines=("$line")
    else
        block_lines+=("$line")
    fi
done < "$LOG_FILE"

# Flush final block
if [ ${#block_lines[@]} -gt 0 ]; then
    flush_block "$block_date" "${block_lines[@]}"
fi

# Replace the log file with only the kept lines
mv "$TMP_KEEP" "$LOG_FILE"
rm -f "$TMP_ARCHIVE"

echo "[rotate_logs] Rotation complete. Kept entries from $CUTOFF_DATE onwards."
