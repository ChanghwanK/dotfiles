return {
    "MeanderingProgrammer/render-markdown.nvim",
    dependencies = {
        "nvim-treesitter/nvim-treesitter",
        "echasnovski/mini.icons",
    },
    ft = { "markdown" },
    config = function(_, opts)
        require("render-markdown").setup(opts)

        -- 커서가 링크 위에 있을 때 underline + bold 강조
        local ns = vim.api.nvim_create_namespace("md_link_hover")
        local link_pat = "%[.-%]%((.-)%)"

        vim.api.nvim_create_autocmd("CursorMoved", {
            pattern = "*.md",
            callback = function(ev)
                vim.api.nvim_buf_clear_namespace(ev.buf, ns, 0, -1)
                local row = vim.api.nvim_win_get_cursor(0)[1] - 1
                local line = vim.api.nvim_buf_get_lines(ev.buf, row, row + 1, false)[1] or ""
                local col = vim.api.nvim_win_get_cursor(0)[2]

                -- 현재 줄에서 링크 패턴 탐색
                local s = 1
                while true do
                    local ms, me = line:find("%[.-%]%(.-%)", s)
                    if not ms then break end
                    -- 커서가 링크 범위 안에 있으면 강조
                    if col >= ms - 1 and col < me then
                        vim.api.nvim_buf_set_extmark(ev.buf, ns, row, ms - 1, {
                            end_col = me,
                            hl_group = "RenderMarkdownLinkHover",
                            priority = 200,
                        })
                    end
                    s = me + 1
                end
            end,
        })

        vim.api.nvim_set_hl(0, "RenderMarkdownLinkHover", { underline = true, bold = true, fg = "#89b4fa" })
    end,
    ---@module 'render-markdown'
    ---@type render.md.UserConfig
    opts = {
        heading = {
            -- H1~H6 레벨별 들여쓰기로 시각적 계층감 부여
            left_pad = 0,
            -- 레벨별 아이콘 (Nerd Font)
            icons = { "󰉫 ", "󰉬 ", "󰉭 ", "󰉮 ", "󰉯 ", "󰉰 " },
            -- 배경이 전체 너비에 걸치도록
            width = "full",
        },
    },
}
