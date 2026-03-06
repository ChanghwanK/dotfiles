return {
    -- URL 열기 (gx 강화)
    {
        "chrishrb/gx.nvim",
        keys = { { "gx", "<cmd>Browse<cr>", mode = { "n", "x" } } },
        cmd = { "Browse" },
        init = function()
            vim.g.netrw_nogx = 1 -- 기본 netrw gx 비활성화
        end,
        opts = {
            open_browser_app = "open", -- macOS
            handlers = {
                plugin  = true, -- lazy.nvim 플러그인 이름 → GitHub으로 열기
                github  = true, -- GitHub 단축 경로 지원
                brewfile = true,
                package_json = true,
                search  = false, -- URL 아닌 텍스트 검색 비활성화
            },
            handler_options = {
                search_engine = "google",
            },
        },
    },

    -- URL 시각적 하이라이트
    {
        "itchyny/vim-highlighturl",
        event = { "BufReadPre", "BufNewFile" },
    },
}
