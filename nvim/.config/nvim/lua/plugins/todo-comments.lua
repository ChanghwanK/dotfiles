return {
    "folke/todo-comments.nvim",
    dependencies = { "nvim-lua/plenary.nvim" },
    event = { "BufReadPre", "BufNewFile" },
    config = function()
        local mapKey = require("utils.keyMapper").mapKey

        require("todo-comments").setup({
            signs = true,       -- 사인 컬럼에 아이콘 표시
            sign_priority = 8,
            keywords = {
                FIX  = { icon = " ", color = "error",   alt = { "FIXME", "BUG", "FIXIT", "ISSUE" } },
                TODO = { icon = " ", color = "info" },
                HACK = { icon = " ", color = "warning" },
                WARN = { icon = " ", color = "warning", alt = { "WARNING", "XXX" } },
                PERF = { icon = "󰅒 ", color = "default", alt = { "OPTIM", "PERFORMANCE", "OPTIMIZE" } },
                NOTE = { icon = "󰍨 ", color = "hint",    alt = { "INFO" } },
                TEST = { icon = "⏲ ", color = "test",    alt = { "TESTING", "PASSED", "FAILED" } },
            },
            gui_style = {
                fg = "NONE",
                bg = "BOLD",
            },
            merge_keywords = true,
            highlight = {
                multiline         = true,
                multiline_pattern = "^.",
                multiline_context = 10,
                before            = "",        -- 키워드 앞 강조 없음
                keyword           = "wide",    -- 키워드 전체 강조
                after             = "fg",      -- 이후 텍스트는 foreground만
                pattern           = [[.*<(KEYWORDS)\s*:]],
                comments_only     = true,      -- 주석 안에서만 동작
                max_line_len      = 400,
                exclude           = {},
            },
            colors = {
                error   = { "DiagnosticError", "ErrorMsg",   "#DC2626" },
                warning = { "DiagnosticWarn",  "WarningMsg", "#FBBF24" },
                info    = { "DiagnosticInfo",               "#2563EB" },
                hint    = { "DiagnosticHint",               "#10B981" },
                default = { "Identifier",                   "#7C3AED" },
                test    = { "Identifier",                   "#FF006E" },
            },
            search = {
                command = "rg",
                args = {
                    "--color=never",
                    "--no-heading",
                    "--with-filename",
                    "--line-number",
                    "--column",
                },
                pattern = [[\b(KEYWORDS):]],
            },
        })

        -- 이전/다음 TODO로 이동
        mapKey("]t", function() require("todo-comments").jump_next() end,
            "n", { desc = "다음 TODO" })
        mapKey("[t", function() require("todo-comments").jump_prev() end,
            "n", { desc = "이전 TODO" })

        -- Telescope으로 TODO 목록 검색
        mapKey("<leader>ft", "<cmd>TodoTelescope<CR>",
            "n", { desc = "TODO 목록 검색" })

        -- Trouble로 TODO 목록 열기
        mapKey("<leader>xt", "<cmd>Trouble todo toggle<CR>",
            "n", { desc = "Trouble: TODO 목록" })
    end,
}
