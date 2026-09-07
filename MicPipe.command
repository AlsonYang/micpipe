#!/bin/bash
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$DIR/.venv/bin/python"
LOG_DIR="$HOME/Library/Logs/MicPipe"
LOG_FILE="$LOG_DIR/micpipe.log"

if [[ ! -x "$PYTHON" ]]; then
    printf '%s\n' "MicPipe is not set up yet." \
        "Open Terminal, run:" \
        "  cd '$DIR'" \
        "  uv sync --frozen" \
        "Then double-click MicPipe.command again."
    read -r -n 1 -p "Press any key to close..."
    printf '\n'
    exit 1
fi

mkdir -p "$LOG_DIR"
chmod 700 "$LOG_DIR"
nohup "$PYTHON" "$DIR/micpipe.py" >>"$LOG_FILE" 2>&1 &
printf 'MicPipe started. Log: %s\n' "$LOG_FILE"
