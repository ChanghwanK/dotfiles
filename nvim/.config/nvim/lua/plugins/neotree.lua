return {
  "nvim-neo-tree/neo-tree.nvim",
  enabled = false, -- [비활성화] snacks.picker.explorer로 대체. 롤백: enabled = true
  branch = "v3.x",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "nvim-tree/nvim-web-devicons",
    "MunifTanjim/nui.nvim",
  },
  
  config = function()
    vim.keymap.set('n', '<leader>e', ':Neotree toggle<CR>', { desc = 'NeoTree toggle' })
    local use_transparent = vim.g.nvim_theme == "terminal"
    
    require("neo-tree").setup({
      -- [추천 1] 소스 선택기 (상단 탭)
      source_selector = {
        winbar = true,
        content_layout = "center",
        sources = {
          { source = "filesystem" },
          { source = "buffers" },
          { source = "git_status" },
        },
      },

      window = {
        width = 30,
        -- [추천 2] 편리한 키 매핑
        mappings = {
          ["l"] = "open",
          ["h"] = "close_node",
          ["Y"] = {
            function(state)
              local node = state.tree:get_node()
              local path = node:get_id()
              vim.fn.setreg("+", path, "c")
            end,
            desc = "Copy Path to Clipboard",
          },
        },
      },

      filesystem = {
        -- [추천 3] 파일 변경 자동 감지 (매우 중요)
        use_libuv_file_watcher = true,
        filtered_items = {
          visible = true,
          hide_dotfiles = false,
          hide_gitignored = true, -- .gitignore 된 파일은 숨김 (필요시 false)
        },
        follow_current_file = {
          enabled = true,
        },
        -- netrw를 완전히 대체
        hijack_netrw_behavior = "disabled",
      },

      default_component_configs = {
        -- [추천 4] 들여쓰기 가이드
        indent = {
          with_markers = true,
          indent_marker = "│",
          last_indent_marker = "└",
          indent_size = 2,
        },
        -- [추천 5] Git 상태 아이콘
        git_status = {
          symbols = {
            added     = "", -- 아이콘 대신 색상으로만 구분하려면 비워둠
            modified  = "",
            conflict  = "",
            renamed   = "󰁕",
            deleted   = "✖",
            ignored   = "",
            unstaged  = "󰄱",
            staged    = "",
            untracked = "",
          }
        },
      },
      
      window_transparent = use_transparent,
    })
  end,
}