#!/usr/bin/env bash
# Claude Code Stop hook — 일반 프롬프트로 출력된 플랜을 읽기 전용 HTML로 브라우저에 띄운다.
#
# 배경: 브라우저 프리뷰의 정식 경로는 PreToolUse(ExitPlanMode) 훅(plan-preview.sh)이다.
#       그러나 plan mode가 아닌 일반 프롬프트("plan 설계해줘")로 요청하면 모델은 플랜을
#       assistant 텍스트로만 출력하고 ExitPlanMode 툴을 호출하지 않아 프리뷰가 안 뜬다.
#       이 훅은 그 빈틈을 메운다.
#
# 한계: plan mode 밖에는 "승인 게이트"가 없다. 모델은 이미 턴을 끝냈으므로 승인/거부할
#       대상이 없다. 따라서 여기서 띄우는 것은 Approve/Reject 버튼이 아니라 읽기 전용 뷰어다.
#
# 비활성화: settings.json의 Stop 훅 배열에서 이 스크립트 라인을 제거하면 즉시 원복된다.

INPUT=$(cat)

# 재귀 호출 방지 (Stop 훅이 자기 자신을 트리거하는 루프 차단)
ACTIVE=$(printf '%s' "$INPUT" | python3 -c \
  'import sys,json; print(json.load(sys.stdin).get("stop_hook_active", False))' 2>/dev/null)
[ "$ACTIVE" = "True" ] && exit 0

TRANSCRIPT=$(printf '%s' "$INPUT" | python3 -c \
  'import sys,json; print(json.load(sys.stdin).get("transcript_path",""))' 2>/dev/null)
[ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ] && exit 0

# 마지막 assistant 메시지를 읽어 plan-format.md 템플릿 구조이면 그 텍스트를 출력한다.
# 오탐 억제를 위해 사용자 템플릿 고유 마커 2개(## Summary + ## Steps|스텝별)를 모두 요구한다.
PLAN=$(python3 - "$TRANSCRIPT" <<'PYEOF'
import json, sys, re

last_text = ""
with open(sys.argv[1]) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "assistant":
            continue
        content = d.get("message", {}).get("content", "")
        if isinstance(content, list):
            text = "\n".join(
                c.get("text", "") for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            )
        else:
            text = str(content)
        if text.strip():
            last_text = text  # 마지막 assistant 텍스트만 유지

has_summary = re.search(r'(?m)^##\s+Summary', last_text) is not None
has_steps = re.search(r'(?m)^##\s+(Steps|스텝별)', last_text) is not None
if has_summary and has_steps:
    sys.stdout.write(last_text)
PYEOF
2>/dev/null)

[ -z "$PLAN" ] && exit 0

# 중복 오픈 방지 — 동일 플랜이 다음 턴에도 마지막 메시지로 남아 재오픈되는 것을 막는다.
HASH=$(printf '%s' "$PLAN" | shasum | awk '{print $1}')
HASH_FILE="/tmp/claude-plan-text-preview.hash"
[ -f "$HASH_FILE" ] && [ "$(cat "$HASH_FILE" 2>/dev/null)" = "$HASH" ] && exit 0
printf '%s' "$HASH" > "$HASH_FILE"

# md → html 변환 후 브라우저 오픈 (읽기 전용, 승인 버튼 없음)
PREVIEW_MD="/tmp/claude-plan-text-preview.md"
printf '%s' "$PLAN" > "$PREVIEW_MD"

HTML=$(python3 -c "import importlib.util; \
spec=importlib.util.spec_from_file_location('p','${HOME}/.claude/scripts/plan-to-html.py'); \
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print(m.convert('$PREVIEW_MD'))" \
  2>/dev/null)

[ -n "$HTML" ] && [ -f "$HTML" ] && open "$HTML" >/dev/null 2>&1

exit 0
