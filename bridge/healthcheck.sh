#!/bin/sh
# No authentication or task calls. Inspect only container-local operator metrics.
set -eu
health_base="http://${HEALTH_LISTEN_ADDR:-127.0.0.1:8080}"
# Global /readyz also waits for OAuth discovery, which this static-Bearer
# deployment does not use. Check the official main-channel probe instead.
wget -q -O /dev/null "$health_base/healthz"
wget -q -O - "$health_base/health/mcp" | tr -d '\r\n' | grep -Eq \
  '"startup_probe"[[:space:]]*:[[:space:]]*\{[[:space:]]*"state"[[:space:]]*:[[:space:]]*"succeeded"'
# Detect a stalled control-plane connection, allowing four normal poll cycles.
wget -q -O - "$health_base/metrics" | awk -v now="$(date +%s)" '
  $1 == "commands_poll_last_successful_timestamp_seconds" ||
  $1 ~ /^commands_poll_last_successful_timestamp_seconds\{/ {
    stamp = $NF
    if (stamp > 0 && now - stamp >= -5 && now - stamp <= 120) recent = 1
  }
  END { exit !recent }
'
