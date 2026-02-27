return {
    "ThePrimeagen/harpoon",
    branch = "harpoon2",
    dependencies = { "nvim-lua/plenary.nvim" },
    config = function()
        local harpoon = require("harpoon")
        local mapKey = require("utils.keyMapper").mapKey

        harpoon:setup({
            settings = {
                save_on_toggle = true,   -- 메뉴 닫을 때 자동 저장
                sync_on_ui_close = true,
            },
        })

        -- 현재 파일 등록/해제
        mapKey("<leader>ha", function() harpoon:list():add() end,    "n", { desc = "Harpoon: 파일 추가" })

        -- 등록 목록 메뉴 열기
        mapKey("<leader>hh", function()
            harpoon.ui:toggle_quick_menu(harpoon:list())
        end, "n", { desc = "Harpoon: 목록 열기" })

        -- 1~4번 파일로 즉시 이동 (Alt + 숫자)
        mapKey("<M-1>", function() harpoon:list():select(1) end, "n", { desc = "Harpoon: 파일 1" })
        mapKey("<M-2>", function() harpoon:list():select(2) end, "n", { desc = "Harpoon: 파일 2" })
        mapKey("<M-3>", function() harpoon:list():select(3) end, "n", { desc = "Harpoon: 파일 3" })
        mapKey("<M-4>", function() harpoon:list():select(4) end, "n", { desc = "Harpoon: 파일 4" })

        -- 이전/다음 Harpoon 파일로 순환
        mapKey("<M-p>", function() harpoon:list():prev() end, "n", { desc = "Harpoon: 이전 파일" })
        mapKey("<M-n>", function() harpoon:list():next() end, "n", { desc = "Harpoon: 다음 파일" })
    end,
}
