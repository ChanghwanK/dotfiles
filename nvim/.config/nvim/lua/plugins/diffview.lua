return {
    "sindrets/diffview.nvim",
    dependencies = { "nvim-lua/plenary.nvim" },
    cmd = { "DiffviewOpen", "DiffviewClose", "DiffviewToggleFiles", "DiffviewFileHistory" },
    config = function()
        local mapKey = require("utils.keyMapper").mapKey
        local actions = require("diffview.actions")

        require("diffview").setup({
            diff_binaries = false,
            enhanced_diff_hl = true,   -- 인라인 변경사항 강조
            git_cmd = { "git" },
            use_icons = true,
            show_help_hints = true,
            watch_index = true,        -- git index 변경 감지
            icons = {
                folder_closed = "",
                folder_open   = "",
            },
            signs = {
                fold_closed = "",
                fold_open   = "",
                done        = "✓",
            },
            view = {
                -- 기본 diff 레이아웃
                default = {
                    layout = "diff2_horizontal",  -- 좌/우 분할
                    winbar_info = false,
                },
                -- merge conflict 레이아웃
                merge_tool = {
                    layout = "diff3_horizontal",
                    disable_diagnostics = true,
                },
                file_history = {
                    layout = "diff2_horizontal",
                },
            },
            file_panel = {
                listing_style = "tree",    -- tree / list
                tree_options = {
                    flatten_dirs = true,   -- 단일 자식 디렉토리 평탄화
                    folder_statuses = "only_folded",
                },
                win_config = {
                    position = "left",
                    width = 35,
                    win_opts = {},
                },
            },
            -- 파일 히스토리 패널
            file_history_panel = {
                log_options = {
                    git = {
                        single_file = { diff_merges = "combined" },
                        multi_file  = { diff_merges = "first-parent" },
                    },
                },
                win_config = {
                    position = "bottom",
                    height = 16,
                    win_opts = {},
                },
            },
            keymaps = {
                disable_defaults = false,
                view = {
                    { "n", "<leader>gx", actions.close, { desc = "Diffview 닫기" } },
                    { "n", "q",          actions.close, { desc = "Diffview 닫기" } },
                },
                file_panel = {
                    { "n", "q", actions.close, { desc = "Diffview 닫기" } },
                },
                file_history_panel = {
                    { "n", "q", actions.close, { desc = "Diffview 닫기" } },
                },
            },
        })

        -- 현재 변경사항 diff (staged + unstaged)
        mapKey("<leader>gd", "<cmd>DiffviewOpen<CR>",
            "n", { desc = "Git: 변경사항 diff 열기" })

        -- 특정 커밋과 비교 (HEAD~1 등 입력)
        mapKey("<leader>gD", function()
            local commit = vim.fn.input("비교할 커밋/브랜치: ")
            if commit ~= "" then
                vim.cmd("DiffviewOpen " .. commit)
            end
        end, "n", { desc = "Git: 커밋과 diff 비교" })

        -- 현재 파일의 커밋 히스토리
        mapKey("<leader>gl", "<cmd>DiffviewFileHistory %<CR>",
            "n", { desc = "Git: 현재 파일 히스토리" })

        -- 전체 프로젝트 git 로그
        mapKey("<leader>gL", "<cmd>DiffviewFileHistory<CR>",
            "n", { desc = "Git: 전체 히스토리" })

        -- Diffview 닫기
        mapKey("<leader>gx", "<cmd>DiffviewClose<CR>",
            "n", { desc = "Git: Diffview 닫기" })
    end,
}
