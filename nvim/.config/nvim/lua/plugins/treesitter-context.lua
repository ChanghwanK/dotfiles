return {
  "nvim-treesitter/nvim-treesitter-context",
  event = "BufReadPost",
  opts = {
    max_lines = 3,           -- 최대 3줄까지 컨텍스트 표시
    min_window_height = 20,  -- 창이 충분히 클 때만 표시
    multiline_threshold = 1, -- 멀티라인 노드는 1줄로 축약
    trim_scope = "outer",    -- 바깥 스코프부터 잘라냄
  },
  keys = {
    {
      "<leader>ct",
      function() require("treesitter-context").toggle() end,
      desc = "Treesitter Context 토글",
    },
    {
      "[c",
      function() require("treesitter-context").go_to_context(vim.v.count1) end,
      desc = "상위 컨텍스트로 이동",
    },
  },
}
