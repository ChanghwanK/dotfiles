return {
    'nvim-treesitter/nvim-treesitter',
    lazy = false,
    build = ':TSUpdate',
    config = function()
        -- require를 안전하게 감싸서, 플러그인이 없을 때 에러가 나지 않게 함
        local status_ok, configs = pcall(require, "nvim-treesitter.configs")
        if not status_ok then
            return
        end

        configs.setup({
            ensure_installed = {"c", "lua", "vim", "python", "go", "html", "javascript", "terraform" },
            sync_install = false,
            highlight = { enable = true },
            indent = { enable = true },
            incremental_selection = {
                enable = true,
                keymaps = {
                    init_selection = "<CR>",    -- 엔터키로 블록 선택 시작
                    node_incremental = "<CR>",  -- 엔터키를 누를 때마다 상위 블록으로 확장
                    scope_incremental = false,     -- 탭키로 스코프 확장
                    node_decremental = "<BS>",  -- 백스페이스로 선택 영역 축소
                },
            },
        })
    end
}