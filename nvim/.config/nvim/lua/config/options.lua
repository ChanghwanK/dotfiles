local opt = vim.opt

vim.opt.updatetime = 2000
vim.opt.timeoutlen = 300

-- 테마 설정 로드
local theme = require("config.theme")
vim.g.nvim_theme = theme

-- copy & past
opt.clipboard:append("unnamedplus")

-- tab/indent
opt.tabstop = 2
opt.shiftwidth = 2
opt.softtabstop = 2
opt.expandtab = true
opt.smartindent = true
opt.wrap = false

-- Search
opt.incsearch = true
opt.ignorecase = true
opt.smartcase = true

-- visual 
opt.number = true
opt.relativenumber = true
opt.termguicolors = true
opt.signcolumn = "yes"

-- 세션 저장 시 포함할 항목 (persistence.nvim이 사용)
opt.sessionoptions = "buffers,curdir,folds,tabpages,winsize"

-- etc
opt.encoding = "UTF-8"
opt.cmdheight = 1
opt.scrolloff = 10
opt.mouse:append("a")

-- 아이콘 폰트 설정
vim.g.have_nerd_font = true  -- NerdFont 사용 표시

-- GUI 폰트 설정 (Neovide, Neovim-qt 등에서 사용)
if vim.g.neovide then
  vim.o.guifont = "JetBrainsMono Nerd Font:h14"
  -- vim.o.guifont = "FiraCode Nerd Font:h14"
  -- vim.o.guifont = "Hack Nerd Font:h14"
  -- vim.o.guifont = "MesloLGS Nerd Font:h14"
else
  -- 터미널 Neovim의 경우 터미널 폰트 설정을 따릅니다
  -- 
  -- NerdFont: https://www.nerdfonts.com/
  -- - iTerm2: Preferences → Profiles → Text → Font
  -- - Alacritty: ~/.config/alacritty/alacritty.yml에서 font.normal.family
  -- - Kitty: ~/.config/kitty/kitty.conf에서 font_family
  --
  -- Nonicons: https://github.com/yamatsum/nonicons
  -- - 메인 폰트는 NerdFont 사용
  -- - "non-ascii" 폰트를 nonicons로 설정 (iTerm2)
  -- - Kitty의 경우: symbol_map U+f101-U+f25c nonicons
end

-- markdown ftplugin이 tabstop=4로 덮어쓰는 것을 방지
vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    vim.opt_local.tabstop = 2
    vim.opt_local.shiftwidth = 2
    vim.opt_local.softtabstop = 2
  end,
})

-- Helm 템플릿 filetype 감지: templates/ 하위 yaml/tpl/txt 파일을 helm으로 인식
vim.filetype.add({
  pattern = {
    [".*/templates/.*%.yaml"] = "helm",
    [".*/templates/.*%.yml"] = "helm",
    [".*/templates/.*%.tpl"] = "helm",
    ["helmfile.*%.yaml"] = "helm",
  },
})

-- helm filetype에 gotmpl treesitter 파서 매핑
vim.treesitter.language.register("gotmpl", "helm")

-- 입력 모드(Insert)에서 나갈 때(Leave) 자동으로 파일 저장
vim.api.nvim_create_autocmd("InsertLeave", {
  pattern = "*",
  command = "update", -- 변경된 내용이 있을 때만 저장
})

-- 진단(Diagnostics) 설정
local signs = { Error = "󰅚 ", Warn = "󰀪 ", Hint = "󰌶 ", Info = " " }

vim.diagnostic.config({
    virtual_text = true,        -- 라인 끝에 에러 메시지 표시
    signs = {
        text = {
            [vim.diagnostic.severity.ERROR] = signs.Error,
            [vim.diagnostic.severity.WARN] = signs.Warn,
            [vim.diagnostic.severity.HINT] = signs.Hint,
            [vim.diagnostic.severity.INFO] = signs.Info,
        },
    },
    underline = true,           -- 빨간 줄로 표시
    update_in_insert = false,   -- 삽입 모드에서는 업데이트 안 함
    severity_sort = true,       -- 심각도 순으로 정렬
})
