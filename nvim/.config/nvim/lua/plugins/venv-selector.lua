return {
  "linux-cultist/venv-selector.nvim",
  dependencies = {
    "neovim/nvim-lspconfig",
    "mfussenegger/nvim-dap",
    "mfussenegger/nvim-dap-python",
  },
  ft = "python", -- 파이썬 파일이 열릴 때만 로드
  branch = "regexp", -- 최신 기능을 위해 이 브랜치를 명시하는 것이 가장 안전합니다.
  keys = {
    { "<leader>v", "<cmd>VenvSelect<cr>" },
  },
  config = function()
    require("venv-selector").setup({
      options = {
        notify_user_on_venv_activation = true,
      },
    })
  end,
}