# Secrets from Keychain (cached by MCP scripts) → fallback to 1Password
# ${VAR:-...} pattern: 상위 셸에서 상속 시 재조회 생략 (성능)
export NOTION_TOKEN="${NOTION_TOKEN:-$(security find-generic-password -a "claude-mcp" -s "notion-personal-token" -w 2>/dev/null || op read 'op://Employee/Claude MCP - Notion-Personal/token' 2>/dev/null)}"
export GITHUB_MCP_TOKEN="${GITHUB_MCP_TOKEN:-$(security find-generic-password -a "claude-mcp" -s "github-token" -w 2>/dev/null || op read 'op://Employee/Claude Desktop - GitHub PAT/token' 2>/dev/null)}"
export SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:-$(security find-generic-password -a "claude-mcp" -s "slack-token" -w 2>/dev/null || op read 'op://Employee/Claude MCP - Slack/token' 2>/dev/null)}"

# Misc secrets not in 1Password (stored in ~/.secrets.zsh, never committed to git)
[[ -f ~/.secrets.zsh ]] && source ~/.secrets.zsh
export WORKING_HOME="$HOME/workspace/riiid/"
export SOCRA_HELM_CHART_REPO="$WORKING_HOME/kubernetes-charts"
export SOCRA_WEBSERVER_HELM_CHART="$SOCRA_HELM_CHART_REPO/charts/webserver"
export WORKING_VALT_PATH="/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/Engineering/working/"
export VALT_BASE_PATH="/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/"
