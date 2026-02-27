local keyMapper = function(from, to, mode, opts)
    local options = { noremap = true, silent = true }
    mode = mode or "n" -- 기본 모드는 노멀(n)
    
    if opts then
        options = vim.tbl_extend("force", options, opts)
    end
    
    vim.keymap.set(mode, from, to, options)
end

return { mapKey = keyMapper }
