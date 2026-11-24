#!/usr/bin/env bash
#
# Raycast Script Command: Notion Daily Todo DB에서 날짜에 맞는 업무 일지 페이지를 바로 연다.
# 페이지 ID는 날짜로 계산할 수 없어서(UUID에 무작위 부분이 있음) Due Date 필터로 조회한다.
#
# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title 업무 todo
# @raycast.mode silent
#
# Optional parameters:
# @raycast.packageName Notion
# @raycast.icon 📓
# @raycast.argument1 { "type": "text", "placeholder": "날짜 (비우면 오늘, -1=어제, YYYY-MM-DD)", "optional": true }
# @raycast.description Daily Todo DB에서 오늘(또는 지정 날짜) 업무 일지 페이지를 연다

set -uo pipefail

# Raycast는 로그인 셸 환경(.zshenv)을 물려받지 않는다 → 토큰을 Keychain에서 직접 읽는다.
NOTION_TOKEN="${NOTION_TOKEN:-$(security find-generic-password -a "claude-mcp" -s "notion-personal-token" -w 2>/dev/null)}"
if [[ -z "$NOTION_TOKEN" ]]; then
  echo "NOTION_TOKEN 없음 (Keychain claude-mcp/notion-personal-token 확인)"
  exit 1
fi

arg="${1:-}"
case "$arg" in
  "")            target=$(date +%F) ;;
  -[0-9]*)       target=$(date -v"${arg}"d +%F) ;;
  +[0-9]*)       target=$(date -v"${arg}"d +%F) ;;
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) target="$arg" ;;
  *) echo "날짜 형식 오류: $arg (예: -1, 2026-11-23)"; exit 1 ;;
esac

page_id=$(NOTION_TOKEN="$NOTION_TOKEN" TARGET="$target" /usr/bin/python3 -I - <<'PY'
import json, os, sys, urllib.request, urllib.error

DB_ID = "2bf64745-3170-8016-b20a-ff022dea06cb"  # Daily Todo DB
HEADERS = {
    "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
    "Notion-Version": "2025-09-03",
    "Content-Type": "application/json",
}

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"https://api.notion.com/v1{path}", data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(r, timeout=10) as resp:
        return json.loads(resp.read())

try:
    ds_id = req("GET", f"/databases/{DB_ID}")["data_sources"][0]["id"]
    res = req("POST", f"/data_sources/{ds_id}/query", {
        "filter": {"property": "Due Date", "date": {"equals": os.environ["TARGET"]}},
        "page_size": 1,
    })["results"]
except urllib.error.HTTPError as e:
    print(f"ERR HTTP {e.code}")
    sys.exit(0)
except Exception as e:
    print(f"ERR {type(e).__name__}")
    sys.exit(0)

print(res[0]["id"].replace("-", "") if res else "")
PY
)

if [[ "$page_id" == ERR* ]]; then
  echo "Notion 조회 실패: ${page_id#ERR }"
  exit 1
fi
if [[ -z "$page_id" ]]; then
  echo "$target 일지 페이지가 없습니다"
  exit 1
fi

open "https://app.notion.com/p/$page_id"
echo "$target 업무 일지를 엽니다"
