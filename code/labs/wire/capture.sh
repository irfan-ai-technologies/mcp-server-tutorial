#!/usr/bin/env bash
# Capture real MCP traffic against ledger, so chapter 2 quotes bytes that were
# actually on a socket rather than bytes someone typed into a chapter.
#
#   ./capture.sh            # writes transcripts/*.txt
#
# Everything here is deliberately curl and nothing else. A client library would
# hide exactly the thing the chapter is about.
set -euo pipefail

PORT="${PORT:-8973}"
URL="http://127.0.0.1:${PORT}/mcp"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/transcripts"
LEDGER="$HERE/../../ledger"

mkdir -p "$OUT"

echo "starting ledger on :$PORT"
( cd "$LEDGER" && uv run ledger --transport http --port "$PORT" >/tmp/wire-ledger.log 2>&1 ) &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  curl -s -o /dev/null --max-time 1 "$URL" 2>/dev/null && break
  sleep 0.5
done

# Two files per capture: the request as sent, the response as received. Keeping
# them apart means a chapter can include either one with real JSON highlighting,
# and a diff after re-running points at exactly what changed.
capture() {
  local name="$1" body="$2"
  echo "$body" | python3 -m json.tool > "$OUT/$name.request.json"
  curl -sS -L --max-time 20 -X POST "$URL" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d "$body" \
    | sed 's/^data: //' \
    | python3 -c 'import sys, json
raw = "".join(l for l in sys.stdin if l.strip() and not l.startswith("event:"))
try:
    print(json.dumps(json.loads(raw), indent=2))
except Exception:
    print(raw)' > "$OUT/$name.response.json"
  echo "  $name.request.json / $name.response.json"
}

capture discover \
  '{"jsonrpc":"2.0","id":1,"method":"server/discover"}'

capture tools-list \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# tools/list is 169 lines and no chapter can print that. Project one tool out of
# the captured response rather than retyping an abridged version by hand: the
# excerpt stays real, and it changes when the server does.
python3 -c '
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
d = json.loads((out / "tools-list.response.json").read_text())
tools = d["result"]["tools"]
one = next(t for t in tools if t["name"] == "find_licences")
(out / "tools-list.one-tool.json").write_text(json.dumps(one, indent=2) + "\n")
print(f"  tools-list.one-tool.json (1 of {len(tools)})")
' "$OUT"

capture tools-call \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_title","arguments":{"title_id":"T-1152"}}}'

capture tools-call-error \
  '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_title","arguments":{"title_id":"T-nope"}}}'

capture resources-list \
  '{"jsonrpc":"2.0","id":5,"method":"resources/list"}'

capture resources-read \
  '{"jsonrpc":"2.0","id":6,"method":"resources/read","params":{"uri":"ledger://agreement/A-100-0"}}'

capture prompts-get \
  '{"jsonrpc":"2.0","id":7,"method":"prompts/get","params":{"name":"clearance_check","arguments":{"title":"The Winter Cartograph","territory":"GB","rights":"svod"}}}'

capture unknown-method \
  '{"jsonrpc":"2.0","id":8,"method":"tools/nope"}'

echo "done"
