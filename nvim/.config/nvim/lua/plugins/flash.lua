return {
  "folke/flash.nvim",
  event = "VeryLazy",
  opts = {
    modes = {
      -- f/F/t/T 동작에 flash 레이블 오버레이 (선택적)
      char = { enabled = false },
    },
  },
  keys = {
    {
      "s",
      mode = { "n", "x", "o" },
      function() require("flash").jump() end,
      desc = "Flash: 화면 내 점프",
    },
    {
      "S",
      mode = { "n", "x", "o" },
      function() require("flash").treesitter() end,
      desc = "Flash: Treesitter 노드 선택",
    },
    {
      "r",
      mode = "o",
      function() require("flash").remote() end,
      desc = "Flash: 원격 조작 (operator pending)",
    },
    {
      "<C-s>",
      mode = { "c" },
      function() require("flash").toggle() end,
      desc = "Flash: 검색 중 토글",
    },
  },
}
