return {
    "stevearc/conform.nvim",
    event = { "BufReadPre", "BufNewFile" },
    config = function()
        local conform = require("conform")
        local mapKey = require("utils.keyMapper").mapKey
        
        conform.setup({
            -- 포매터 등록 (언어별로 어떤 포매터를 사용할지 지정)
            formatters_by_ft = {
                -- JavaScript/TypeScript
                javascript = { "prettier" },
                typescript = { "prettier" },
                javascriptreact = { "prettier" },
                typescriptreact = { "prettier" },
                json = { "prettier" },
                
                -- Python
                python = { "black", "isort" },
                
                -- Lua
                lua = { "stylua" },
                
                -- Go
                go = { "gofmt", "goimports" },
                
                -- Terraform
                terraform = { "terraform_fmt" },
                tf = { "terraform_fmt" },
                hcl = { "terraform_fmt" },
                
                -- HTML/CSS
                html = { "prettier" },
                css = { "prettier" },
                scss = { "prettier" },
                
                -- Shell
                bash = { "shfmt" },
                sh = { "shfmt" },
            },
            
            -- 포매터 기본 설정
            formatters = {
                prettier = {
                    args = { "--stdin-filepath", "$FILENAME" },
                },
                stylua = {
                    args = { "--stdin-filepath", "$FILENAME", "-" },
                },
                black = {
                    args = { "--quiet", "-" },
                },
                isort = {
                    args = { "--quiet", "-" },
                },
                shfmt = {
                    args = { "-i", "2" },  -- 2칸 들여쓰기
                },
                terraform_fmt = {
                    -- Terraform fmt 기본 옵션
                    args = { "fmt", "-" },
                },
                yamlfmt = {
                    -- YAML 포매팅 옵션
                    args = { "-" },
                    stdin = true,
                },
            },
            
            -- 저장 시 자동 포맷 설정
            format_on_save = {
                timeout_ms = 500,
                lsp_fallback = true,
            },
        })

        -- 키맵 설정
        -- <leader>fm: 현재 버퍼 포맷 (노멀 모드)
        mapKey("<leader>fm", function()
            conform.format({
                async = true,
                lsp_fallback = true,
            })
        end, "n", { desc = "파일 포맷팅" })

        -- <leader>fm: 선택 영역 포맷 (비주얼 모드)
        mapKey("<leader>fm", function()
            conform.format({
                async = true,
                lsp_fallback = true,
                range = {
                    ["start"] = vim.fn.line("'<"),
                    ["end"] = vim.fn.line("'>"),
                },
            })
        end, "v", { desc = "선택 영역 포맷팅" })
    end,
}