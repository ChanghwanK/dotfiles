-- ~/.config/nvim/lua/plugins/themes.lua
return {
  {
    "sainnhe/gruvbox-material",
    lazy = false,
    priority = 1000,
    enabled = vim.g.nvim_theme == "gruvbox-material",
    config = function()
      -- 옵션 설정 (취향에 따라 변경 가능)
      vim.g.gruvbox_material_background = "hard"     -- hard, medium, soft
      vim.g.gruvbox_material_foreground = "material" -- material, mix, original
      vim.g.gruvbox_material_enable_italic = 1
      vim.g.gruvbox_material_enable_bold = 1
      vim.g.gruvbox_material_transparent_background = 0 -- 1로 설정시 배경 투명

      -- 테마 적용
      vim.cmd("colorscheme gruvbox-material")
    end,
  },
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000,
    enabled = vim.g.nvim_theme == "catppuccin",
    config = function()
      require("catppuccin").setup({
        flavour = "mocha", -- latte, frappe, macchiato, mocha
        transparent_background = false,
        term_colors = true,
        integrations = {
          cmp = true,
          gitsigns = true,
          nvimtree = true,
          treesitter = true,
          telescope = true,
          indent_blankline = {
            enabled = true,
            scope_color = "lavender",
            colored_indent_levels = false,
          },
          which_key = true,
        },
      })

      vim.cmd("colorscheme catppuccin")
    end,
  },
  {
    "olimorris/onedarkpro.nvim",
    priority = 1000, -- 로드 우선순위를 높여서 가장 먼저 로드되게 함
    enabled = vim.g.nvim_theme == "onedark_pro",
    config = function()
      require("onedarkpro").setup({
        -- 옵션 설정 (필요에 따라 주석 해제하여 사용)
        options = {
          transparency = false,         -- 배경 투명하게 (true/false)
          cursorline = true,            -- 커서 라인 강조
          lualine_transparency = false, -- lualine 투명하게
        },
        styles = {
          comments = "italic",      -- 주석을 이탤릭체로
          keywords = "bold,italic", -- 키워드를 굵고 이탤릭체로
        },
        highlights = {
          -- Visual: 비주얼 모드 선택 영역 (이전 질문)
          Visual = { bg = "#264f78" },

          -- [추가] 들여쓰기 가이드라인 색상 (더 잘 보이게 수정)
          IblIndent = { fg = "#3E4452" }, -- 일반 들여쓰기 선 (밝은 회색)
          IblScope = { fg = "#E06C75" },  -- 현재 커서가 있는 블록의 선 (빨간색 강조)

          -- (혹시 구버전 플러그인을 쓸 경우를 대비한 호환성 설정)
          IndentBlanklineChar = { fg = "#3E4452" },
          IndentBlanklineContextChar = { fg = "#E06C75" },
        }
      })
      -- 테마 적용 (변형: "onedark", "onelight", "onedark_vivid", "onedark_dark")
      vim.cmd("colorscheme onedark_vivid")
    end,
  },
  {
    "rebelot/kanagawa.nvim",
    priority = 1000,
    enabled = vim.g.nvim_theme == "kanagawa",
    config = function()
      require("kanagawa").setup({
        compile = true,   -- 컴파일을 활성화하여 시작 속도 향상
        undercurl = true, -- undercurl 지원 활성화
        commentStyle = { italic = true },
        functionStyle = {},
        keywordStyle = { italic = true },
        statementStyle = { bold = true },
        typeStyle = {},
        -- transparent = false,     -- 배경 투명 여부
        dimInactive = true,    -- 비활성 창 어둡게 하기
        terminalColors = true, -- 터미널 색상 정의
        -- theme = "dragon", -- 테마 선택: "wave", "dragon", "lotus"
        -- background = {    -- 배경 설정에 따른 테마 매핑
        --   dark = "dragon",
        --   light = "lotus"
        -- },
      })
      vim.cmd("colorscheme kanagawa-dragon")
    end,
  },
  {
    "morhetz/gruvbox",
    priority = 1000,
    enabled = vim.g.nvim_theme == "gruvbox",
    config = function()
      vim.g.gruvbox_contrast_dark = "hard" -- hard, medium, soft
      vim.g.gruvbox_italic = 1             -- 이탤릭 활성화

      vim.cmd("colorscheme gruvbox")
    end,
  },
  {
    "mawkler/onedark.nvim",
    priority = 1000,
    enabled = vim.g.nvim_theme == "onedark",
    config = function()
      require("onedark").setup({
        comment_style = "italic",
        keyword_style = "italic",
        function_style = "italic",
        variable_style = "none",
        dark_sidebar = true,
        dark_float = false,
        transparent = false,
        transparent_sidebar = false,
        hide_inactive_statusline = true,
        hide_end_of_buffer = true,
        highlight_linenumber = false,
        lualine_bold = false,
        msg_area_style = "none",
        sidebars = {},
        colors = {},
        overrides = function(c)
          return {}
        end,
      })
      vim.cmd([[colorscheme onedark]])
    end,
  },
  {
    "jacoborus/tender.vim",
    lazy = false,
    priority = 1000,
    enabled = vim.g.nvim_theme == "tender",
    config = function()
      -- tender 테마 적용
      vim.cmd("colorscheme tender")
    end,
  },
  {
    "Shatur/neovim-ayu",
    priority = 1000,
    enabled = vim.g.nvim_theme == "ayu",
    config = function()
      require("ayu").setup({
        mirage = true, -- true: ayu-mirage, false: ayu-dark
        terminal_colors = true,
        overrides = {},
      })
      vim.cmd("colorscheme ayu-mirage")
    end,
  },
  {
    "vague-theme/vague.nvim",
    priority = 1000,
    enabled = vim.g.nvim_theme == "vague",
    config = function()
      require("vague").setup({
        transparent = true,
        bold = true,
        italic = true,
        style = {
          boolean = "bold",
          number = "none",
          float = "none",
          error = "bold",
          comments = "italic",
          conditionals = "none",
          functions = "none",
          headings = "bold",
          operators = "none",
          strings = "italic",
          variables = "none",
          keywords = "none",
          keyword_return = "italic",
          keywords_loop = "none",
          keywords_label = "none",
          keywords_exception = "none",
          builtin_constants = "bold",
          builtin_functions = "none",
          builtin_types = "bold",
          builtin_variables = "none",
        },
        plugins = {
          cmp = {
            match = "bold",
            match_fuzzy = "bold",
          },
          dashboard = {
            footer = "italic",
          },
          lsp = {
            diagnostic_error = "bold",
            diagnostic_hint = "none",
            diagnostic_info = "italic",
            diagnostic_ok = "none",
            diagnostic_warn = "bold",
          },
          neotest = {
            focused = "bold",
            adapter_name = "bold",
          },
          telescope = {
            match = "bold",
          },
        },
      })
      vim.cmd([[colorscheme vague]])
    end,
  },
}
