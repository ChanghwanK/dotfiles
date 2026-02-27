return {
    "utilyre/barbecue.nvim",
    name = "barbecue",
    version = "*",
    dependencies = {
      "SmiteshP/nvim-navic",
      "nvim-tree/nvim-web-devicons",
    },
    event = "LspAttach", -- LSP가 붙을 때 로드됨
    opts = {
      -- 기본 설정 사용
      -- 필요시 테마나 아이콘 설정을 여기서 변경 가능
    },
  }