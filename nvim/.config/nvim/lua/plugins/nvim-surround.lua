return {
    "kylechui/nvim-surround",
    version = "*",
    event = "VeryLazy",
    config = function()
        -- v4부터 keymaps 설정은 setup()에서 제거됨, 기본값 사용
        -- Normal 모드:
        --   ys{motion}{char}  - 감싸기 (e.g. ysiw" → 단어를 "로 감싸기)
        --   ds{char}          - 삭제    (e.g. ds"  → " 제거)
        --   cs{old}{new}      - 변경    (e.g. cs"' → "를 '로 변경)
        -- Visual 모드:
        --   S{char}           - 선택 영역 감싸기
        -- Insert 모드:
        --   <C-g>s{char}      - 커서 위치에 감싸기
        require("nvim-surround").setup({})
    end,
}
