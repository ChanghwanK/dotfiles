return {
  "APZelos/blamer.nvim",
  event = "BufReadPre",
  config = function()
    vim.g.blamer_enabled = 1
    vim.g.blamer_delay = 100
    vim.g.blamer_template = "<committer>, <committer-time> • <summary>"
    vim.g.blamer_relative_time = 1
    vim.g.blamer_show_in_visual_modes = 1
    vim.g.blamer_show_in_insert_modes = 1
  end,
}
