return {
    "kevinhwang91/nvim-ufo",
    dependencies = "kevinhwang91/promise-async",
    event = "BufReadPost",
    config = function()
        local ufo = require("ufo")
        local mapKey = require("utils.keyMapper").mapKey
        
        vim.o.foldcolumn = "0"
        vim.o.foldlevel = 99
        vim.o.foldlevelstart = 99
        vim.o.foldenable = true
        
        -- 특수 파일 타입에서 폴딩 비활성화 (autocmd 사용)
        vim.api.nvim_create_autocmd("FileType", {
            pattern = { 
                "neo-tree", 
                "neo-tree-popup",
                "NvimTree",
                "alpha",
                "dashboard",
                "lazy",
                "mason",
                "help",
                "lspinfo",
                "checkhealth",
            },
            callback = function()
                vim.opt_local.foldenable = false
            end,
        })
        
        ufo.setup({
            provider_selector = function(bufnr, filetype, buftype)
                local ft_ignore = { "neo-tree", "neo-tree-popup", "alpha", "dashboard", "NvimTree", "lazy", "mason" }
                if vim.tbl_contains(ft_ignore, filetype) then
                    return ""
                end
                return { "lsp", "indent" }
            end,
            
            preview = {
                win_config = {
                    border = "rounded",
                    winhighlight = "Normal:Folded",
                    winblend = 0,
                },
            },
            
            fold_virt_text_handler = function(virtText, lnum, endLnum, width, truncate)
                local newVirtText = {}
                local suffix = (" 󰁂 %d"):format(endLnum - lnum)
                local sufWidth = vim.fn.strdisplaywidth(suffix)
                local targetWidth = width - sufWidth
                local curWidth = 0
                
                for _, chunk in ipairs(virtText) do
                    local chunkText = chunk[1]
                    local chunkWidth = vim.fn.strdisplaywidth(chunkText)
                    if targetWidth > curWidth + chunkWidth then
                        table.insert(newVirtText, chunk)
                    else
                        chunkText = truncate(chunkText, targetWidth - curWidth)
                        table.insert(newVirtText, { chunkText, chunk[2] })
                        break
                    end
                    curWidth = curWidth + chunkWidth
                end
                
                table.insert(newVirtText, { suffix, "WarningMsg" })
                return newVirtText
            end,
        })

        -- 대형 폴드만 자동으로 닫는 함수
        local function close_large_folds(min_lines)
            min_lines = min_lines or 20
            vim.cmd("normal! zM")
            local line_count = vim.api.nvim_buf_line_count(0)
            local i = 1
            while i <= line_count do
                local foldstart = vim.fn.foldclosed(i)
                if foldstart ~= -1 then
                    local foldend = vim.fn.foldclosedend(foldstart)
                    if (foldend - foldstart + 1) < min_lines then
                        vim.cmd(foldstart .. "foldopen")
                    end
                    i = foldend + 1
                else
                    i = i + 1
                end
            end
        end

        -- 파일 열 때 대형 폴드 자동 닫기
        local skip_ft = { "dashboard", "lazy", "mason", "help", "lspinfo", "checkhealth", "neo-tree", "NvimTree", "alpha", "snacks_dashboard" }
        vim.api.nvim_create_autocmd("BufReadPost", {
            callback = function()
                local ft = vim.bo.filetype
                if vim.tbl_contains(skip_ft, ft) then return end
                vim.defer_fn(function()
                    if not vim.api.nvim_buf_is_valid(0) then return end
                    if vim.tbl_contains(skip_ft, vim.bo.filetype) then return end
                    close_large_folds(20)
                end, 150)
            end,
        })

        -- 키맵 설정
        mapKey("zR", function() ufo.openAllFolds() end, "n", { desc = "UFO: 모든 폴드 펼치기" })
        mapKey("zM", function() ufo.closeAllFolds() end, "n", { desc = "UFO: 모든 폴드 닫기" })
        mapKey("zr", function() ufo.openFoldsExceptKinds() end, "n", { desc = "UFO: 점진적 펼치기" })
        mapKey("zm", function() ufo.closeFoldsWith() end, "n", { desc = "UFO: 점진적 닫기" })
        
        mapKey("zL", function() close_large_folds(20) end, "n", { desc = "UFO: 대형 폴드 접기 (20줄 이상)" })

        mapKey("za", "za", "n", { desc = "폴드 토글" })
        mapKey("zo", "zo", "n", { desc = "폴드 열기" })
        mapKey("zc", "zc", "n", { desc = "폴드 닫기" })
        mapKey("zO", "zO", "n", { desc = "재귀 열기" })
        mapKey("zC", "zC", "n", { desc = "재귀 닫기" })
        
        mapKey("K", function()
            local winid = ufo.peekFoldedLinesUnderCursor()
            if not winid then
                vim.lsp.buf.hover()
            end
        end, "n", { desc = "UFO 프리뷰 또는 LSP 호버" })
    end,
}