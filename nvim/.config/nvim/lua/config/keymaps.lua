local mapKey = require("utils.keyMapper").mapKey

-- [비활성화] Neo-tree 단축키 — snacks.picker.explorer로 대체. 롤백: 아래 주석 해제 + leader e snacks 줄 제거
-- mapKey('<leader>e', ':Neotree toggle<cr>', 'n', { desc = "파일 탐색기 토글" })
-- mapKey('<leader>ee', ':Neotree focus<cr>', 'n', { desc = "파일 탐색기로 포커스" })
-- mapKey('<leader>eb', '<C-w>p', 'n', { desc = "버퍼로 포커스 (탐색기 → 에디터)" })
mapKey('<leader>e', function() Snacks.picker.explorer({ cwd = vim.fn.getcwd() }) end, 'n', { desc = "파일 탐색기 토글" })

-- indent (들여쓰기 후 선택 영역 유지)
mapKey('<', '<gv', 'v', { desc = "왼쪽 들여쓰기" })
mapKey('>', '>gv', 'v', { desc = "오른쪽 들여쓰기" })


-- 삽입 모드에서 뒤 단어 삭제 (Ctrl + Shift + d)
mapKey("<C-d>", "<Esc>dwa", "i", { desc = "뒤 단어 삭제" })
mapKey('<A-e>', '<C-o>e', 'i', { desc = "단어 맨 뒤로" }) 


-- 복사(y) 후 커서가 시작점으로 튀지 않고 제자리(선택 끝)에 유지되게 함
vim.keymap.set("v", "y", "ygv<Esc>", { desc = "선택 영역 복사 (커서 유지)" })

-- Cmd+C / Cmd+V: macOS 스타일 복사/붙여넣기
vim.keymap.set('n', '<D-c>', '"+yy',        { desc = 'Cmd+C: 현재 줄 복사' })
vim.keymap.set('v', '<D-c>', '"+y',         { desc = 'Cmd+C: 선택 영역 복사' })
vim.keymap.set('i', '<D-c>', '<Esc>"+yyi',  { desc = 'Cmd+C: 현재 줄 복사 (Insert Mode)' })
vim.keymap.set('n', '<D-v>', '"+p',   { desc = 'Cmd+V: 붙여넣기' })
vim.keymap.set('v', '<D-v>', '"+p',   { desc = 'Cmd+V: 붙여넣기' })
vim.keymap.set('i', '<D-v>', '<C-r>+', { desc = 'Cmd+V: 붙여넣기 (Insert Mode)' })

-- nvim-notify 단축키
mapKey('<leader>nh', function() Snacks.notifier.show_history() end, 'n', { desc = '알림 히스토리 보기' })
mapKey('<leader>nd', function() require("notify").dismiss({ silent = true, pending = true }) end, 'n',
  { desc = '모든 알림 닫기' })

-- 버퍼 이동 (Shift + h / Shift + l)
mapKey('<S-h>', ':BufferPrevious<CR>', 'n', { desc = "이전 버퍼로 이동" })
mapKey('<S-l>', ':BufferNext<CR>', 'n', { desc = "다음 버퍼로 이동" })
mapKey('<leader>bd', function() Snacks.bufdelete() end, 'n', { desc = "현재 버퍼 닫기" })
mapKey('<C-w>', function() Snacks.bufdelete() end, 'n', { desc = "현재 버퍼 닫기" })
mapKey('<leader>bo', function() Snacks.bufdelete.other() end, 'n', { desc = "다른 버퍼 모두 닫기 (현재 제외)" })
mapKey('<leader>ba', function() Snacks.bufdelete.all() end, 'n', { desc = "버퍼 모두 닫기" })
mapKey('<leader>bl', ':BufferCloseBuffersLeft<CR>', 'n', { desc = "왼쪽 버퍼 모두 닫기" })
mapKey('<leader>br', ':BufferCloseBuffersRight<CR>', 'n', { desc = "오른쪽 버퍼 모두 닫기" })

-- blamer.nvim (인라인 Git Blame, VSCode GitLens 스타일)
mapKey('<leader>gb', ':BlamerToggle<CR>', 'n', { desc = "Git Blame 인라인 토글" })

-- 창 분할 (Split Window)
mapKey('<leader>sv', ':vsplit<CR>', 'n', { desc = "창 수직 분할 (|)" })
mapKey('<leader>sh', ':split<CR>', 'n', { desc = "창 수평 분할 (-)" })

-- 분할된 창 닫기
mapKey('<leader>sd', ':close<CR>', 'n', { desc = "현재 분할 창 닫기" })

-- [선택한 줄을 위아래로 이동]
-- 창 크기 조절(<A-j/k>)과 충돌 방지를 위해 방향키로 변경했습니다.
-- 노멀 모드: Alt + Down (아래로) / Alt + Up (위로)
mapKey('<A-Down>', ':m .+1<CR>==', 'n', { desc = "현재 줄을 아래로 이동" })
mapKey('<A-Up>', ':m .-2<CR>==', 'n', { desc = "현재 줄을 위로 이동" })

-- 비주얼 모드 (선택한 여러 줄도 가능)
mapKey('<A-Down>', ":m '>+1<CR>gv=gv", 'v', { desc = "선택한 줄을 아래로 이동" })
mapKey('<A-Up>', ":m '<-2<CR>gv=gv", 'v', { desc = "선택한 줄을 위로 이동" })


-- 멀티 커서 (플러그인 설정이라 desc 추가 불가, 주석으로 설명 대체)
vim.g.VM_maps = {
  ['Find Under'] = '<C-n>',         -- 단어 선택 (VSCode Ctrl+d 유사)
  ['Find Subword Under'] = '<C-n>', -- 부분 단어 선택
}

