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

        local lspconfig = require("lspconfig")
        local capabilities = require("blink.cmp").get_lsp_capabilities()

        -- 2. Mason-LSPConfig 설정
        require("mason-lspconfig").setup({
            ensure_installed = { 
                "lua_ls",       -- Lua
                "pyright",      -- Python
                "ts_ls",        -- TypeScript/JavaScript
                "html",         -- HTML
                "cssls",        -- CSS
                "gopls",        -- Go
                "jdtls",        -- Java
                "terraformls",  -- Terraform
                "yamlls",       -- YAML
                "helm_ls",      -- Helm Chart (추가됨)
            },
            handlers = {
                -- 기본 핸들러 (모든 서버에 공통 적용)
                function(server_name)
                    lspconfig[server_name].setup({
                        capabilities = capabilities,
                    })
                end,
                -- [추가] Pyright 전용 설정: Django Meta 클래스 상속 에러 무시
                ["pyright"] = function()
                    lspconfig.pyright.setup({
                        capabilities = capabilities,
                        settings = {
                            python = {
                                analysis = {
                                    -- 자식 클래스가 부모 클래스의 변수 타입을 덮어쓸 때 발생하는 에러 무시
                                    -- Django의 class Meta 패턴에서 필수적임
                                    reportIncompatibleVariableOverride = false, 
                                    
                                    -- (선택 사항) Django 사용 시 유용한 추가 설정들
                                    -- typeCheckingMode = "basic", -- "off", "basic", "standard", "strict"
                                },
                            },
                        },
                    })
                end,
                -- Go
                ["gopls"] = function()
                    lspconfig.gopls.setup({
                        capabilities = capabilities,
                        settings = {
                            gopls = {
                                analyses = {
                                    unusedparams = true,
                                },
                                staticcheck = true
                            },
                        },
                    })
                end,
                -- YAML 전용 설정
                ["yamlls"] = function()
                    lspconfig.yamlls.setup({
                        capabilities = capabilities,
                        settings = {
                            yaml = {
                                keyOrdering = false,
                            },
                        },
                    })
                end,

                -- Helm 전용 설정 (필요시 추가 설정 가능, 보통 기본값으로 충분)
                ["helm_ls"] = function()
                    lspconfig.helm_ls.setup({
                        capabilities = capabilities,
                        settings = {
                            ['helm-ls'] = {
                                yamlls = {
                                    path = "yaml-language-server",
                                }
                            }
                        }
                    })
                end,

                -- Lua 언어 서버 전용 설정
                ["lua_ls"] = function()
                    lspconfig.lua_ls.setup({
                        capabilities = capabilities,
                        settings = {
                            Lua = {
                                diagnostics = {
                                    globals = { "vim" },
                                },
                            },
                        },
                    })
                end,
            }
        })

        -- 3. Helm 템플릿 파일에서 yamlls 비활성화
        vim.api.nvim_create_autocmd({"BufRead", "BufNewFile"}, {
            pattern = {"*/templates/*.yaml", "*/templates/*.yml", "*/templates/*.tpl"},
            callback = function()
                vim.diagnostic.disable(0)  -- 현재 버퍼의 diagnostics 비활성화
                -- yamlls가 이미 attach되어 있다면 detach
                local clients = vim.lsp.get_clients({ bufnr = 0 })
                for _, client in ipairs(clients) do
                    if client.name == "yamlls" then
                        vim.lsp.buf_detach_client(0, client.id)
                    end
                end
            end,
        })

        -- 4. 키맵 설정 (LSP 연결 시) - 사용자 정의 keyMapper 사용
        vim.api.nvim_create_autocmd("LspAttach", {
            group = vim.api.nvim_create_augroup("UserLspConfig", {}),
            callback = function(ev)
                local opts = { buffer = ev.buf }
                -- utils/keyMapper.lua에서 mapKey 함수 불러오기
                local mapKey = require("utils.keyMapper").mapKey

                -- Neovim 0.11+ 내장 gr* 키맵 제거 (mini.clue 메뉴 충돌 방지)
                -- grr 등은 vim/_defaults.lua에서 global로 설정되므로 buffer 없이도 삭제
                for _, key in ipairs({ "grn", "grr", "gra", "gri", "grt" }) do
                    pcall(vim.keymap.del, "n", key)
                    pcall(vim.keymap.del, "n", key, { buffer = ev.buf })
                end

                -- mapKey(from, to, mode, opts)
                mapKey("gd", function()                               -- 정의로 이동
                    local bufname = vim.api.nvim_buf_get_name(0)
                    if bufname:match("/templates/") then
                        local ok, helm = pcall(require, "utils.helm_values")
                        if ok and helm.try_goto_helm_value() then return end
                    end
                    vim.lsp.buf.definition()
                end, "n", opts)
                mapKey("K", vim.lsp.buf.hover, "n", opts)            -- 호버 (문서 보기)
                mapKey("<leader>rn", vim.lsp.buf.rename, "n", opts)  -- 이름 변경
                mapKey("<leader>ca", vim.lsp.buf.code_action, "n", opts) -- 코드 액션
                mapKey("gr", function()                               -- 참조 찾기
                    local bufname = vim.api.nvim_buf_get_name(0)
                    if bufname:match("values%.yaml$") then
                        local ok, helm = pcall(require, "utils.helm_values")
                        if ok and helm.find_value_references() then return end
                    end
                    require("glance").open("references")
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