vim.g.mapleader = " " -- 글로벌 리더키를 스페이스바로 설정
vim.g.maplocalleader = " " -- local leader

-- macOS: Homebrew PATH 보장 (launchd 등 shell 없이 실행될 때 PATH 미포함 방지)
vim.env.PATH = "/opt/homebrew/bin:/opt/homebrew/opt/openjdk@21/bin:" .. vim.env.PATH
vim.env.JAVA_HOME = "/opt/homebrew/opt/openjdk@21"
