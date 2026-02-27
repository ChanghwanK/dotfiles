return {
  {
    "goolord/alpha-nvim",
    enabled = false, -- [비활성화] snacks.dashboard로 대체. 롤백: enabled = true
    event = "VimEnter",
    config = function()
      local alpha = require("alpha")
      local dashboard = require("alpha.themes.dashboard")

      -- 대시보드 헤더 설정 (ASCII art 로고)
      dashboard.section.header.val = {
        "                                                     ",
        "  ███╗   ██╗███████╗ ██████╗ ██╗   ██╗██╗███╗   ███╗ ",
        "  ████╗  ██║██╔════╝██╔═══██╗██║   ██║██║████╗ ████║ ",
        "  ██╔██╗ ██║█████╗  ██║   ██║██║   ██║██║██╔████╔██║ ",
        "  ██║╚██╗██║██╔══╝  ██║   ██║╚██╗ ██╔╝██║██║╚██╔╝██║ ",
        "  ██║ ╚████║███████╗╚██████╔╝ ╚████╔╝ ██║██║ ╚═╝ ██║ ",
        "  ╚═╝  ╚═══╝╚══════╝ ╚═════╝   ╚═══╝  ╚═╝╚═╝     ╚═╝ ",
        "                                                     ",
      }

      -- 메뉴 항목 설정
      dashboard.section.buttons.val = {
        dashboard.button("e", "  새 파일", ":ene <BAR> startinsert <CR>"),
        dashboard.button("f", "  파일 찾기", function() Snacks.picker.files({ hidden = true }) end),
        dashboard.button("g", "  최근 파일", function() Snacks.picker.recent() end),
        dashboard.button("s", "  텍스트 검색", function() Snacks.picker.grep({ hidden = true }) end),
        dashboard.button("c", "  설정 열기", ":e ~/.config/nvim/init.lua <CR>"),
        dashboard.button("q", "  종료", ":qa <CR>"),
      }

      -- 바닥글 설정
      local function footer()
        return "Happy coding! 🚀"
      end

      dashboard.section.footer.val = footer()

      -- 섹션 스타일
      dashboard.section.header.opts.hl = "AlphaHeader"
      dashboard.section.buttons.opts.hl = "AlphaButtons"
      dashboard.section.footer.opts.hl = "AlphaFooter"

      -- 레이아웃 설정
      local opts = {
        layout = {
          { type = "padding", val = 4 },
          dashboard.section.header,
          { type = "padding", val = 2 },
          dashboard.section.buttons,
          { type = "padding", val = 2 },
          dashboard.section.footer,
        },
        opts = {
          margin = 5,
        },
      }

      alpha.setup(opts)
    end,
  },
}
