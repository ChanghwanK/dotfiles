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
      attach_navic = false,   -- lsp.lua에서 navic.attach() 직접 호출 중이므로 중복 방지
      show_dirname = true,    -- 상위 디렉토리 표시 (~/workspace/project/cmd)
      show_basename = true,   -- 파일명 표시 (main.go)
      show_modified = true,   -- 수정 여부 표시
      -- VS Code처럼 경로 구분자 스타일
      separator = "  ",
      lead_custom_section = function()
        return " "
      end,
    },
  }