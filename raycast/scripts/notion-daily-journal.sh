#!/usr/bin/env bash
#
# Raycast Script Command: Notion Daily Todo DB에서 오늘 업무 일지 페이지를 Chrome 새 탭으로 연다.
# 페이지 ID는 날짜로 계산할 수 없어서(UUID에 무작위 부분이 있음) Due Date 필터로 조회한다.
# 오늘 페이지가 없으면(주말 등) 기본 템플릿으로 만든 뒤 연다.
#
# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title notion:daily-todo
# @raycast.mode silent
#
# Optional parameters:
# @raycast.packageName Notion
# @raycast.icon /Users/changhwan/.dotfiles/raycast/scripts/images/notion.png
# @raycast.description Daily Todo DB에서 오늘 업무 일지 페이지를 Chrome 새 탭으로 연다

set -uo pipefail

# Raycast는 로그인 셸 환경(.zshenv)을 물려받지 않는다 → 토큰을 Keychain에서 직접 읽는다.
NOTION_TOKEN="${NOTION_TOKEN:-$(security find-generic-password -a "claude-mcp" -s "notion-personal-token" -w 2>/dev/null)}"
if [[ -z "$NOTION_TOKEN" ]]; then
  echo "NOTION_TOKEN 없음 (Keychain claude-mcp/notion-personal-token 확인)"
  exit 1
fi

# DAILY_TODO_DATE는 시험용이다(Raycast에서는 비어 있어 항상 오늘).
target="${DAILY_TODO_DATE:-$(date +%F)}"

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

target = os.environ["TARGET"]
try:
    ds_id = req("GET", f"/databases/{DB_ID}")["data_sources"][0]["id"]
    res = req("POST", f"/data_sources/{ds_id}/query", {
        "filter": {"property": "Due Date", "date": {"equals": target}},
        "page_size": 1,
    })["results"]
    if res:
        print(res[0]["id"].replace("-", ""))
        sys.exit(0)
    # 평일 일지는 Notion 반복 템플릿이 00:00에 만든다. 주말처럼 없는 날만 여기서 만든다.
    # 제목·Due Date는 반복 템플릿이 만든 페이지와 같은 형식(날짜 mention + " 업무 일지")으로 채우고,
    # 본문은 DB 기본 템플릿(@Today 업무 일지)을 적용한다.
    page = req("POST", "/pages", {
        "parent": {"type": "data_source_id", "data_source_id": ds_id},
        "template": {"type": "default"},
        "properties": {
            "이름": {"title": [
                {"type": "mention", "mention": {"type": "date", "date": {"start": target}}},
                {"type": "text", "text": {"content": " 업무 일지"}},
            ]},
            "Due Date": {"date": {"start": target}},
        },
    })
    print("NEW " + page["id"].replace("-", ""))
except urllib.error.HTTPError as e:
    print(f"ERR HTTP {e.code}")
except Exception as e:
    print(f"ERR {type(e).__name__}")
PY
)

if [[ "$page_id" == ERR* ]]; then
  echo "Notion 요청 실패: ${page_id#ERR }"
  exit 1
fi
if [[ -z "$page_id" ]]; then
  echo "Notion 응답이 비었습니다"
  exit 1
fi
msg="$target 업무 일지를 엽니다"
if [[ "$page_id" == NEW* ]]; then
  page_id="${page_id#NEW }"
  msg="$target 업무 일지를 만들어 엽니다"
fi

# Notion 데스크톱 앱은 notion:// 링크를 지금 보고 있는 탭이 아니라 원래 탭에 열어 그 탭을 덮어쓴다(2026-11-26 확인).
# 새 탭 URL 파라미터도 없어서 Chrome으로 연다. Chrome은 외부에서 넘어온 URL을 새 탭에 연다.
open -a "Google Chrome" "https://www.notion.so/$page_id"
echo "$msg"
