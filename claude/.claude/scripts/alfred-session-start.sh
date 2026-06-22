#!/usr/bin/env bash
# alfred-session-start.sh — SessionStart hook
#
# alfred-state.json을 읽어 현재 진행 Task를 세션 컨텍스트에 주입한다.
# TUI에서 Task를 선택해 세션을 연 경우: state 파일에 정확한 Task 정보가 있음.
# 직접 세션을 연 경우: state 파일이 없거나 오래됐으면 감지 불가로 표시.
#
# 출력 포맷: Claude Code SessionStart hook JSON
#   suppressOutput=false  → Claude가 reason 메시지를 컨텍스트로 읽음
#   suppressOutput=true   → 조용히 통과

STATE="$HOME/.claude/alfred-state.json"
MAX_AGE_HOURS=8  # state 파일이 이 시간보다 오래됐으면 무효로 간주

if [ ! -f "$STATE" ]; then
  printf '{"continue":true,"suppressOutput":true,"status":"no-active-task"}\n'
  exit 0
fi

# state 파일 유효성 검사 (MAX_AGE_HOURS 이내)
python3 - <<PYEOF
import json, datetime, sys, os

try:
    state = json.load(open('$STATE'))
    task = state.get('current_task', {})
    name = task.get('name', '')
    priority = task.get('priority', '')
    started_at = task.get('started_at', '')
    source = task.get('source', '')

    if not name or not started_at:
        print('{"continue":true,"suppressOutput":true,"status":"invalid-state"}')
        sys.exit(0)

    # 경과 시간 체크
    started = datetime.datetime.fromisoformat(started_at)
    elapsed = (datetime.datetime.now().astimezone() - started).total_seconds() / 3600
    if elapsed > $MAX_AGE_HOURS:
        # 오래된 state — 조용히 통과 (완료됐거나 다른 작업일 가능성)
        print('{"continue":true,"suppressOutput":true,"status":"stale-state"}')
        sys.exit(0)

    prio_str = f' ({priority})' if priority else ''
    msg = f'현재 진행 Task: {name}{prio_str}  [source: {source}, {elapsed:.0f}h ago]'
    import json as _json
    print(_json.dumps({"continue": True, "suppressOutput": False, "status": msg}))

except Exception as e:
    print('{"continue":true,"suppressOutput":true,"status":"state-read-error"}')
PYEOF
