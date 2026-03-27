return {
  "romgrk/barbar.nvim",
  event = "VeryLazy",
  dependencies = {
    "nvim-tree/nvim-web-devicons",
    "lewis6991/gitsigns.nvim",
  },
  init = function()
    vim.g.barbar_auto_setup = false
  end,
  config = function(_, opts)
    require("barbar").setup(opts)
    local function set_hl()
      local hl = vim.api.nvim_set_hl
      -- 활성 탭
      hl(0, "BufferCurrent",         { fg = "#e5e9f0", bg = "#1b2230", bold = true })
      hl(0, "BufferCurrentSign",     { fg = "#88c0d0", bg = "#1b2230" })
      hl(0, "BufferCurrentMod",      { fg = "#e5c07b", bg = "#1b2230", bold = true })
      hl(0, "BufferCurrentAdded",    { fg = "#a3be8c", bg = "#1b2230" })
      hl(0, "BufferCurrentChanged",  { fg = "#ebcb8b", bg = "#1b2230" })
      hl(0, "BufferCurrentDeleted",  { fg = "#bf616a", bg = "#1b2230" })
      -- 비활성 탭
      hl(0, "BufferInactive",        { fg = "#6b7280", bg = "#11151c" })
      hl(0, "BufferInactiveSign",    { fg = "#3b4252", bg = "#11151c" })
      hl(0, "BufferInactiveMod",     { fg = "#6b7280", bg = "#11151c" })
      hl(0, "BufferInactiveAdded",   { fg = "#4b5a40", bg = "#11151c" })
      hl(0, "BufferInactiveChanged", { fg = "#5a5030", bg = "#11151c" })
      hl(0, "BufferInactiveDeleted", { fg = "#5a3535", bg = "#11151c" })
      -- 빈 영역
      hl(0, "BufferTabpageFill",     { bg = "#0f1115" })
    end
    set_hl()
    vim.api.nvim_create_autocmd("ColorScheme", { callback = set_hl })
  end,
  opts = {
    auto_hide = false,
    icons = {
      preset = "default",
      separator = { left = "▎", right = "" },
      separator_at_end = true,
      buffer_index = false,
      buffer_number = false,
      button = "×",
      gitsigns = {
        added   = { enabled = true, icon = "+" },
        changed = { enabled = true, icon = "~" },
        deleted = { enabled = true, icon = "-" },
      },
      modified = { button = "●" },
      filetype = { enabled = true },
    },
    highlight_alternate = true,
    highlight_inactive_file_icons = false,
  },
}
