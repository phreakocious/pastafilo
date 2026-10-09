#!/usr/bin/env bash
# Play the current code from bar 1, record it in the open REPL page, and wait
# for the WAV to land in output/. Prints the file's path.
# The page needs one click after each load: browsers keep audio suspended until then.
#
# Usage: scripts/record.sh <seconds> [base_url]
# base_url must be a server started from this checkout: the WAV lands in its output/.
#   scripts/record.sh 240                 # 128 bars at 130 BPM is 236 s
set -euo pipefail
secs=${1:?usage: record.sh <seconds> [base_url]}
base=${2:-http://localhost:3000}
cd "$(dirname "$0")/.."

marker=$(mktemp)
trap 'rm -f "$marker"' EXIT

curl -sS --fail-with-body -X POST "$base/api/stop" >/dev/null
curl -sS --fail-with-body -X POST "$base/api/play" >/dev/null
curl -sS --fail-with-body -X POST "$base/api/record" -H 'Content-Type: application/json' \
  -d "{\"seconds\": $secs}" >&2
echo >&2

deadline=$((SECONDS + ${secs%.*} + 60))
while ((SECONDS < deadline)); do
  f=$(find output -name '*.wav' -newer "$marker" 2>/dev/null | head -1)
  if [[ -n $f ]]; then
    echo "$f"
    exit 0
  fi
  sleep 2
done
echo "no recording arrived in $((${secs%.*} + 60)) s; did the page get a click since it loaded? (console: 'Recorded 0 samples')" >&2
exit 1
