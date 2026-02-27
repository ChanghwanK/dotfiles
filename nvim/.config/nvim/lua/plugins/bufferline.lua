-- lua/plugins/bufferline.lua
return {
  "akinsho/bufferline.nvim",
  event = "VeryLazy",
  dependencies = { "nvim-tree/nvim-web-devicons" },
  version = "*",
  opts = {
    options = {
      mode = "buffers",
      -- 스타일: "slant" | "slope" | "thick" | "thin" | { 'any', 'any' }
      separator_style = "slant", -- 윤곽선 체감 강화
      always_show_bufferline = true,

      -- 활성 탭 표시(두꺼운 느낌)
      indicator = {
        icon = "▎",
        style = "icon",
      },

      -- [비활성화] neo-tree offset — 롤백 시 아래 주석 해제
      -- offsets = {
      --   {
      --     filetype = "neo-tree",
      --     text = "File Explorer",
      --     highlight = "Directory",
      --     text_align = "left",
      --     separator = true,
      --   },
      -- },
    },

    highlights = {
      fill = { bg = "#0f1115" },

      -- 비활성 탭
      background = { fg = "#6b7280", bg = "#11151c" },
      buffer_visible = { fg = "#9aa4b2", bg = "#11151c" },

      -- 활성 탭
      buffer_selected = { fg = "#e5e9f0", bg = "#1b2230", bold = true },

      -- underline_selected 제거 (에러 원인)
      indicator_selected = { fg = "#4aa3ff" },

      -- 탭 경계(윤곽선 느낌 강화)
      separator = { fg = "#0b0e14", bg = "#11151c" },
      separator_visible = { fg = "#0b0e14", bg = "#11151c" },
      separator_selected = { fg = "#4aa3ff", bg = "#1b2230" },
    },
  },
}