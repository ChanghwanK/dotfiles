return {
    "echasnovski/mini.icons",
    version = false,
    lazy = false,  -- true를 false로 변경
    priority = 1000,  -- 이 줄 추가 (높은 우선순위)
    config = function()
      local mini_icons = require("mini.icons")
      mini_icons.setup({
        style = "glyph",
      })
      
      -- nvim-web-devicons 호환성을 위한 설정
      mini_icons.mock_nvim_web_devicons()
    end,
  }