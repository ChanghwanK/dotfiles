return {
  "nvimtools/hydra.nvim",
  event = "VeryLazy",
  config = function()
    local Hydra = require("hydra")

    Hydra({
      name = "Window Resize",
      mode = "n",
      body = "<Leader>w",
      heads = {
        { "h", "<C-w><", { desc = "←" } },
        { "j", "<C-w>+", { desc = "↓" } },
        { "k", "<C-w>-", { desc = "↑" } },
        { "l", "<C-w>>", { desc = "→" } },
        { "q", nil, { exit = true, desc = "exit" } },
      },
    })
  end,
}