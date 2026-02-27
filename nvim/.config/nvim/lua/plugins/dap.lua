return {
    -- DAP 코어
    {
        "mfussenegger/nvim-dap",
        dependencies = {
            -- Mason으로 디버그 어댑터 자동 설치
            "williamboman/mason.nvim",
            "jay-babu/mason-nvim-dap.nvim",
            -- DAP UI
            "rcarriga/nvim-dap-ui",
            "nvim-neotest/nvim-nio",  -- dap-ui 의존성
            -- 변수 hover 지원
            "theHamsta/nvim-dap-virtual-text",
        },
        config = function()
            local dap = require("dap")
            local dapui = require("dapui")
            local mapKey = require("utils.keyMapper").mapKey

            -- Mason으로 디버그 어댑터 자동 설치
            require("mason-nvim-dap").setup({
                ensure_installed = {
                    "debugpy",   -- Python
                    "delve",     -- Go
                    "js",        -- JavaScript/TypeScript
                },
                automatic_installation = true,
                handlers = {},
            })

            -- 가상 텍스트로 변수 값 표시
            require("nvim-dap-virtual-text").setup({
                commented = true,  -- 주석 형태로 표시
            })

            -- DAP UI 설정
            dapui.setup({
                icons = { expanded = "▾", collapsed = "▸", current_frame = "▸" },
                layouts = {
                    {
                        -- 왼쪽: 스코프/변수/감시
                        elements = {
                            { id = "scopes",      size = 0.40 },
                            { id = "breakpoints", size = 0.20 },
                            { id = "stacks",      size = 0.20 },
                            { id = "watches",     size = 0.20 },
                        },
                        size = 40,
                        position = "left",
                    },
                    {
                        -- 하단: REPL + 콘솔
                        elements = {
                            { id = "repl",    size = 0.5 },
                            { id = "console", size = 0.5 },
                        },
                        size = 10,
                        position = "bottom",
                    },
                },
            })

            -- 디버그 시작/종료 시 UI 자동 열기/닫기
            dap.listeners.after.event_initialized["dapui_config"] = function()
                dapui.open()
            end
            dap.listeners.before.event_terminated["dapui_config"] = function()
                dapui.close()
            end
            dap.listeners.before.event_exited["dapui_config"] = function()
                dapui.close()
            end

            -- 중단점 아이콘
            vim.fn.sign_define("DapBreakpoint",          { text = "🔴", texthl = "", linehl = "", numhl = "" })
            vim.fn.sign_define("DapBreakpointCondition", { text = "🟡", texthl = "", linehl = "", numhl = "" })
            vim.fn.sign_define("DapBreakpointRejected",  { text = "⭕", texthl = "", linehl = "", numhl = "" })
            vim.fn.sign_define("DapLogPoint",            { text = "📝", texthl = "", linehl = "", numhl = "" })
            vim.fn.sign_define("DapStopped",             { text = "▶️",  texthl = "", linehl = "DapStoppedLine", numhl = "" })

            -- 키맵: IDE 스타일 F키
            mapKey("<F5>",  dap.continue,        "n", { desc = "디버그 시작/계속" })
            mapKey("<F10>", dap.step_over,        "n", { desc = "다음 줄 (Step Over)" })
            mapKey("<F11>", dap.step_into,        "n", { desc = "함수 진입 (Step Into)" })
            mapKey("<F12>", dap.step_out,         "n", { desc = "함수 탈출 (Step Out)" })
            mapKey("<S-F5>", dap.terminate,       "n", { desc = "디버그 종료" })

            -- 키맵: leader 기반
            mapKey("<leader>db", dap.toggle_breakpoint, "n", { desc = "중단점 토글" })
            mapKey("<leader>dB", function()
                dap.set_breakpoint(vim.fn.input("중단 조건: "))
            end, "n", { desc = "조건부 중단점" })
            mapKey("<leader>dl", function()
                dap.set_breakpoint(nil, nil, vim.fn.input("로그 메시지: "))
            end, "n", { desc = "로그 중단점" })
            mapKey("<leader>dr", dap.repl.open,   "n", { desc = "REPL 열기" })
            mapKey("<leader>du", dapui.toggle,    "n", { desc = "DAP UI 토글" })
            mapKey("<leader>de", dapui.eval,      { "n", "v" }, { desc = "표현식 평가" })
            mapKey("<leader>dc", dap.continue,    "n", { desc = "디버그 계속" })
            mapKey("<leader>dn", dap.step_over,   "n", { desc = "Step Over" })
            mapKey("<leader>di", dap.step_into,   "n", { desc = "Step Into" })
            mapKey("<leader>do", dap.step_out,    "n", { desc = "Step Out" })
            mapKey("<leader>dt", dap.terminate,   "n", { desc = "디버그 종료" })
        end,
    },
}
