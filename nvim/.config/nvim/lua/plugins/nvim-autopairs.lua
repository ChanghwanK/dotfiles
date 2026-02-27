return {
    "windwp/nvim-autopairs",
    event = "InsertEnter",
    config = function()
        local autopairs = require("nvim-autopairs")
        
        autopairs.setup({
            check_ts = true,
            ts_config = {
                lua = { "string", "comment" },
                javascript = { "string", "template_string" },
            },
        })
    end,
}