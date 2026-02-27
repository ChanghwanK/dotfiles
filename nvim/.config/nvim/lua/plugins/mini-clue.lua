return {
    "echasnovski/mini.clue",
    version = false,
    event = "VeryLazy",
    config = function()
      local miniclue = require("mini.clue")
      miniclue.setup({
        triggers = {
          -- Leader triggers
          { mode = "n", keys = "<Leader>" },
          { mode = "x", keys = "<Leader>" },
  
          -- Built-in triggers (<C-w> 제거: 단독 매핑으로 버퍼 닫기 사용)
          { mode = "n", keys = "g" },     -- 'g' key
          { mode = "x", keys = "g" },
          { mode = "n", keys = "z" },     -- 'z' key
          { mode = "x", keys = "z" },
          { mode = "n", keys = "'" },     -- Marks 
          { mode = "n", keys = "`" },
          { mode = "x", keys = "'" },
          { mode = "x", keys = "`" },
          { mode = "n", keys = '"' },     -- Registers
          { mode = "x", keys = '"' },
          { mode = "i", keys = "<C-r>" },
          { mode = "c", keys = "<C-r>" },
        },
  
        clues = {
          -- Enhance this by adding descriptions for <Leader> mapping groups
          miniclue.gen_clues.builtin_completion(),
          miniclue.gen_clues.g(),
          miniclue.gen_clues.marks(),
          miniclue.gen_clues.registers(),
          -- miniclue.gen_clues.windows(), -- <C-w> 단독으로 버퍼 닫기 사용 중
          miniclue.gen_clues.z(),
  
          -- Custom groups (Claude Code 포함)
          { mode = "n", keys = "<Leader>f", desc = "+file" },
          { mode = "n", keys = "<Leader>b", desc = "+buffers" },
          { mode = "n", keys = "<Leader>g", desc = "+git" },
          { mode = "n", keys = "<Leader>a", desc = "+AI/Claude Code" },
          { mode = "n", keys = "<Leader>n", desc = "notice" },
          { mode = "n", keys = "<Leader>s", desc = "split view" },
        },
  
        window = {
          delay = 250,
          config = {
            width = 50, -- 너비를 50칸으로 고정 (원하는 크기로 조절 가능)
            -- 또는 화면 비율로 설정하고 싶다면 아래와 같이 함수를 사용할 수도 있습니다.
            -- width = math.floor(vim.o.columns * 0.6), -- 화면 너비의 60%
            border = "double",
          },
        },
      })
    end,
  }