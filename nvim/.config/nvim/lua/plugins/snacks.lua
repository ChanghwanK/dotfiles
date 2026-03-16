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
    lazygit = { enabled = true },
    picker = {
      enabled = true,
      sources = {
        explorer = {
          hidden = true,
          watch = true,
          actions = {
            -- [패치] (1) 디렉토리 y+p 복사 지원, (2) 이름 충돌 시 _copy suffix 자동 추가
            explorer_paste = function(picker)
              local files = vim.split(vim.fn.getreg(vim.v.register or "+") or "", "\n", { plain = true })
              files = vim.tbl_filter(function(file)
                return file ~= "" and (vim.fn.filereadable(file) == 1 or vim.fn.isdirectory(file) == 1)
              end, files)
              if #files == 0 then
                return Snacks.notify.warn(("The `%s` register does not contain any files"):format(vim.v.register or "+"))
              end
              local dir = picker:dir()
              local svim = require("snacks.util.vim")
              -- 충돌 시 suffix를 붙여 unique한 경로를 생성하는 헬퍼
              local function unique_path(target)
                if not vim.uv.fs_stat(target) then
                  return target
                end
                local parent = vim.fs.dirname(target)
                local base = vim.fn.fnamemodify(target, ":t")
                -- 확장자 분리 (디렉토리는 ext 없음)
                local name, ext
                if vim.fn.isdirectory(target) == 1 or not base:find("%.") then
                  name, ext = base, ""
                else
                  name = base:match("^(.+)%.[^.]+$") or base
                  ext = base:match("^.+(%.[^.]+)$") or ""
                end
                local i = 1
                local candidate
                repeat
                  local suffix = i == 1 and "_copy" or ("_copy" .. i)
                  candidate = parent .. "/" .. name .. suffix .. ext
                  i = i + 1
                until not vim.uv.fs_stat(candidate)
                return candidate
              end
              for _, path in ipairs(files) do
                local name = vim.fn.fnamemodify(path, ":t")
                local to = svim.fs.normalize(dir .. "/" .. name)
                to = unique_path(to)
                Snacks.picker.util.copy_path(svim.fs.normalize(path), to)
              end
              local Tree = require("snacks.explorer.tree")
              Tree:refresh(dir)
              Tree:open(dir)
              picker:find()
            end,
          },
          on_show = function(picker)
            vim.schedule(function()
              local win = picker.layout.root.win
              if win and vim.api.nvim_win_is_valid(win) then
                local width = vim.api.nvim_win_get_width(win)
                require("barbar.api").set_offset(width + 1, "Explorer", nil, "left")
              end
              -- 활성 버퍼 디렉토리만 펼침 (나머지 모두 접기)
              local buf_path = vim.api.nvim_buf_get_name(0)
              if buf_path ~= "" then
                local buf_dir = vim.fn.fnamemodify(buf_path, ":h")
                local Tree = require("snacks.explorer.tree")
                Tree:close_all(picker:cwd())
                Tree:open(buf_dir)
                picker:find()
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

    -- [패치] Explorer 파일 정렬: 디렉토리 우선, 파일은 수정시간 내림차순 (최신순)
    local Tree = require("snacks.explorer.tree")
    local orig_walk = Tree.walk
    Tree.walk = function(self, node, fn, opts_walk)
      local abort = fn(node)
      if abort ~= nil then
        return abort
      end
      local children = vim.tbl_values(node.children)
      table.sort(children, function(a, b)
        if a.dir ~= b.dir then
          return a.dir
        end
        if a.dir and b.dir then
          return a.name < b.name
        end
        local sa = vim.uv.fs_stat(a.path)
        local sb = vim.uv.fs_stat(b.path)
        if sa and sb then
          return sa.mtime.sec > sb.mtime.sec
        end
        return a.name > b.name
      end)
      for c, child in ipairs(children) do
        child.last = c == #children
        abort = false
        if child.dir and (child.open or (opts_walk and opts_walk.all)) then
          abort = self:walk(child, fn, opts_walk)
        else
          abort = fn(child)
        end
        if abort then
          return true
        end
      end
      return false
    end

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

    -- 버퍼 전환 시 explorer 트리 동기화 (활성 버퍼 디렉토리만 펼침)
    local _explorer_syncing = false
    vim.api.nvim_create_autocmd("BufEnter", {
      callback = function()
        -- 재진입 방지 (explorer:find() 실행 중 BufEnter 재발생 시 무시)
        if _explorer_syncing then return end
        -- unlisted 버퍼(explorer list 등)에서는 실행하지 않음 → barbar 재귀 차단
        if not vim.bo.buflisted then return end
        local explorer = Snacks.picker.get({ source = "explorer" })[1]
        if not explorer then return end
        local buf_path = vim.api.nvim_buf_get_name(0)
        if buf_path == "" then return end
        local buf_dir = vim.fn.fnamemodify(buf_path, ":h")
        local Tree = require("snacks.explorer.tree")
        _explorer_syncing = true
        Tree:close_all(explorer:cwd())
        Tree:open(buf_dir)
        explorer:find()
        _explorer_syncing = false
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
