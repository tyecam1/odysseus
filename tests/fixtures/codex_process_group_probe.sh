#!/bin/sh
set -eu

pid_dir="${AOTERU_TEST_PID_DIR:?}"
mode="${AOTERU_TEST_MODE:-success}"
out_path=""
previous=""

for arg in "$@"; do
    if [ "$previous" = "-o" ]; then
        out_path="$arg"
        break
    fi
    previous="$arg"
done

printf '%s\n' "$$" > "$pid_dir/wrapper.pid"

if [ "$mode" = "timeout" ]; then
    sleep 30 &
    printf '%s\n' "$!" > "$pid_dir/child.pid"
    sleep 30
    exit 0
fi

if [ -n "$out_path" ]; then
    printf '%s' "${AOTERU_TEST_OUTPUT_TEXT:-fixture output}" > "$out_path"
fi
