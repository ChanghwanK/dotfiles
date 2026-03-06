return {
    "folke/persistence.nvim",
    event = "BufReadPre", -- 파일 열기 전에 로드
    opts = {
        dir = vim.fn.stdpath("state") .. "/sessions/", -- 세션 저장 경로
        need = 1, -- 최소 1개 버퍼가 있어야 세션 저장
    },
    init = function()
        -- 세션 저장 직전: 이름 없는 버퍼 및 특수 buftype 버퍼 정리
        vim.api.nvim_create_autocmd("User", {
            pattern = "PersistenceSavePre",
            callback = function()
                -- 특수 창(explorer, 빈 창 등)을 먼저 닫아야 세션에 split이 남지 않음
                for _, win in ipairs(vim.api.nvim_list_wins()) do
                    local buf = vim.api.nvim_win_get_buf(win)
                    if vim.api.nvim_buf_is_valid(buf) then
                        local name = vim.api.nvim_buf_get_name(buf)
                        local bt = vim.bo[buf].buftype
                        local ft = vim.bo[buf].filetype
                        if name == "" or bt ~= "" or ft:match("^snacks_") then
                            pcall(vim.api.nvim_win_close, win, false)
                        end
                    end
                end
                -- 남은 특수 버퍼 삭제
                for _, buf in ipairs(vim.api.nvim_list_bufs()) do
                    if vim.api.nvim_buf_is_loaded(buf) then
                        local name = vim.api.nvim_buf_get_name(buf)
                        local bt = vim.bo[buf].buftype
                        if name == "" or bt ~= "" then
                            pcall(vim.api.nvim_buf_delete, buf, { force = true })
                        end
                    end
                end
            end,
        })

        -- nvim을 인자 없이 실행한 경우에만 자동 복원
        if vim.fn.argc() == 0 then
            vim.api.nvim_create_autocmd("VimEnter", {
                nested = true,
                callback = function()
                    require("persistence").load()
                end,
            })
        end
    end,
}
