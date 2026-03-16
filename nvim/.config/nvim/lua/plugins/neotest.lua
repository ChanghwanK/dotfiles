return {
  "nvim-neotest/neotest",
  dependencies = {
    "nvim-neotest/nvim-nio",
    "nvim-lua/plenary.nvim",
    "nvim-treesitter/nvim-treesitter",
    "nvim-neotest/neotest-go",
    "nvim-neotest/neotest-python",
  },
  keys = {
    { "<leader>tt", function() require("neotest").run.run() end,                          desc = "가장 가까운 테스트 실행" },
    { "<leader>tf", function() require("neotest").run.run(vim.fn.expand("%")) end,        desc = "현재 파일 테스트 실행" },
    { "<leader>ts", function() require("neotest").summary.toggle() end,                   desc = "테스트 요약 토글" },
    { "<leader>to", function() require("neotest").output_panel.toggle() end,              desc = "테스트 출력 패널 토글" },
    { "<leader>tS", function() require("neotest").run.stop() end,                         desc = "테스트 중지" },
    { "]t",         function() require("neotest").jump.next({ status = "failed" }) end,   desc = "다음 실패 테스트로" },
    { "[t",         function() require("neotest").jump.prev({ status = "failed" }) end,   desc = "이전 실패 테스트로" },
  },
  config = function()
    require("neotest").setup({
      adapters = {
        require("neotest-go")({
          experimental = { test_table = true },
          args = { "-count=1", "-timeout=60s" },
        }),
        require("neotest-python")({
          dap = { justMyCode = false },
          runner = "pytest",
        }),
      },
      output = { open_on_run = false },
      status = { virtual_text = true, signs = true },
    })
  end,
}
