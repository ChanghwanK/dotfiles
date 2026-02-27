return {
  'nvim-lualine/lualine.nvim',
  dependencies = { 
    'nvim-tree/nvim-web-devicons',
  },
  config = function()
    -- ... (기존 테마 설정 코드 유지) ...
    local theme_map = {
      gruvbox = "gruvbox",
      onedark = "onedark",
      vague = "auto",
      terminal = "auto"
    }
    
    local current_theme = vim.g.nvim_theme or "gruvbox"
    local lualine_theme = theme_map[current_theme] or "auto"

    -- 1. 파이썬 환경 표시 함수
    local function python_env()
      local venv = os.getenv('VIRTUAL_ENV')
      local conda = os.getenv('CONDA_DEFAULT_ENV')
      
      if venv then
        -- 경로에서 마지막 디렉토리 이름만 추출 (예: /home/user/.venv -> .venv)
        local env_name = string.match(venv, '[^/]+$')
        return ' ' .. env_name
      elseif conda then
        return ' ' .. conda
      end
      return ''
    end

    -- 2. 쿠버네티스 컨텍스트 표시 함수 (파일 읽기 방식)
    local function k8s_ctx()
      -- KUBECONFIG 환경변수가 있으면 그것을, 없으면 기본 경로 사용
      local kubeconfig = os.getenv("KUBECONFIG") or (os.getenv("HOME") .. "/.kube/config")
      local f = io.open(kubeconfig, "r")
      if f then
        local content = f:read("*a")
        f:close()
        -- "current-context: <context>" 패턴 찾기
        local ctx = string.match(content, "current%-context: ([%w%-%_%.%@%/]+)")
        if ctx then
          return "󱃾 " .. ctx
        end
      end
      return ""
    end
    
    require("lualine").setup({
      options = {
        theme = lualine_theme,
        icons_enabled = true,
        component_separators = { left = '', right = ''},
        section_separators = { left = '', right = ''},
      },
      sections = {
        lualine_a = {'mode'},
        lualine_b = {
          { 'branch', icon = '󰊢' },
          'diff',
          'diagnostics',
        },
        lualine_c = {'filename'},
        -- lualine_x 섹션에 함수 추가
        lualine_x = {
          { python_env, color = { fg = '#ffbc03' } }, -- 노란색 아이콘 (선택사항)
          { k8s_ctx, color = { fg = '#326ce5' } },    -- 파란색 아이콘 (선택사항)
          'encoding', 
          'fileformat', 
          'filetype'
        },
        lualine_y = {'progress'},
        lualine_z = {'location'}
      },
    })
  end
}