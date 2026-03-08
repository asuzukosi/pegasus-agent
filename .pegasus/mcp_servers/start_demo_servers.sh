#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log_dir="$script_dir/logs"

mkdir -p "$log_dir"

cd "$script_dir"

echo "starting hackathon manager server..."
node "hackathon_manager_server.js" >"$log_dir/hackathon_manager.log" 2>&1 &
hackathon_pid=$!

echo "starting event booking server..."
node "event_booking_server.js" >"$log_dir/event_booking.log" 2>&1 &
event_booking_pid=$!

cleanup() {
  echo
  echo "stopping demo mcp servers..."
  kill "$hackathon_pid" "$event_booking_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "hackathon manager pid: $hackathon_pid"
echo "event booking pid: $event_booking_pid"
echo "logs: $log_dir"
echo "press ctrl+c to stop both servers"

wait "$hackathon_pid" "$event_booking_pid"
