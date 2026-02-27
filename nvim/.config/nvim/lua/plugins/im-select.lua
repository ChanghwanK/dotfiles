return {
    "keaising/im-select.nvim",
    config = function()
      require("im_select").setup({
        -- macOS에서 기본 입력기(영어)로 전환할 때 사용할 입력 소스 ID
        default_im_select = "com.apple.keylayout.ABC",
        
        -- [추가] 플러그인은 기본적으로 'macism'을 찾으므로, 설치한 'im-select'를 쓰도록 지정
        default_command = "im-select",
        
        -- 자동 복원 기능
        set_previous_events = { "InsertEnter" },
        
        -- Normal 모드 진입 시 영어로 전환
        set_default_events = { "VimEnter", "FocusGained", "InsertLeave", "CmdlineLeave" },
      })
    end,
  }