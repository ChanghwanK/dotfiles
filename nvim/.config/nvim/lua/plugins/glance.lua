return {
    "dnlhc/glance.nvim",
    event = "LspAttach",
    config = function()
        local glance = require("glance")
        local actions = glance.actions

        glance.setup({
            height = 18,
            zindex = 45,
            border = { enable = true, top_char = "―", bottom_char = "―" },
            list = { position = "left", width = 0.33 },
            theme = { enable = true, mode = "auto" },
            winbar = { enable = true },
            folds = {
                fold_closed = "",
                fold_open = "",
                folded = true,  -- 처음에 그룹 접힌 상태로 시작
            },
            indent_lines = { enable = true, icon = "│" },
            -- 결과가 1개면 바로 점프, 여러 개면 팝업 열기
            hooks = {
                before_open = function(results, open, jump, method)
                    if #results == 1 then
                        jump(results[1])
                    else
                        open(results)
                    end
                end,
            },
            mappings = {
                list = {
                    ["j"] = actions.next,
                    ["k"] = actions.previous,
                    ["<Tab>"] = actions.next_location,
                    ["<S-Tab>"] = actions.previous_location,
                    ["<C-u>"] = actions.preview_scroll_win(5),
                    ["<C-d>"] = actions.preview_scroll_win(-5),
                    ["v"] = actions.jump_vsplit,
                    ["s"] = actions.jump_split,
                    ["t"] = actions.jump_tab,
                    ["<CR>"] = actions.jump,
                    ["o"] = actions.jump,
                    ["<C-q>"] = actions.quickfix,
                    ["l"] = actions.open_fold,
                    ["h"] = actions.close_fold,
                    ["<leader>l"] = actions.enter_win("preview"),
                    ["q"] = actions.close,
                    ["Q"] = actions.close,
                    ["<Esc>"] = actions.close,
                },
                preview = {
                    ["q"] = actions.close,
                    ["<Esc>"] = actions.close,
                    ["<Tab>"] = actions.next_location,
                    ["<S-Tab>"] = actions.previous_location,
                    ["<leader>h"] = actions.enter_win("list"),
                },
            },
        })
    end,
}
