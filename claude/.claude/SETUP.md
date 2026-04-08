# Claude Code 환경 세팅 가이드

새 머신이나 재설치 시 Claude Code 환경을 재현하기 위한 가이드.
`~/.dotfiles`에서 `claude` 패키지를 제외했으므로 이 문서를 따라 수동 설정.

---

## 1. 사전 준비 (brew 패키지)

```bash
brew install git gh curl python3 kubectl
brew install 1password-cli   # op CLI
brew install podman          # Grafana MCP용 (Docker 대신 사용)
```

1Password CLI 인증:
```bash
op signin
```

---

## 2. Claude Code 설치 및 인증

```bash
npm install -g @anthropic-ai/claude-code
claude login
```

---

## 3. ~/.claude/settings.json

아래 내용으로 생성. `/Users/changhwan/` → 새 머신 username으로 치환.

```json
{
  "env": {
    "ENABLE_TOOL_SEARCH": "auto:5"
  },
  "permissions": {
    "allow": [
      "Bash(kubectl config use-context:*)",
      "Bash(/Users/<USER>/.claude/scripts/notify-slack.sh *)"
    ]
  },
  "model": "opusplan",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "cmd=$(cat | python3 -c \"import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))\"); if printf '%s' \"$cmd\" | grep -qE 'kubectl[[:space:]]+(edit|delete)'; then printf 'BLOCKED: kubectl edit/delete bypasses GitOps and will be reverted by ArgoCD. Modify YAML files in Git instead.\\n' >&2; exit 2; fi"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/<USER>/.claude/scripts/notify-on-stop.sh"
          }
        ]
      }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "python3 /Users/<USER>/.claude/statusline.py"
  },
  "enabledPlugins": {
    "helm-chart@socraai-devops-skills": true,
    "istio-troubleshooting@socraai-devops-skills": true,
    "example-skills@anthropic-agent-skills": true,
    "pod-crash@socraai-devops-skills": true,
    "socra-infra-design@socraai-devops-skills": true,
    "claude-mem@thedotmack": true
  },
  "skipDangerousModePermissionPrompt": true
}
```

---

## 4. ~/.claude.json (mcpServers 섹션)

Claude Code MCP 서버 설정은 `~/.claude.json`의 `mcpServers` 필드에 직접 추가한다.
(`~/.claude/mcp.json`은 Claude Code가 읽지 않으므로 사용하지 않음)

`~/.claude.json`을 열어 `mcpServers` 키 하위에 아래 서버들을 추가:

```json
"grafana": {
  "type": "stdio",
  "command": "/Users/<USER>/.claude/scripts/mcp-grafana.sh"
},
"slack": {
  "type": "stdio",
  "command": "/Users/<USER>/.claude/scripts/mcp-slack.sh"
},
"github": {
  "type": "stdio",
  "command": "/Users/<USER>/.claude/scripts/mcp-github.sh"
},
"notion-personal": {
  "type": "stdio",
  "command": "/Users/<USER>/.claude/scripts/mcp-notion-personal.sh"
}
```

---

## 5. macOS Keychain 토큰 등록

각 MCP 서버 토큰을 1Password에서 읽어 Keychain에 등록.
Wrapper 스크립트는 Keychain 우선 조회, 실패 시 1Password로 fallback.

```bash
# Grafana
security add-generic-password -a "claude-mcp" -s "grafana-token" \
  -w "$(op read 'op://Employee/Claude MCP - Grafana/token')" -T ""

# Slack
security add-generic-password -a "claude-mcp" -s "slack-token" \
  -w "$(op read 'op://Employee/Claude MCP - Slack/token')" -T ""

# GitHub
security add-generic-password -a "claude-mcp" -s "github-token" \
  -w "$(op read 'op://Employee/Claude Desktop - GitHub PAT/token')" -T ""

# Notion (Personal)
security add-generic-password -a "claude-mcp" -s "notion-personal-token" \
  -w "$(op read 'op://Employee/Claude MCP - Notion-Personal/token')" -T ""
```

| 서비스 | Keychain service ID | 1Password 경로 |
|--------|---------------------|----------------|
| Grafana | `grafana-token` | `op://Employee/Claude MCP - Grafana/token` |
| Slack | `slack-token` | `op://Employee/Claude MCP - Slack/token` |
| GitHub | `github-token` | `op://Employee/Claude Desktop - GitHub PAT/token` |
| Notion | `notion-personal-token` | `op://Employee/Claude MCP - Notion-Personal/token` |

모든 항목의 account name: `claude-mcp`

---

