return {
  "coder/claudecode.nvim",
  dependencies = { "folke/snacks.nvim" },
  config = function(_, opts)
    require("claudecode").setup(opts)
    -- Snacks 터미널에서 Shift+Enter → 줄바꿈(\n) 전달
    vim.api.nvim_create_autocmd("TermOpen", {
      callback = function()
        local opts = { buffer = true, nowait = true }
        vim.keymap.set("t", "<S-CR>", "\n", opts)
        -- Warp: kitty keyboard protocol raw sequence for Shift+Enter
        vim.keymap.set("t", "\x1b[13;2u", "\n", opts)
      end,
    })
  end,
  -- 옵션 설정을 통해 터미널 크기, 위치, Diff 동작 등을 제어할 수 있습니다.
  opts = {
    -- Server Configuration
    auto_start = true, -- Neovim 시작 시 자동으로 서버 시작 여부
    -- terminal_cmd = nil, -- 커스텀 claude 명령어 경로가 필요할 경우 설정 (예: "~/.claude/local/claude")

    -- Send/Focus Behavior
    focus_after_send = false, -- 전송 후 터미널로 포커스 이동 여부

    -- Selection Tracking
    track_selection = true, -- 시각적 선택 영역 추적

    -- Terminal Configuration
    terminal = {
      split_side = "right",          -- "left" or "right"
      split_width_percentage = 0.30, -- 터미널 너비 (30%)
      provider = "auto",             -- "auto", "snacks", "native", "external", "none"
      auto_close = true,
      snacks_win_opts = {},          -- Snacks 터미널 옵션 (플로팅 윈도우 등 설정 가능)
    },

    -- Diff Integration
    diff_opts = {
      auto_close_on_accept = true, -- 수락 시 Diff 창 자동 닫기
      vertical_split = true,       -- Diff를 수직 분할로 열기
      open_in_current_tab = true,  -- 현재 탭에서 열기
      keep_terminal_focus = false, -- Diff가 열린 후에도 터미널 포커스 유지 여부
    },
  },
  keys = {
    { "<leader>a",  nil,                              desc = "AI/Claude Code" },
    { "<leader>ac", "<cmd>ClaudeCode<cr>",            desc = "Toggle Claude" },
    { "<leader>af", "<cmd>ClaudeCodeFocus<cr>",       desc = "Focus Claude" },
    { "<leader>ar", "<cmd>ClaudeCode --resume<cr>",   desc = "Resume Claude" },
    { "<leader>aC", "<cmd>ClaudeCode --continue<cr>", desc = "Continue Claude" },
    { "<leader>am", "<cmd>ClaudeCodeSelectModel<cr>", desc = "Select Claude model" },
    { "<leader>ab", "<cmd>ClaudeCodeAdd %<cr>",       desc = "Add current buffer" },
    { "<leader>as", "<cmd>ClaudeCodeSend<cr>",        mode = "v",                  desc = "Send to Claude" },
    {
      "<leader>as",
      "<cmd>ClaudeCodeTreeAdd<cr>",
      desc = "Add file",
      ft = { "NvimTree", "neo-tree", "oil", "minifiles", "netrw" },
    },
    -- Diff management
    { "<leader>aa", "<cmd>ClaudeCodeDiffAccept<cr>", desc = "Accept diff" },
    { "<leader>ad", "<cmd>ClaudeCodeDiffDeny<cr>",   desc = "Deny diff" },
  },
}
