return {
    {
        "nvim-treesitter/nvim-treesitter",
        lazy = false,
        build = ":TSUpdate",
        config = function()
            -- 파서 설치 (이미 설치된 경우 무시됨)
            require("nvim-treesitter").install({
                "lua", "vim", "vimdoc", "query",
                "python", "go", "rust", "c",
                "javascript", "typescript", "tsx",
                "html", "css", "json", "yaml", "toml",
                "terraform", "bash", "dockerfile",
                "markdown", "markdown_inline",
            })

            -- 모든 filetype에서 treesitter 하이라이팅 활성화
            vim.api.nvim_create_autocmd("FileType", {
                callback = function(args)
                    pcall(vim.treesitter.start, args.buf)
                end,
            })

            -- treesitter indents 쿼리가 존재하는 언어에 자동 적용
            vim.api.nvim_create_autocmd("FileType", {
                callback = function(args)
                    local lang = vim.treesitter.language.get_lang(args.match) or args.match
                    local ok = pcall(vim.treesitter.query.get, lang, "indents")
                    if ok then
                        vim.bo[args.buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
                    end
                end,
            })
        end,
    },
    {
        "nvim-treesitter/nvim-treesitter-textobjects",
        branch = "main",
        dependencies = { "nvim-treesitter/nvim-treesitter" },
        config = function()
            require("nvim-treesitter-textobjects").setup({
                select = {
                    lookahead = true,
                },
                move = {
                    set_jumps = true,
                },
            })

            local select = require("nvim-treesitter-textobjects.select")
            local move = require("nvim-treesitter-textobjects.move")

            -- textobjects: 함수/클래스/파라미터 선택
            local textobjects = {
                { "af", "@function.outer", "Treesitter: select function (outer)" },
                { "if", "@function.inner", "Treesitter: select function (inner)" },
                { "ac", "@class.outer",    "Treesitter: select class (outer)" },
                { "ic", "@class.inner",    "Treesitter: select class (inner)" },
                { "aa", "@parameter.outer", "Treesitter: select parameter (outer)" },
                { "ia", "@parameter.inner", "Treesitter: select parameter (inner)" },
            }
            for _, obj in ipairs(textobjects) do
                vim.keymap.set({ "x", "o" }, obj[1], function()
                    select.select_textobject(obj[2])
                end, { desc = obj[3] })
            end

            -- move: 함수/클래스 간 이동
            local moves = {
                { "]f", "@function.outer", "next",     "start", "Treesitter: next function" },
                { "]F", "@function.outer", "next",     "end",   "Treesitter: next function end" },
                { "[f", "@function.outer", "previous", "start", "Treesitter: prev function" },
                { "[F", "@function.outer", "previous", "end",   "Treesitter: prev function end" },
                { "]C", "@class.outer",    "next",     "start", "Treesitter: next class" },
                { "[C", "@class.outer",    "previous", "start", "Treesitter: prev class" },
            }
            for _, m in ipairs(moves) do
                vim.keymap.set({ "n", "x", "o" }, m[1], function()
                    if m[4] == "start" then
                        move["goto_" .. m[3] .. "_start"](m[2])
                    else
                        move["goto_" .. m[3] .. "_end"](m[2])
                    end
                end, { desc = m[5] })
            end

            -- incremental selection: CR로 확장, BS로 축소
            local node_sel = nil
            local function select_node(node)
                local sr, sc, er, ec = node:range()
                vim.fn.setpos("'<", { 0, sr + 1, sc + 1, 0 })
                vim.fn.setpos("'>", { 0, er + 1, ec, 0 })
                vim.cmd("normal! gv")
            end

            vim.keymap.set("n", "<CR>", function()
                node_sel = vim.treesitter.get_node()
                if node_sel then select_node(node_sel) end
            end, { desc = "Treesitter: start node selection" })

            vim.keymap.set("v", "<CR>", function()
                if node_sel then
                    node_sel = node_sel:parent() or node_sel
                    select_node(node_sel)
                end
            end, { desc = "Treesitter: expand selection" })

            vim.keymap.set("v", "<BS>", function()
                if node_sel then
                    local child = node_sel:child(0)
                    if child then node_sel = child end
                    select_node(node_sel)
                end
            end, { desc = "Treesitter: shrink selection" })
        end,
    },
}
