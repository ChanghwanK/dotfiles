return {
  "MagicDuck/grug-far.nvim",
  cmd = "GrugFar",
  keys = {
    {
      "<leader>sr",
      function()
        require("grug-far").open({ prefills = { search = vim.fn.expand("<cword>") } })
      end,
      mode = { "n" },
      desc = "프로젝트 전체 검색/교체 (커서 단어)",
    },
    {
      "<leader>sr",
      function()
        require("grug-far").with_visual_selection()
      end,
      mode = { "v" },
      desc = "프로젝트 전체 검색/교체 (선택 영역)",
    },
    {
      "<leader>sR",
      function()
        require("grug-far").open()
      end,
      mode = { "n" },
      desc = "프로젝트 전체 검색/교체 (빈 상태)",
    },
  },
  opts = {
    headerMaxWidth = 80,
  },
}
