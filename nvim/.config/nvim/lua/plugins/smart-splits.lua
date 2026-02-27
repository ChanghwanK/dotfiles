return {
    "mrjones2014/smart-splits.nvim",
    lazy = false, -- 창 이동은 자주 쓰이므로 즉시 로딩 추천
    config = function()
      require("smart-splits").setup({
        -- 기본 설정 (필요에 따라 수정 가능)
        ignored_filetypes = {
          "nofile",
          "quickfix",
          "prompt",
        },
        ignored_buftypes = { "nofile" },
      })
    end,
  }