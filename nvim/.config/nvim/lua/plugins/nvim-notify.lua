return {
  "rcarriga/nvim-notify",
  enabled = false, -- snacks.notifier가 vim.notify를 담당하므로 비활성화 (충돌 방지)
  config = function()
    local notify = require("notify")
    
    -- 터미널 테마 사용 시 투명 배경
    local bg_color = vim.g.nvim_theme == "terminal" and "#00000000" or "#000000"
    
    notify.setup({
      -- 알림 레벨별 배경색
      background_colour = bg_color,
      
      -- 알림 표시 시간 (밀리초)
      timeout = 3000,
      
      -- 최대 알림 창 개수
      max_width = 50,
      max_height = 10,
      
      -- 알림 위치 (top_left, top_right, bottom_left, bottom_right)
      top_down = true,
      
      -- 알림 애니메이션
      stages = "fade_in_slide_out",
      
      -- 최소 레벨 (DEBUG, INFO, WARN, ERROR)
      level = "INFO",
      
      -- 렌더링 스타일
      render = "default",
      
      -- FPS
      fps = 30,
    })
    
    -- Neovim의 기본 알림을 nvim-notify로 대체
    vim.notify = notify
  end,
}
