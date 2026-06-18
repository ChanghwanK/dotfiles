-- lua/plugins/bufferline.lua
return {
  "akinsho/bufferline.nvim",
  enabled = true,
  event = "VeryLazy",
  dependencies = { "nvim-tree/nvim-web-devicons" },
  version = "*",
  opts = {
    options = {
      mode = "buffers",
      -- 스타일: "slant" | "slope" | "thick" | "thin" | { 'any', 'any' }
      separator_style = "slope",
      always_show_bufferline = true,

      -- 활성 탭 표시(두꺼운 느낌)
      indicator = { style = "none" },

      offsets = {
        {
          filetype = "snacks_layout_box",
          text = "Explorer",
          highlight = "Directory",
          text_align = "left",
          separator = true,
        },
      },
    },

    highlights = {
      fill = { bg = "#0f1115" },

      -- 비활성 탭
      background        = { fg = "#6b7280", bg = "#11151c" },
      buffer_visible    = { fg = "#9aa4b2", bg = "#11151c" },

      -- 활성 탭: yellow (#b48600)
      buffer_selected    = { fg = "#ffffff", bg = "#b48600", bold = true },
      indicator_selected = { fg = "#b48600", bg = "#b48600" },

      -- separator: fg = 탭 색, bg = fill 색
      separator          = { fg = "#0f1115", bg = "#11151c" },
      separator_visible  = { fg = "#0f1115", bg = "#11151c" },
      separator_selected = { fg = "#b48600", bg = "#0f1115" },
    },
  },
}