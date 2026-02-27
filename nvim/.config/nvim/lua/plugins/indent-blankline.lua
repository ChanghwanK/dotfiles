return {
    "lukas-reineke/indent-blankline.nvim",
    main = "ibl",
    event = { "BufReadPost", "BufNewFile" },
    config = function()
        local ibl = require("ibl")        
        ibl.setup({
            indent = {
                char = "▏", -- 가장 얇은 문자 (Left One Eighth Block)
                tab_char = "▏"
            },
            scope = {
                enabled = true,
                show_start = true,
                show_end = false,
                char = "▎", -- 살짝 굵은 문자 (Left One Quarter Block)
            },
        })
    end,
}