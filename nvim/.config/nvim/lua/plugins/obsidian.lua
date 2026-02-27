return {
    "obsidian-nvim/obsidian.nvim",
    version = "*",
    ft = "markdown",
    opts = {
        legacy_commands = false,

        workspaces = {
            {
                name = "personal",
                path = "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/",
            },
        },

        -- blink.cmp 사용 중이므로 blink 활성화
        completion = {
            nvim_cmp = false,
            blink = true,
            min_chars = 2,
        },

        -- snacks.picker 사용
        picker = {
            name = "snacks",
        },

        daily_notes = {
            folder = "daily",
            date_format = "%Y-%m-%d",
            template = nil,
        },

        templates = {
            folder = "templates",
            date_format = "%Y-%m-%d",
            time_format = "%H:%M",
        },

        -- 새 노트 위치: 현재 작업 디렉토리
        new_notes_location = "current_dir",
        preferred_link_style = "wiki",

        attachments = {
            img_folder = "attachments",
        },
    },

    keys = {
        { "<leader>on", "<cmd>Obsidian new<cr>",           desc = "New note" },
        { "<leader>oo", "<cmd>Obsidian quick_switch<cr>",  desc = "Quick switch" },
        { "<leader>os", "<cmd>Obsidian search<cr>",        desc = "Search notes" },
        { "<leader>od", "<cmd>Obsidian today<cr>",         desc = "Daily note (today)" },
        { "<leader>oD", "<cmd>Obsidian yesterday<cr>",     desc = "Daily note (yesterday)" },
        { "<leader>ob", "<cmd>Obsidian backlinks<cr>",     desc = "Backlinks" },
        { "<leader>ol", "<cmd>Obsidian links<cr>",         desc = "Links in note" },
        { "<leader>ot", "<cmd>Obsidian tags<cr>",          desc = "Browse tags" },
        { "<leader>oT", "<cmd>Obsidian toc<cr>",           desc = "Table of contents" },
        { "<leader>op", "<cmd>Obsidian paste_img<cr>",     desc = "Paste image" },
        { "<leader>or", "<cmd>Obsidian rename<cr>",        desc = "Rename note" },
        { "<leader>ow", "<cmd>Obsidian workspace<cr>",     desc = "Switch workspace" },
        -- visual mode
        { "<leader>ol", "<cmd>Obsidian link<cr>",          desc = "Link selection",    mode = "v" },
        { "<leader>oe", "<cmd>Obsidian extract_note<cr>",  desc = "Extract to note",   mode = "v" },
    },
}
