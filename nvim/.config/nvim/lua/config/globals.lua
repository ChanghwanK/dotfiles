vim.g.mapleader = " " -- 글로벌 리더키를 스페이스바로 설정
vim.g.maplocalleader = " " -- local leader

-- macOS: Homebrew PATH 보장 (launchd 등 shell 없이 실행될 때 PATH 미포함 방지)
vim.env.PATH = "/opt/homebrew/bin:" .. vim.env.PATH

-- Java (openjdk@21) — 설치된 경우에만 PATH/JAVA_HOME 설정
local java_home = "/opt/homebrew/opt/openjdk@21"
if vim.fn.isdirectory(java_home) == 1 then
  vim.env.PATH = java_home .. "/bin:" .. vim.env.PATH
  vim.env.JAVA_HOME = java_home
end
