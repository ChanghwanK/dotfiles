-- lua/plugins/bufferline.lua

-- 탭바 색은 colorscheme을 따라가지 않고 아래 hex로 고정되므로, 테마별로 색 세트를 둔다.
-- 구조(빈 영역 < 비활성 탭 < 노란 활성 탭, slope 구분자)는 테마와 무관하게 같다.
local function tab_colors()
  if vim.g.nvim_theme == "rose-pine" then
    local p = require("rose-pine.palette")
    return {
      fill = p.overlay,          -- 탭바 빈 영역: 배경보다 한 단계 진한 띠
      inactive = p.surface,      -- 비활성 탭
      inactive_fg = p.subtle,
      visible_fg = p.text,
      active = p.gold,           -- 활성 탭: Dawn gold
      active_fg = p.text,        -- gold 위 흰 글자는 대비가 낮아 본문색을 쓴다
    }
  end
  return {
    fill = "#0f1115",
    inactive = "#11151c",
    inactive_fg = "#6b7280",
    visible_fg = "#9aa4b2",
    active = "#b48600",
    active_fg = "#ffffff",
  }
end

return {
  "akinsho/bufferline.nvim",
  enabled = true,
  event = "VeryLazy",
  dependencies = { "nvim-tree/nvim-web-devicons" },
  version = "*",
  opts = function()
    local c = tab_colors()
    return {
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
        fill = { bg = c.fill },

        -- 비활성 탭
        background        = { fg = c.inactive_fg, bg = c.inactive },
        buffer_visible    = { fg = c.visible_fg, bg = c.inactive },

        -- 활성 탭
        buffer_selected    = { fg = c.active_fg, bg = c.active, bold = true },
        indicator_selected = { fg = c.active, bg = c.active },

        -- separator: fg = 탭 색, bg = fill 색
        separator          = { fg = c.fill, bg = c.inactive },
        separator_visible  = { fg = c.fill, bg = c.inactive },
        separator_selected = { fg = c.active, bg = c.fill },
      },
    }
  end,
}
