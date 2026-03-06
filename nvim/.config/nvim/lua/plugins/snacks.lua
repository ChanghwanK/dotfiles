return {
  "folke/snacks.nvim",
  priority = 1000,
  lazy = false,
  ---@type snacks.Config
  opts = {
    bigfile = { enabled = true },
    notifier = { enabled = true },
    quickfile = { enabled = true },
    statuscolumn = { enabled = true },
    words = { enabled = true },
    bufdelete = { enabled = true },
    picker = {
      enabled = true,
      sources = {
        explorer = {
          hidden = true,
          watch = true, -- 외부 프로세스가 파일 생성/삭제 시 자동 반영
          on_show = function(picker)
            vim.schedule(function()
              local win = picker.layout.root.win
              if win and vim.api.nvim_win_is_valid(win) then
                local width = vim.api.nvim_win_get_width(win)
                require("barbar.api").set_offset(width + 1, "Explorer", nil, "left")
              end
            end)
          end,
          on_close = function()
            require("barbar.api").set_offset(0, "", nil, "left")
          end,
        },
      },
    },
    dashboard = {
      enabled = true,
      preset = {
        header = "",
        keys = {
          { icon = " ", key = "r", desc = "세션 복원",    action = function() require("persistence").load() end },
          { icon = " ", key = "e", desc = "새 파일",      action = ":ene | startinsert" },
          { icon = " ", key = "f", desc = "파일 찾기",    action = function() Snacks.picker.files({ hidden = true }) end },
          { icon = " ", key = "g", desc = "최근 파일",    action = function() Snacks.picker.recent() end },
          { icon = " ", key = "s", desc = "텍스트 검색",  action = function() Snacks.picker.grep({ hidden = true }) end },
          { icon = " ", key = "c", desc = "설정 열기",    action = ":e ~/.config/nvim/init.lua" },
          { icon = "󰅙 ", key = "q", desc = "종료",        action = ":qa" },
        },
      },
      sections = {
        { section = "header" },
        { section = "keys", gap = 1, padding = 1 },
        { text = { { "Happy coding! 🚀", hl = "Comment" } }, align = "center", padding = 1 },
      },
    },
    -- 터미널 설정 수정
    terminal = {
      enabled = true,
      win = {
        position = "float",
        border = "rounded",
        width = 0.8,
        height = 0.8,
        -- [추가됨] 윈도우 옵션 설정
        wo = {
          -- NormalFloat(플로팅 배경)을 Normal(에디터 배경)과 같게 설정하여 색상 통일
          winhighlight = "Normal:Normal,FloatBorder:SpecialChar,NormalFloat:Normal",
        },
      },
    },
  },
  config = function(_, opts)
    local header_large = [[
  ███╗   ██╗███████╗ ██████╗ ██╗   ██╗██╗███╗   ███╗
  ████╗  ██║██╔════╝██╔═══██╗██║   ██║██║████╗ ████║
  ██╔██╗ ██║█████╗  ██║   ██║██║   ██║██║██╔████╔██║
  ██║╚██╗██║██╔══╝  ██║   ██║╚██╗ ██╔╝██║██║╚██╔╝██║
  ██║ ╚████║███████╗╚██████╔╝ ╚████╔╝ ██║██║ ╚═╝ ██║
  ╚═╝  ╚═══╝╚══════╝ ╚═════╝   ╚═══╝  ╚═╝╚═╝     ╚═╝]]
    local header_small = [[
  ╔╗╔╔═╗╔═╗╦  ╦╦╔╦╗
  ║║║║╣ ║ ║╚╗╔╝║║║║
  ╝╚╝╚═╝╚═╝ ╚╝ ╩╩ ╩]]

    opts.dashboard.preset.header = vim.o.columns >= 55 and header_large or header_small
    require("snacks").setup(opts)

    -- VimResized 시 대시보드 헤더 갱신
    vim.api.nvim_create_autocmd("VimResized", {
      callback = function()
        local new_header = vim.o.columns >= 55 and header_large or header_small
        if Snacks.config.dashboard.preset.header ~= new_header then
          Snacks.config.dashboard.preset.header = new_header
          for _, buf in ipairs(vim.api.nvim_list_bufs()) do
            if vim.api.nvim_buf_is_valid(buf) and vim.bo[buf].filetype == "snacks_dashboard" then
              vim.schedule(function() Snacks.dashboard() end)
              break
            end
          end
        end
      end,
    })

    local mapKey = require("utils.keyMapper").mapKey
    -- [추가] 스크래치 패드 토글 (Leader + s)
    mapKey("<leader>ns", function() Snacks.scratch() end, "n", { desc = "Toggle Scratch Pad" })
    
    -- [추가] 로그 파일 같은 것을 볼 때 유용한 스크래치 버퍼 (내용 유지 안됨)
    mapKey("<leader>S", function() Snacks.scratch.select() end, "n", { desc = "Select Scratch Buffer" })

    -- Toggle Terminal
    -- mapKey("<c-/>", function() Snacks.terminal() end, { "n", "t" }, { desc = "Toggle Terminal" })
    mapKey("<c-_>", function() Snacks.terminal() end, { "n", "t" }, { desc = "Toggle Terminal" })

    -- Lazygit
    mapKey("<leader>gg", function() Snacks.lazygit() end, "n", { desc = "Lazygit" })

    -- Picker (telescope 대체)
    mapKey('<leader>ff', function() Snacks.picker.files({ hidden = true }) end, "n", { desc = "Find Files" })
    mapKey('<leader>fg', function() Snacks.picker.grep({ hidden = true }) end, "n", { desc = "Live Grep" })
    mapKey('<leader>bf', function() Snacks.picker.buffers() end, "n", { desc = "Buffers" })
    mapKey('<leader>fh', function() Snacks.picker.help() end, "n", { desc = "Help Tags" })
    mapKey('<leader>fi', function() Snacks.picker.lsp_implementations() end, "n", { desc = "LSP Implementations" })

    -- 마지막 버퍼를 닫으면 대시보드 표시
    vim.api.nvim_create_autocmd("BufDelete", {
      callback = function(ev)
        -- dashboard 버퍼 삭제 시 무시 (explorer confirm 시 충돌 방지)
        if vim.bo[ev.buf].filetype == "snacks_dashboard" then
          return
        end
        vim.schedule(function()
          -- 이름 있는 버퍼만 카운트 (Neovim 자동 생성 [No Name] 제외)
          local real_bufs = vim.tbl_filter(function(b)
            return vim.bo[b].buflisted and vim.api.nvim_buf_get_name(b) ~= ""
          end, vim.api.nvim_list_bufs())
          if #real_bufs == 0 then
            Snacks.dashboard()
          end
        end)
      end,
    })
  end,
}
