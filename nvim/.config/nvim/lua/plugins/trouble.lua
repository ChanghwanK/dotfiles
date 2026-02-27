return {
    "folke/trouble.nvim",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    cmd = "Trouble",
    config = function()
        local mapKey = require("utils.keyMapper").mapKey

        require("trouble").setup({
            modes = {
                -- 진단 목록 (기본)
                diagnostics = {
                    auto_close = false,
                    auto_preview = true,
                    auto_refresh = true,
                },
            },
            icons = {
                indent = {
                    middle = " ├╴",
                    last   = " └╴",
                    top    = "    ",
                    ws     = "│  ",
                },
                fold_closed = " ",
                fold_open   = " ",
                kinds = {
                    Array         = " ",
                    Boolean       = "󰨙 ",
                    Class         = " ",
                    Constant      = "󰏿 ",
                    Constructor   = " ",
                    Enum          = " ",
                    EnumMember    = " ",
                    Event         = " ",
                    Field         = " ",
                    File          = " ",
                    Function      = "󰊕 ",
                    Interface     = " ",
                    Key           = " ",
                    Method        = "󰊕 ",
                    Module        = " ",
                    Namespace     = "󰦮 ",
                    Null          = " ",
                    Number        = "󰎠 ",
                    Object        = " ",
                    Operator      = " ",
                    Package       = " ",
                    Property      = " ",
                    String        = " ",
                    Struct        = "󰆼 ",
                    TypeParameter = " ",
                    Variable      = "󰀫 ",
                },
            },
        })

        -- 전체 워크스페이스 진단 토글
        mapKey("<leader>xx", "<cmd>Trouble diagnostics toggle<CR>",
            "n", { desc = "Trouble: 워크스페이스 진단" })
        -- 현재 파일 진단 토글
        mapKey("<leader>xd", "<cmd>Trouble diagnostics toggle filter.buf=0<CR>",
            "n", { desc = "Trouble: 현재 파일 진단" })
        -- LSP 심볼 목록
        mapKey("<leader>xs", "<cmd>Trouble symbols toggle focus=false<CR>",
            "n", { desc = "Trouble: 심볼 목록" })
        -- LSP 참조/정의 등
        mapKey("<leader>xr", "<cmd>Trouble lsp toggle focus=false win.position=right<CR>",
            "n", { desc = "Trouble: LSP 참조" })
        -- Location list
        mapKey("<leader>xl", "<cmd>Trouble loclist toggle<CR>",
            "n", { desc = "Trouble: Location List" })
        -- Quickfix
        mapKey("<leader>xq", "<cmd>Trouble qflist toggle<CR>",
            "n", { desc = "Trouble: Quickfix" })

        -- 이전/다음 항목으로 이동
        mapKey("[x", function()
            require("trouble").prev({ skip_groups = true, jump = true })
        end, "n", { desc = "Trouble: 이전 항목" })
        mapKey("]x", function()
            require("trouble").next({ skip_groups = true, jump = true })
        end, "n", { desc = "Trouble: 다음 항목" })
    end,
}