## 6. Claude Desktop MCP 설정

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "awslabs.aws-api-mcp-server": {
      "command": "uvx",
      "args": ["awslabs.aws-api-mcp-server@latest"],
      "env": {
        "AWS_REGION": "ap-northeast-1",
        "AWS_API_MCP_PROFILE_NAME": "okta-devops",
        "READ_OPERATIONS_ONLY": "true"
      }
    },
    "victoriametrics-prod": {
      "command": "/Users/<USER>/go/bin/mcp-victoriametrics",
      "env": {
        "VM_INSTANCE_ENTRYPOINT": "https://metrics.prod.riiid.team",
        "VM_INSTANCE_TYPE": "single"
      }
    },
    "awslabs.eks-mcp-server": {
      "command": "uvx",
      "args": ["awslabs.eks-mcp-server@latest", "--allow-sensitive-data-access"],
      "env": {
        "AWS_PROFILE": "okta-devops",
        "AWS_REGION": "ap-northeast-1"
      }
    },
    "github": {
      "command": "/Users/<USER>/.claude/scripts/mcp-github.sh"
    },
    "awslabs.aws-network-mcp-server": {
      "command": "uvx",
      "args": ["awslabs.aws-network-mcp-server@latest"],
      "env": {
        "AWS_PROFILE": "okta-devops",
        "AWS_REGION": "ap-northeast-1"
      }
    }
  },
  "preferences": {
    "quickEntryShortcut": "off",
    "menuBarEnabled": false
  }
}
```

**VictoriaMetrics 바이너리 빌드** (Go 필요):
```bash
go install github.com/victoriametrics/mcp-victoriametrics@latest
```

---

## 7. scripts/ 디렉토리 배포

`~/.claude/scripts/`는 dotfiles에서 관리하지 않으므로 직접 복사 또는 재생성.

### Wrapper 스크립트 구조

각 스크립트는 동일한 패턴: Keychain 우선 → 1Password fallback

**mcp-grafana.sh**:
```bash
#!/usr/bin/env bash
set -euo pipefail
export GRAFANA_URL="https://riiid.grafana.net/"
export GRAFANA_SERVICE_ACCOUNT_TOKEN
GRAFANA_SERVICE_ACCOUNT_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "grafana-token" -w 2>/dev/null \
  || op read "op://Employee/Claude MCP - Grafana/token"
)
exec podman run --rm -i \
  -e GRAFANA_URL \
  -e GRAFANA_SERVICE_ACCOUNT_TOKEN \
  docker.io/grafana/mcp-grafana \
  -transport stdio
```

**mcp-slack.sh**:
```bash
#!/usr/bin/env bash
set -euo pipefail
export SLACK_BOT_TOKEN
export SLACK_TEAM_ID="T02PSFS4G"
SLACK_BOT_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "slack-token" -w 2>/dev/null \
  || op read "op://Employee/Claude MCP - Slack/token"
)
exec npx -y @modelcontextprotocol/server-slack
```

**mcp-github.sh**:
```bash
#!/usr/bin/env bash
set -euo pipefail
export GITHUB_PERSONAL_ACCESS_TOKEN
GITHUB_PERSONAL_ACCESS_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "github-token" -w 2>/dev/null \
  || op read "op://Employee/Claude Desktop - GitHub PAT/token"
)
exec npx -y @modelcontextprotocol/server-github
```

**mcp-notion-personal.sh**:
```bash
#!/usr/bin/env bash
set -euo pipefail
NOTION_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "notion-personal-token" -w 2>/dev/null \
  || op read "op://Employee/Claude MCP - Notion-Personal/token"
)
export OPENAPI_MCP_HEADERS="{\"Authorization\": \"Bearer ${NOTION_TOKEN}\", \"Notion-Version\": \"2022-06-28\"}"
exec npx -y @notionhq/notion-mcp-server
```

스크립트 생성 후 실행 권한 부여:
```bash
chmod +x ~/.claude/scripts/mcp-*.sh
```

### Slack 알림 활성화

```bash
touch ~/.claude/scripts/.notify-enabled
```

비활성화: `rm ~/.claude/scripts/.notify-enabled`

---

## 8. 플러그인 설치

```bash
claude plugins install helm-chart@socraai-devops-skills
claude plugins install istio-troubleshooting@socraai-devops-skills
claude plugins install pod-crash@socraai-devops-skills
claude plugins install socra-infra-design@socraai-devops-skills
claude plugins install example-skills@anthropic-agent-skills
claude plugins install claude-mem@thedotmack
```

---

## 9. 개인화 필요 항목

새 머신 세팅 시 변경이 필요한 하드코딩된 값들:

| 항목 | 현재 값 | 변경 방법 |
|------|---------|-----------|
| 경로 prefix | `/Users/changhwan/` | 새 username으로 전체 치환 |
| Slack 수신자 ID | `U098T8A1XL0` | notify-on-stop.sh, notify-slack.sh 수정 |
| Slack Team ID | `T02PSFS4G` | mcp-slack.sh 수정 |
| Grafana URL | `https://riiid.grafana.net/` | mcp-grafana.sh 수정 |
| AWS 프로파일 | `okta-devops` | Desktop config env 수정 |
| VictoriaMetrics URL | `https://metrics.prod.riiid.team` | Desktop config env 수정 |

---

## 10. 검증 체크리스트

```bash
# Claude Code 버전 확인
claude --version

# MCP 서버 연결 확인 (Claude Code 내에서)
# /mcp

# Git 설정 확인
git config user.name
git config user.email

# Grafana 쿼리 테스트 (Claude 세션에서)
# "Grafana에서 현재 알림 목록 보여줘"

# Slack 알림 테스트
~/.claude/scripts/notify-slack.sh "세팅 완료 테스트"
```

- [ ] `claude --version` 출력 확인
- [ ] `/mcp` → Grafana, Slack 연결 확인
- [ ] Claude Desktop → GitHub, AWS, EKS MCP 연결 확인
- [ ] Grafana 쿼리 테스트 성공
- [ ] Slack 알림 수신 확인 (changhwan DM)
- [ ] kubectl PreToolUse hook 동작 확인 (`kubectl delete` 시 BLOCKED 메시지)
- [ ] statusline.py 비용 표시 확인

---

## 참조

- `~/.claude/settings.json` — Claude Code 메인 설정
- `~/.claude.json` (`mcpServers` 섹션) — Claude Code MCP 서버
- `~/.claude/scripts/` — MCP wrapper 및 시스템 스크립트
- `~/Library/Application Support/Claude/claude_desktop_config.json` — Claude Desktop MCP
- `~/.dotfiles/` — GNU Stow dotfiles 레포 (claude 제외)
