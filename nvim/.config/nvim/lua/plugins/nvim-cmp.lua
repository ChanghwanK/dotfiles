return {
    "saghen/blink.cmp",
    lazy = false,
    version = "*",
    dependencies = {
        -- LuaSnip 제거: blink.cmp 내장 vim.snippet 엔진 사용 (Neovim 0.10+)
        -- rollback: 아래 주석 해제 후 snippets.preset = "luasnip" 으로 변경
        -- {
        --     "L3MON4D3/LuaSnip",
        --     dependencies = { "rafamadriz/friendly-snippets" },
        --     config = function()
        --         require("luasnip.loaders.from_vscode").lazy_load()
        --     end,
        -- },
        "rafamadriz/friendly-snippets", -- blink.cmp 내장 snippets source가 자동 로드
    },
    opts = {
        keymap = {
            preset = "none",
            ["<C-Space>"] = { "show", "show_documentation", "hide_documentation" },
            ["<C-e>"] = { "hide" },
            ["<CR>"] = { "accept", "fallback" },
            ["<C-k>"] = { "select_prev", "fallback" },
            ["<C-j>"] = { "select_next", "fallback" },
            ["<Up>"] = { "select_prev", "fallback" },
            ["<Down>"] = { "select_next", "fallback" },
            ["<C-b>"] = { "scroll_documentation_up", "fallback" },
            ["<C-f>"] = { "scroll_documentation_down", "fallback" },
            ["<Tab>"] = {
                function(cmp)
                    if cmp.snippet_active() then
                        return cmp.snippet_forward()
                    elseif cmp.is_visible() then
                        return cmp.select_and_accept()
                    end
                end,
                "fallback",
            },
            ["<S-Tab>"] = { "snippet_backward", "select_prev", "fallback" },
        },
        snippets = {
            preset = "default", -- vim.snippet 내장 엔진 사용 (Neovim 0.10+), rollback 시 "luasnip"
        },
        sources = {
            default = { "lsp", "path", "snippets", "buffer" },
        },
        appearance = {
            nerd_font_variant = "mono",
        },
        completion = {
            list = {
                selection = {
                    preselect = false,  -- 자동 선택 비활성화: Enter가 줄바꿈+수락 동시에 되는 현상 방지
                },
            },
            documentation = {
                auto_show = true,
                window = { border = "rounded" },
            },
            menu = {
                border = "rounded",
                draw = {
                    columns = {
                        { "kind_icon" },
                        { "label", "label_description", gap = 1 },
                        { "kind", "source_name", gap = 1 },
                    },
                    components = {
                        kind_icon = {
                            text = function(ctx)
                                local icons = {
                                    Text          = "󰉿",
                                    Method        = "󰆧",
                                    Function      = "󰊕",
                                    Constructor   = "",
                                    Field         = "󰜢",
                                    Variable      = "󰀫",
                                    Class         = "󰠱",
                                    Interface     = "",
                                    Module        = "",
                                    Property      = "󰜢",
                                    Unit          = "󰑭",
                                    Value         = "󰎠",
                                    Enum          = "",
                                    Keyword       = "󰌋",
                                    Snippet       = "",
                                    Color         = "󰏘",
                                    File          = "󰈙",
                                    Reference     = "󰈇",
                                    Folder        = "󰉋",
                                    EnumMember    = "",
                                    Constant      = "󰏿",
                                    Struct        = "󰙅",
                                    Event         = "",
                                    Operator      = "󰆕",
                                    TypeParameter = "",
                                }
                                return (icons[ctx.kind] or "") .. " "
                            end,
                        },
                        source_name = {
                            text = function(ctx)
                                local labels = {
                                    lsp      = "[LSP]",
                                    snippets = "[Snip]",
                                    buffer   = "[Buf]",
                                    path     = "[Path]",
                                }
                                return labels[ctx.source_name] or ""
                            end,
                        },
                    },
                },
            },
        },
    },
}
