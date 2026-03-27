local function tpl(file)
  return vim.fn.stdpath("config") .. "/templates/" .. file
end

-- Go: package 이름을 디렉토리명에서 동적으로 추출 (main.go → package main)
vim.api.nvim_create_autocmd("BufNewFile", {
  pattern = "*.go",
  callback = function()
    local filename = vim.fn.expand("%:t")
    local pkg = filename == "main.go" and "main" or vim.fn.expand("%:h:t")
    vim.api.nvim_buf_set_lines(0, 0, -1, false, { "package " .. pkg, "" })
  end,
})

-- Python
vim.api.nvim_create_autocmd("BufNewFile", {
  pattern = "*.py",
  command = "0r " .. tpl("skeleton.py"),
})

-- YAML: Helm templates/*.yaml는 helm skeleton, 그 외는 일반 skeleton
vim.api.nvim_create_autocmd("BufNewFile", {
  pattern = { "*.yaml", "*.yml" },
  callback = function()
    local path = vim.fn.expand("%:p")
    if path:match("/templates/[^/]+%.ya?ml$") then
      vim.cmd("0r " .. tpl("skeleton_helm.yaml"))
    else
      vim.cmd("0r " .. tpl("skeleton.yaml"))
    end
  end,
})

-- JavaScript
vim.api.nvim_create_autocmd("BufNewFile", {
  pattern = { "*.js", "*.jsx" },
  command = "0r " .. tpl("skeleton.js"),
})

-- TypeScript
vim.api.nvim_create_autocmd("BufNewFile", {
  pattern = { "*.ts", "*.tsx" },
  command = "0r " .. tpl("skeleton.ts"),
})
