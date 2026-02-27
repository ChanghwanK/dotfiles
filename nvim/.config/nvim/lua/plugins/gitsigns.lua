return {
    "lewis6991/gitsigns.nvim",
    event = { "BufReadPre", "BufNewFile" },
    config = function()
        local gitsigns = require("gitsigns")
        local mapKey = require("utils.keyMapper").mapKey
        
        gitsigns.setup({
            signs = {
                add          = { text = '│' },  -- 추가된 줄
                change       = { text = '│' },  -- 수정된 줄
                delete       = { text = '_' },  -- 삭제된 줄
                topdelete    = { text = '‾' },  -- 맨 위 삭제
                changedelete = { text = '~' },  -- 변경 후 삭제
                untracked    = { text = '┆' },  -- 추적 안 되는 파일
            },
            
            -- Git blame 표시 (현재 줄의 커밋 정보)
            current_line_blame = false,  -- 기본 비활성화
            current_line_blame_opts = {
                virt_text = true,
                virt_text_pos = 'eol',  -- 줄 끝에 표시
                delay = 500,
            },
            
            -- 미리보기 설정
            preview_config = {
                border = 'rounded',
                style = 'minimal',
            },
            
            -- 키맵 비활성화 (아래에서 직접 설정)
            on_attach = function(bufnr)
                local opts = { buffer = bufnr }
                
                -- Hunk 이동 (변경 사항 블록 이동)
                mapKey(']c', function()
                    if vim.wo.diff then return ']c' end
                    vim.schedule(function() gitsigns.next_hunk() end)
                    return '<Ignore>'
                end, 'n', vim.tbl_extend('force', opts, { expr = true, desc = "다음 변경사항" }))
                
                mapKey('[c', function()
                    if vim.wo.diff then return '[c' end
                    vim.schedule(function() gitsigns.prev_hunk() end)
                    return '<Ignore>'
                end, 'n', vim.tbl_extend('force', opts, { expr = true, desc = "이전 변경사항" }))
                
                -- Git 액션
                mapKey('<leader>hs', gitsigns.stage_hunk, 'n', vim.tbl_extend('force', opts, { desc = "Hunk 스테이지" }))
                mapKey('<leader>hr', gitsigns.reset_hunk, 'n', vim.tbl_extend('force', opts, { desc = "Hunk 리셋" }))
                mapKey('<leader>hS', gitsigns.stage_buffer, 'n', vim.tbl_extend('force', opts, { desc = "버퍼 스테이지" }))
                mapKey('<leader>hu', gitsigns.undo_stage_hunk, 'n', vim.tbl_extend('force', opts, { desc = "스테이지 취소" }))
                mapKey('<leader>hR', gitsigns.reset_buffer, 'n', vim.tbl_extend('force', opts, { desc = "버퍼 리셋" }))
                mapKey('<leader>hp', gitsigns.preview_hunk, 'n', vim.tbl_extend('force', opts, { desc = "Hunk 미리보기" }))
                mapKey('<leader>hb', function() gitsigns.blame_line({ full = true }) end, 'n', vim.tbl_extend('force', opts, { desc = "줄 Blame 보기" }))
                mapKey('<leader>tb', gitsigns.toggle_current_line_blame, 'n', vim.tbl_extend('force', opts, { desc = "Blame 토글" }))
                mapKey('<leader>hd', gitsigns.diffthis, 'n', vim.tbl_extend('force', opts, { desc = "Diff 보기" }))
                mapKey('<leader>hD', function() gitsigns.diffthis('~') end, 'n', vim.tbl_extend('force', opts, { desc = "Diff 보기 (HEAD)" }))
                mapKey('<leader>td', gitsigns.toggle_deleted, 'n', vim.tbl_extend('force', opts, { desc = "삭제된 줄 토글" }))
            end,
        })
    end,
}