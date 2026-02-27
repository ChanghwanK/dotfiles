return {
    "stevearc/aerial.nvim",
    dependencies = {
        "nvim-treesitter/nvim-treesitter",
        "nvim-tree/nvim-web-devicons",
    },
    event = "LspAttach",
    config = function()
        local mapKey = require("utils.keyMapper").mapKey

        require("aerial").setup({
            -- 백엔드 우선순위: LSP → Treesitter → 순수 파싱
            backends = { "lsp", "treesitter", "markdown", "asciidoc", "man" },

            layout = {
                max_width      = { 40, 0.2 },  -- 최대 40자 or 20%
                width          = nil,
                min_width      = 20,
                default_direction = "prefer_right",
                placement      = "window",     -- 현재 창 옆에 배치
                resize_to_content = false,
                preserve_equality = false,
            },

            -- 아웃라인 창 설정
            attach_mode     = "window",
            close_automatic_events = { "unsupported" },
            keymaps = {
                ["?"]     = "actions.show_help",
                ["g?"]    = "actions.show_help",
                ["<CR>"]  = "actions.jump",
                ["<2-LeftMouse>"] = "actions.jump",
                ["<C-v>"] = "actions.jump_vsplit",
                ["<C-s>"] = "actions.jump_split",
                ["p"]     = "actions.scroll",
                ["<C-j>"] = "actions.down_and_scroll",
                ["<C-k>"] = "actions.up_and_scroll",
                ["{"]     = "actions.prev",
                ["}"]     = "actions.next",
                ["[["]    = "actions.prev_up",
                ["]]"]    = "actions.next_up",
                ["q"]     = "actions.close",
                ["o"]     = "actions.tree_toggle",
                ["za"]    = "actions.tree_toggle",
                ["O"]     = "actions.tree_toggle_recursive",
                ["zA"]    = "actions.tree_toggle_recursive",
                ["l"]     = "actions.tree_open",
                ["zo"]    = "actions.tree_open",
                ["L"]     = "actions.tree_open_recursive",
                ["zO"]    = "actions.tree_open_recursive",
                ["h"]     = "actions.tree_close",
                ["zc"]    = "actions.tree_close",
                ["H"]     = "actions.tree_close_recursive",
                ["zC"]    = "actions.tree_close_recursive",
                ["zr"]    = "actions.tree_increase_fold_level",
                ["zR"]    = "actions.tree_open_all",
                ["zm"]    = "actions.tree_decrease_fold_level",
                ["zM"]    = "actions.tree_close_all",
                ["zx"]    = "actions.tree_sync_folds",
                ["zX"]    = "actions.tree_sync_folds",
            },

            -- 심볼 필터: 표시할 항목 종류
            filter_kind = {
                "Class",
                "Constructor",
                "Enum",
                "Function",
                "Interface",
                "Module",
                "Method",
                "Struct",
            },

            -- 아이콘 (mini.icons / nvim-web-devicons 자동 사용)
            icons = {},

            -- 코드 이동 시 아웃라인 자동 하이라이트 동기화
            highlight_on_hover  = true,
            highlight_on_jump   = 300,  -- ms

            -- 현재 심볼 자동 스크롤
            autoscroll          = true,

            -- 아웃라인 열 때 포커스
            focus_on_open       = false,

            -- 닫힌 fold 안의 심볼도 표시
            show_guides         = true,
            guides = {
                mid_item   = "├─",
                last_item  = "└─",
                nested_top = "│ ",
                whitespace = "  ",
            },

            -- 파일 열 때 자동 열기 (false = 수동)
            open_automatic = false,

            -- lualine 연동용 (옵션)
            lualine_sep = " | ",
        })

        -- 아웃라인 패널 토글
        mapKey("<leader>o", "<cmd>AerialToggle!<CR>",
            "n", { desc = "Aerial: 아웃라인 토글" })

        -- 이전/다음 심볼로 이동
        mapKey("[s", "<cmd>AerialPrev<CR>",
            "n", { desc = "Aerial: 이전 심볼" })
        mapKey("]s", "<cmd>AerialNext<CR>",
            "n", { desc = "Aerial: 다음 심볼" })

        -- 심볼 검색
        mapKey("<leader>fs", "<cmd>AerialNavToggle<CR>",
            "n", { desc = "Aerial: 심볼 검색" })
    end,
}
