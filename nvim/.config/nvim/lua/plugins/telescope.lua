return {
  {
    "nvim-telescope/telescope.nvim",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "nvim-telescope/telescope-file-browser.nvim",
    },
    cmd = "Telescope",
    keys = {
      { "<leader>fe", desc = "File Browser" },
    },
    config = function()
      local telescope = require("telescope")
      local actions = require("telescope.actions")
      telescope.setup({
        defaults = {
          mappings = {
            n = {
              ["<Down>"] = actions.move_selection_next,
              ["<Up>"] = actions.move_selection_previous,
            },
            i = {
              ["<Down>"] = actions.move_selection_next,
              ["<Up>"] = actions.move_selection_previous,
            },
          },
        },
        extensions = {
          file_browser = {
            hidden = true,
            hijack_netrw = false,
          },
        },
      })
      telescope.load_extension("file_browser")

      vim.keymap.set("n", "<leader>fe", function()
        telescope.extensions.file_browser.file_browser({ path = vim.fn.getcwd() })
      end, { desc = "File Browser" })
    end,
  },
  {
    "nvim-telescope/telescope-file-browser.nvim",
    dependencies = { "nvim-telescope/telescope.nvim", "nvim-lua/plenary.nvim" },
  },
}
