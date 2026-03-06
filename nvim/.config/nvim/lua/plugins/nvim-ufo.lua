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

        -- 키맵 설정
        mapKey("zR", function() ufo.openAllFolds() end, "n", { desc = "UFO: 모든 폴드 펼치기" })
        mapKey("zM", function() ufo.closeAllFolds() end, "n", { desc = "UFO: 모든 폴드 닫기" })
        mapKey("zr", function() ufo.openFoldsExceptKinds() end, "n", { desc = "UFO: 점진적 펼치기" })
        mapKey("zm", function() ufo.closeFoldsWith() end, "n", { desc = "UFO: 점진적 닫기" })
        
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