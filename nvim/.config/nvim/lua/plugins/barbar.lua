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
  opts = {
    auto_hide = false,
    icons = {
      preset = "slanted",
      separator_at_end = true,
    },
    sidebar_filetypes = {
      snacks_layout_box = {
        text = "Explorer",
        align = "left",
      },
    },
  },
  config = function(_, opts)
    require("barbar").setup(opts)

  end,
}
