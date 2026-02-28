return {
    "neovim/nvim-lspconfig",
    dependencies = {
        "williamboman/mason.nvim",
        "williamboman/mason-lspconfig.nvim",
    },
    config = function()
        -- 1. Mason 설정
        require("mason").setup({
            ui = {
                icons = {
                    package_installed = "✓",
                    package_pending = "➜",
                    package_uninstalled = "✗"
                }
            }
        })

        -- 2. 전역 capabilities 설정 (blink.cmp)
        local capabilities = require("blink.cmp").get_lsp_capabilities()
        vim.lsp.config('*', { capabilities = capabilities })

        -- 3. 서버별 설정 (vim.lsp.config으로 마이그레이션)
        vim.lsp.config('pyright', {
            settings = {
                python = {
                    analysis = {
                        -- Django의 class Meta 패턴에서 필수적임
                        reportIncompatibleVariableOverride = false,
                    },
                },
            },
        })

        vim.lsp.config('gopls', {
            settings = {
                gopls = {
                    analyses = { unusedparams = true },
                    staticcheck = true,
                },
            },
        })

        vim.lsp.config('yamlls', {
            settings = {
                yaml = { keyOrdering = false },
            },
        })

        vim.lsp.config('helm_ls', {
            settings = {
                ['helm-ls'] = {
                    yamlls = { path = "yaml-language-server" }
                }
            }
        })

        vim.lsp.config('kotlin_language_server', {
            cmd = { "/opt/homebrew/bin/kotlin-language-server" },
        })

        vim.lsp.config('lua_ls', {
            settings = {
                Lua = {
                    diagnostics = { globals = { "vim" } },
                },
            },
        })

        -- 4. Mason-LSPConfig 설정
        require("mason-lspconfig").setup({
            ensure_installed = {
                "lua_ls",
                "pyright",
                "ts_ls",
                "html",
                "cssls",
                "gopls",
                "jdtls",
                "kotlin_language_server",
                "terraformls",
                "yamlls",
                "helm_ls",
            },
            automatic_enable = true,
        })

        -- 5. Helm 템플릿 파일에서 yamlls 비활성화
        vim.api.nvim_create_autocmd({"BufRead", "BufNewFile"}, {
            pattern = {"*/templates/*.yaml", "*/templates/*.yml", "*/templates/*.tpl"},
            callback = function()
                vim.diagnostic.disable(0)
                local clients = vim.lsp.get_clients({ bufnr = 0 })
                for _, client in ipairs(clients) do
                    if client.name == "yamlls" then
                        vim.lsp.buf_detach_client(0, client.id)
                    end
                end
            end,
        })

        -- 6. 키맵 설정 (LSP 연결 시)
        vim.api.nvim_create_autocmd("LspAttach", {
            group = vim.api.nvim_create_augroup("UserLspConfig", {}),
            callback = function(ev)
                local opts = { buffer = ev.buf }
                local mapKey = require("utils.keyMapper").mapKey

                -- Neovim 0.11+ 내장 gr* 키맵 제거 (mini.clue 메뉴 충돌 방지)
                for _, key in ipairs({ "grn", "grr", "gra", "gri", "grt" }) do
                    pcall(vim.keymap.del, "n", key)
                    pcall(vim.keymap.del, "n", key, { buffer = ev.buf })
                end

                mapKey("gd", function()
                    local bufname = vim.api.nvim_buf_get_name(0)
                    if bufname:match("/templates/") then
                        local ok, helm = pcall(require, "utils.helm_values")
                        if ok and helm.try_goto_helm_value() then return end
                    end
                    vim.lsp.buf.definition()
                end, "n", opts)
                mapKey("K", vim.lsp.buf.hover, "n", opts)
                mapKey("<leader>rn", vim.lsp.buf.rename, "n", opts)
                mapKey("<leader>ca", vim.lsp.buf.code_action, "n", opts)
                mapKey("gr", function()
                    local bufname = vim.api.nvim_buf_get_name(0)
                    if bufname:match("values%.yaml$") then
                        local ok, helm = pcall(require, "utils.helm_values")
                        if ok and helm.find_value_references() then return end
                    end
                    require("glance").open("references")
                end, "n", opts)
                mapKey("gi", function()
                    -- kotlin_language_server advertises implementation support but returns -32603 internally
                    local unsupported_fts = { kotlin = true, java = true }
                    if unsupported_fts[vim.bo.filetype] then
                        vim.notify("go-to-implementation not supported for " .. vim.bo.filetype, vim.log.levels.WARN)
                        return
                    end
                    require("glance").open("implementations")
                end, "n", opts)

                -- navic 연결 (barbecue를 위해)
                local client = vim.lsp.get_client_by_id(ev.data.client_id)
                if client and client.server_capabilities.documentSymbolProvider then
                    local navic_ok, navic = pcall(require, "nvim-navic")
                    if navic_ok then
                        navic.attach(client, ev.buf)
                    end
                end
            end,
        })
    end,
}
