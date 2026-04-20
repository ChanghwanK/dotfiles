return {
  "smjonas/inc-rename.nvim",
  cmd = "IncRename",
  config = function()
    require("inc_rename").setup({
      input_buffer_type = "snacks", -- Snacks.input UI 사용
    })
  end,
}
