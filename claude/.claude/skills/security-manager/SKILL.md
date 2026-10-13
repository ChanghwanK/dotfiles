---
name: security-manager
description: |
  macOS Keychain 기반 MCP 토큰 관리 스킬.
  토큰 추가/조회/업데이트/삭제, 1Password 동기화, 신규 MCP 서버 온보딩을 수행한다.
  사용 시점: (1) MCP 토큰 등록/교체/삭제, (2) Keychain 상태 확인,
  (3) 신규 MCP 서버 온보딩, (4) 전체 토큰 재동기화.
  트리거 키워드: "토큰 추가", "토큰 교체", "토큰 삭제", "Keychain 확인",
  "MCP 서버 추가", "token rotate", "1Password 동기화", "credential 관리",
  "/security-manager".
model: sonnet
allowed-tools:
  - Bash(security *)
  - Bash(op *)
  - Bash(bash /Users/changhwan/.claude/skills/security-manager/scripts/keychain-manager.sh *)
---

# Security Manager

MCP 서버 토큰은 macOS Keychain에 저장된다. 모든 항목은 account=`claude-mcp` 공유, service name으로 구분.
전체 명세: `~/.claude/SECURITY.md`

## 등록된 토큰 목록

| service name            | 사용처                         | 1Password 경로 |
|-------------------------|-------------------------------|----------------|
| `grafana-token`         | mcp-grafana.sh                | `op://Employee/Claude MCP - Grafana/token` |
| `slack-token`           | mcp-slack.sh, notify-slack.sh | `op://Employee/Claude MCP - Slack/token` |
| `github-token`          | mcp-github.sh                 | `op://Employee/Claude Desktop - GitHub PAT/token` |
| `notion-personal-token` | mcp-notion-personal.sh        | `op://Employee/Claude MCP - Notion-Personal/token` |

## 명령어

### 조회 (list)
Keychain에서 account=`claude-mcp`인 **모든 항목**을 동적으로 나열한다 (하드코딩 목록 아님):
```bash
security dump-keychain 2>/dev/null | python3 -c "
import sys, re
blocks = re.split(r'(?=keychain: )', sys.stdin.read())
seen = set()
for block in blocks:
    if '\"claude-mcp\"' in block:
        m = re.search(r'\"svce\"<blob>=\"([^\"]+)\"', block)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            print('  ' + m.group(1))
" | sort
```

### 존재 확인 (show \<service\>)
토큰 문자는 한 글자도 출력하지 않는다. `-w` 없이 조회해 항목 존재와 메타데이터(service, account, 생성·수정 시각)만 확인한다:
```bash
security find-generic-password -a "claude-mcp" -s "<service>-token"
```

### 추가 (add \<service\>)
토큰 값은 채팅에 붙여넣게 하지 않는다. 값이 채팅·명령 인자에 나타나지 않는 경로만 쓴다.

먼저 사용자에게 service name(예: `newservice-token`)과 토큰이 이미 1Password에 있는지만 확인한다.

**A. 토큰이 이미 1Password에 있는 경우**: 업데이트·rotate와 같이 `op read` 명령 치환으로 Claude가 실행한다:
```bash
security add-generic-password -a "claude-mcp" -s "<service>-token" \
  -w "$(op read 'op://Employee/<1pw-item>/token')" -T "" -U
```

**B. 토큰이 1Password에 없는 경우**: 아래 명령을 사용자에게 안내하고 사용자가 자기 터미널에서 직접 실행하게 한다 (Claude가 실행하지 않는다):
```bash
# 1) Keychain 저장: -w를 마지막에 값 없이 두면 security가 토큰을 대화형으로 묻는다 (화면·셸 히스토리에 남지 않음)
security add-generic-password -a "claude-mcp" -s "<service>-token" -T "" -U -w

# 2) 1Password 저장: Keychain에 넣은 값을 명령 치환으로 읽어 신규 항목 생성
op item create \
  --category "API Credential" \
  --title "Claude MCP - <Service>" \
  --vault "Employee" \
  "token[password]=$(security find-generic-password -a 'claude-mcp' -s '<service>-token' -w)"
```

1Password 항목이 이미 존재하는 경우 2)의 create 대신:
```bash
op item edit "Claude MCP - <Service>" --vault "Employee" \
  "token[password]=$(security find-generic-password -a 'claude-mcp' -s '<service>-token' -w)"
```

사용자가 실행을 마쳤다고 하면 "존재 확인(show)"으로 등록 여부만 확인한다. 저장 완료 후 `~/.claude/SECURITY.md` 토큰 목록 테이블에 행 추가.

### 업데이트 (update \<service\>)
```bash
security add-generic-password -a "claude-mcp" -s "<service>-token" \
  -w "$(op read 'op://Employee/<1pw-item>/token')" -T "" -U
```
실행 전 어떤 1Password 항목을 사용할지 사용자에게 확인.

### 전체 재동기화 (rotate-all)
아래 "전체 재동기화 (rotate-all): 스크립트 사용" 절의 `keychain-manager.sh rotate-all`을 쓴다.

### 삭제 (delete \<service\>)
```bash
security delete-generic-password -a "claude-mcp" -s "<service>-token"
```
삭제 전 사용자에게 한 번 확인.

## 신규 MCP 서버 온보딩 (new-mcp \<service\>)

1. **Keychain 등록**
```bash
security add-generic-password -a "claude-mcp" -s "<service>-token" \
  -w "$(op read 'op://Employee/<1pw-item>/token')" -T ""
```

2. **Wrapper 스크립트 생성** (`~/.claude/scripts/mcp-<service>.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail
export MY_TOKEN
MY_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "<service>-token" -w 2>/dev/null \
  || op read "op://Employee/<1pw-item>/token"
)
exec npx -y @modelcontextprotocol/server-<service>
```
```bash
chmod +x ~/.claude/scripts/mcp-<service>.sh
```

3. **`~/.claude.json` `mcpServers` 등록**

`~/.claude.json`의 `mcpServers` 섹션에 직접 추가한다:
```json
"<service>": {
  "type": "stdio",
  "command": "/Users/changhwan/.claude/scripts/mcp-<service>.sh"
}
```

4. **`~/.claude/SECURITY.md` 토큰 목록 업데이트**

### 전체 재동기화 (rotate-all): 스크립트 사용
```bash
bash /Users/changhwan/.claude/skills/security-manager/scripts/keychain-manager.sh rotate-all
```

## 원칙
- `-T ""` 필수: 없으면 매번 GUI 프롬프트 발생
- `-U` = upsert (없으면 추가, 있으면 덮어씀)
- 작업 완료 후 변경 내용 한 줄 요약 보고

---

## 검증

각 작업 완료 후 결과를 반드시 확인한다.

```bash
# 토큰 저장 확인 (값은 출력하지 않고 존재·메타데이터만 확인)
security find-generic-password -a "claude-mcp" -s "<service>-token"
```

실패 시:
- `SecKeychainItemCopyAttributesAndData` 에러 → `-T ""` 옵션 확인
- `op read` 실패 → `op signin` 으로 1Password 인증 확인
- 토큰 없음 (exit 44) → service name 오타 확인 (`<service>-token` 형식)
