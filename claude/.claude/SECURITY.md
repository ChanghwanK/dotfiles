# MCP Token Security

Claude Code MCP 서버들의 토큰은 **macOS Keychain**에 저장됩니다.
각 wrapper 스크립트는 Keychain을 우선 조회하고, 실패 시 1Password를 fallback으로 사용합니다.

## 아키텍처

```
wrapper 스크립트
  └─ security find-generic-password  ──→ macOS Keychain (주 저장소)
       실패 시 fallback
  └─ op read                         ──→ 1Password (백업 / 복구용)
```

**원칙:**
- 토큰은 config 파일(mcp.json 등)에 절대 하드코딩하지 않는다
- Keychain은 `-T ""` 플래그로 저장 → 앱 제한 없이 CLI 접근 허용
- 1Password는 원본 토큰 보관소 역할 (Keychain 분실 시 복구 경로)

---

## 등록된 토큰 목록

모든 항목의 account name: `claude-mcp`

| service name              | 용도                   | 1Password 항목                              |
|---------------------------|------------------------|---------------------------------------------|
| `grafana-token`           | Grafana MCP 서버       | `op://Employee/Claude MCP - Grafana/token`  |
| `slack-token`             | Slack MCP + 알림 스크립트 | `op://Employee/Claude MCP - Slack/token` |
| `github-token`            | GitHub MCP 서버        | `op://Employee/Claude Desktop - GitHub PAT/token` |
| `notion-personal-token`   | Notion MCP 서버        | `op://Employee/Claude MCP - Notion-Personal/token` |

---

## 토큰 관리 명령어

### 조회

```bash
# 특정 토큰 값 확인
security find-generic-password -a "claude-mcp" -s "slack-token" -w

# 등록된 모든 claude-mcp 항목 동적 나열 (하드코딩 없이 Keychain 전체 스캔)
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

### 추가 (신규 토큰)

토큰 값을 직접 입력받아 **Keychain과 1Password에 동시에 저장**한다.

```bash
# 1) Keychain 저장
security add-generic-password \
  -a "claude-mcp" \
  -s "<service-name>" \
  -w "<token-value>" \
  -T ""

# 2) 1Password 저장 (신규 항목)
op item create \
  --category "API Credential" \
  --title "Claude MCP - <Service>" \
  --vault "Employee" \
  "token[password]=<token-value>"

# 2-b) 이미 1Password 항목이 존재하는 경우
op item edit "Claude MCP - <Service>" --vault "Employee" "token[password]=<token-value>"
```

- `-T ""`: 모든 앱/CLI 접근 허용 (필수)

### 업데이트 (토큰 교체)

`-U` 플래그로 기존 항목을 덮어씁니다.

```bash
security add-generic-password -a "claude-mcp" -s "slack-token" \
  -w "NEW_TOKEN_VALUE" -T "" -U
```

**1Password에서 최신 값으로 동기화:**
```bash
security add-generic-password -a "claude-mcp" -s "slack-token" \
  -w "$(op read 'op://Employee/Claude MCP - Slack/token')" -T "" -U
```

**전체 토큰 일괄 재동기화:**
```bash
security add-generic-password -a "claude-mcp" -s "grafana-token" \
  -w "$(op read 'op://Employee/Claude MCP - Grafana/token')" -T "" -U

security add-generic-password -a "claude-mcp" -s "slack-token" \
  -w "$(op read 'op://Employee/Claude MCP - Slack/token')" -T "" -U

security add-generic-password -a "claude-mcp" -s "github-token" \
  -w "$(op read 'op://Employee/Claude Desktop - GitHub PAT/token')" -T "" -U

security add-generic-password -a "claude-mcp" -s "notion-personal-token" \
  -w "$(op read 'op://Employee/Claude MCP - Notion-Personal/token')" -T "" -U
```

### 삭제

```bash
security delete-generic-password -a "claude-mcp" -s "slack-token"
```

---

## 새 MCP 서버 추가 체크리스트

새 MCP wrapper 스크립트를 만들 때 따를 패턴:

**1. 1Password에 토큰 저장** (없으면 신규 생성)

**2. Keychain에 등록**
```bash
security add-generic-password -a "claude-mcp" -s "<service>-token" \
  -w "$(op read 'op://Employee/<1pw-item>/token')" -T ""
```

**3. wrapper 스크립트 작성** (`~/.claude/bin/mcp-<service>.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

export MY_SERVICE_TOKEN
MY_SERVICE_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "<service>-token" -w 2>/dev/null \
  || op read "op://Employee/<1pw-item>/token"
)

exec npx -y @modelcontextprotocol/server-<service>
```

**4. 이 문서의 토큰 목록 테이블에 행 추가**

**5. `~/.claude.json` `mcpServers`에 서버 등록**

`~/.claude.json`의 `mcpServers` 섹션에 직접 추가한다 (`~/.claude/mcp.json`은 Claude Code가 읽지 않음):
```json
"<service>": {
  "type": "stdio",
  "command": "/Users/changhwan/.claude/scripts/mcp-<service>.sh"
}
```

---

## 트러블슈팅

**Keychain 항목이 있는데도 1Password 프롬프트가 뜨는 경우**

Keychain 항목이 특정 앱에만 허용되도록 등록된 것일 수 있습니다.
삭제 후 `-T ""`를 명시하여 재등록합니다:

```bash
security delete-generic-password -a "claude-mcp" -s "slack-token"
security add-generic-password -a "claude-mcp" -s "slack-token" -w "TOKEN" -T ""
```

**토큰 값을 잃어버린 경우**

1Password가 원본 저장소이므로 거기서 복구합니다:
```bash
op read "op://Employee/Claude MCP - Slack/token"
```