-- 창 이동 (Ctrl + h/j/k/l)
mapKey('<C-h>', function() require('smart-splits').move_cursor_left() end, 'n', { desc = "왼쪽 창으로 이동" })
mapKey('<C-j>', function() require('smart-splits').move_cursor_down() end, 'n', { desc = "아래 창으로 이동" })
mapKey('<C-k>', function() require('smart-splits').move_cursor_up() end, 'n', { desc = "위 창으로 이동" })
mapKey('<C-l>', function() require('smart-splits').move_cursor_right() end, 'n', { desc = "오른쪽 창으로 이동" })

-- 창 크기 조절 (Alt + 방향키)
-- 줄 이동(<A-방향키>)과 분리하여 충돌을 방지했습니다.
mapKey('<A-h>', function() require('smart-splits').resize_left() end, 'n', { desc = "창 크기 조절: 왼쪽" })
mapKey('<A-j>', function() require('smart-splits').resize_down() end, 'n', { desc = "창 크기 조절: 아래" })
mapKey('<A-k>', function() require('smart-splits').resize_up() end, 'n', { desc = "창 크기 조절: 위" })
mapKey('<A-l>', function() require('smart-splits').resize_right() end, 'n', { desc = "창 크기 조절: 오른쪽" })

-- 입력 모드에서 Ctrl+z로 되돌리기
vim.keymap.set('i', '<C-z>', '<C-o>u', { desc = 'Undo in Insert Mode' })

-- Insert 모드에서 Alt+s를 누르면 현재 단어를 선택하고 'Select Mode'로 진입
-- (선택된 상태에서 타이핑하면 바로 교체됨, 백스페이스 누르면 지워짐)
vim.keymap.set('i', '<A-s>', '<Esc>viw<C-g>', { desc = 'Select current word (IDE Style)' })

-- Shift + 화살표로 텍스트 선택 (Select Mode)
vim.keymap.set('i', '<S-Right>', '<C-o>v<Right><C-g>', { desc = 'Select Right' })
vim.keymap.set('i', '<S-Left>', '<C-o>v<Left><C-g>', { desc = 'Select Left' })
-- 이미 선택된 상태(Select Mode)에서 범위 늘리기
vim.keymap.set('s', '<S-Right>', '<Right>', { desc = 'Extend Selection Right' })
vim.keymap.set('s', '<S-Left>', '<Left>', { desc = 'Extend Selection Left' })


-- 인서트 모드에서 Ctrl+d를 누르면 뒷 단어 삭제 (Delete Word)
vim.keymap.set("i", "<C-d>", "<Del>", { desc = "Delete Next Character" })
-- Insert 모드에서 Alt+v를 누르면 바로 Visual Mode로 전환
vim.keymap.set('i', '<C-v>', '<Esc>v', { desc = 'Enter Visual Mode from Insert' })
-- Insert 모드에서 Shift+화살표를 누르면 바로 Visual Mode로 진입하며 선택 시작
vim.keymap.set('i', '<S-Right>', '<Esc>v<Right>', { desc = 'Start Visual Mode & Move Right' })
vim.keymap.set('i', '<S-Left>', '<Esc>v<Left>', { desc = 'Start Visual Mode & Move Left' })
vim.keymap.set('i', '<S-Down>', '<Esc>v<Down>', { desc = 'Start Visual Mode & Move Down' })
vim.keymap.set('i', '<S-Up>', '<Esc>v<Up>', { desc = 'Start Visual Mode & Move Up' })

-- Insert 모드에서 줄 맨 앞으로 이동 (Ctrl + a)
-- <Esc>I 와 동일: Normal 모드로 나가서 대문자 I (맨 앞 삽입)를 누르는 효과
vim.keymap.set('i', '<C-a>', '<Esc>I', { desc = 'Go to beginning of line' })

-- Insert 모드에서 줄 맨 뒤로 이동 (Ctrl + e)
-- <Esc>A 와 동일: Normal 모드로 나가서 대문자 A (맨 뒤 삽입)를 누르는 효과
vim.keymap.set('i', '<C-e>', '<Esc>A', { desc = 'Go to end of line' })

-- [현재 버퍼 경로에 새 파일 생성]
-- <leader>nf를 누르면 커맨드 라인에 ':e /현재/파일/경로/' 가 입력된 상태가 됩니다.
mapKey('<leader>nf', function()
  local current_dir = vim.fn.expand("%:p:h")
  vim.api.nvim_feedkeys(":e " .. current_dir .. "/", "n", false)
end, 'n', { desc = "현재 경로에 새 파일 생성" })

mapKey('<leader>fn', function()
  local current_dir = vim.fn.expand("%:p:h")
  vim.api.nvim_feedkeys(":e " .. current_dir .. "/", "n", false)
end, 'n', { desc = "현재 경로에 새 파일 생성" })

-- 수정된 일반 파일 버퍼만 자동 저장 (공통 조건)
local function autosave_if_modified()
  if vim.bo.modified and vim.bo.buftype == "" then
    vim.cmd("silent! write")
  end
end

-- Insert 모드에서 Esc로 나올 때
vim.api.nvim_create_autocmd("InsertLeave", { callback = autosave_if_modified })

-- 다른 버퍼로 이동할 때 (dd 후 버퍼 전환하면 저장)
vim.api.nvim_create_autocmd("BufLeave", { callback = autosave_if_modified })

-- 가만히 있을 때 (기본 4초, updatetime에 따름) — dd 후 잠깐 멈추면 저장
vim.api.nvim_create_autocmd({ "CursorHold", "CursorHoldI" }, {
  callback = autosave_if_modified,
})
