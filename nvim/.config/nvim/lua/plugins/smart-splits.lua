return {
    "mrjones2014/smart-splits.nvim",
    lazy = false, -- 창 이동은 자주 쓰이므로 즉시 로딩 추천
    config = function()
      require("smart-splits").setup({
        ignored_filetypes = {
          "nofile",
          "quickfix",
          "prompt",
        },
        ignored_buftypes = { "nofile" },
        -- tmux pane ↔ neovim split 통합 이동
        multiplexer_integration = "tmux",
      })
    end,
  }