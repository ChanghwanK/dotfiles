local M = {}

-- 커서 위치의 .Values.xxx.yyy 경로를 추출
local function get_values_path_at_cursor()
    local line = vim.api.nvim_get_current_line()
    local col = vim.api.nvim_win_get_cursor(0)[2] + 1 -- 1-indexed

    local best = nil
    local pos = 1
    while true do
        local s, e, path = line:find("%.Values%.([%w%.%-_]+)", pos)
        if not s then break end
        if col >= s and col <= e then
            return path -- 커서가 정확히 이 위치에 있음
        end
        if not best then best = path end -- fallback: 라인의 첫 번째 .Values 경로
        pos = e + 1
    end
    return best
end

-- Chart.yaml을 찾아 차트 루트 경로 반환
local function find_chart_root()
    local current_file = vim.api.nvim_buf_get_name(0)
    local dir = vim.fn.fnamemodify(current_file, ":h")
    for _ = 1, 10 do
        if vim.fn.filereadable(dir .. "/Chart.yaml") == 1 then
            return dir
        end
        local parent = vim.fn.fnamemodify(dir, ":h")
        if parent == dir then break end
        dir = parent
    end
    return nil
end

-- 스택 기반으로 중첩 YAML 키 경로의 라인 번호를 탐색
local function find_yaml_line(lines, keys)
    local stack = {} -- { indent, key }

    for i, line in ipairs(lines) do
        -- 빈 줄, 주석 건너뜀
        if line:match("^%s*#") or line:match("^%s*$") then goto continue end

        local indent = #(line:match("^(%s*)") or "")
        local key = line:match("^%s*([%w%-_]+)%s*:")
        if not key then goto continue end

        -- 현재 indent 이상의 스택 항목 제거 (스코프 이탈)
        while #stack > 0 and stack[#stack].indent >= indent do
            table.remove(stack)
        end

        -- 현재 깊이에서 찾고 있는 키와 일치하는지 확인
        local depth = #stack + 1
        if depth <= #keys and key == keys[depth] then
            table.insert(stack, { indent = indent, key = key })
            if #stack == #keys then return i end -- 모든 키를 찾음
        end

        ::continue::
    end
    return nil
end

-- values.yaml에서 커서 위치 키의 전체 YAML 경로를 역추적
local function get_yaml_key_path_at_cursor()
    local cursor_row = vim.api.nvim_win_get_cursor(0)[1] -- 1-indexed
    local all_lines = vim.api.nvim_buf_get_lines(0, 0, cursor_row, false)

    local current_line = all_lines[cursor_row]
    local current_key = current_line:match("^%s*([%w%-_]+)%s*:")
    if not current_key then return nil end

    local target_indent = #(current_line:match("^(%s*)") or "")
    local path = { current_key }

    -- 위로 올라가며 부모 키 탐색
    for i = cursor_row - 1, 1, -1 do
        local line = all_lines[i]
        if line:match("^%s*#") or line:match("^%s*$") then goto continue end

        local indent = #(line:match("^(%s*)") or "")
        local key = line:match("^%s*([%w%-_]+)%s*:")

        if key and indent < target_indent then
            table.insert(path, 1, key)
            target_indent = indent
            if target_indent == 0 then break end
        end

        ::continue::
    end

    return table.concat(path, ".")
end

-- values.yaml에서 gr: 해당 키를 참조하는 템플릿 파일 검색 (성공 시 true 반환)
function M.find_value_references()
    local yaml_path = get_yaml_key_path_at_cursor()
    if not yaml_path then return false end

    local chart_root = find_chart_root()
    if not chart_root then
        vim.notify("helm: Chart.yaml을 찾을 수 없습니다", vim.log.levels.WARN)
        return true
    end

    local search_term = ".Values." .. yaml_path

    local ok, telescope = pcall(require, "telescope.builtin")
    if ok then
        telescope.grep_string({
            search = search_term,
            cwd = chart_root,
            prompt_title = "Helm References: " .. search_term,
        })
    else
        -- fallback: vimgrep
        vim.cmd("vimgrep /" .. vim.fn.escape(search_term, "/") .. "/ " .. chart_root .. "/templates/**/*")
        vim.cmd("copen")
    end
    return true
end

-- values.yaml에서 .Values 경로로 이동 (성공 시 true 반환)
function M.try_goto_helm_value()
    local value_path = get_values_path_at_cursor()
    if not value_path then return false end

    local chart_root = find_chart_root()
    if not chart_root then
        vim.notify("helm: Chart.yaml을 찾을 수 없습니다", vim.log.levels.WARN)
        return true
    end

    local values_file = chart_root .. "/values.yaml"
    if vim.fn.filereadable(values_file) == 0 then
        vim.notify("helm: values.yaml을 찾을 수 없습니다: " .. values_file, vim.log.levels.WARN)
        return true
    end

    local keys = vim.split(value_path, ".", { plain = true })
    local file_lines = vim.fn.readfile(values_file)
    local target = find_yaml_line(file_lines, keys)

    vim.cmd("edit " .. vim.fn.fnameescape(values_file))

    if target then
        vim.api.nvim_win_set_cursor(0, { target, 0 })
        vim.cmd("normal! zz")
        vim.notify(".Values." .. value_path, vim.log.levels.INFO)
    else
        -- fallback: 마지막 키를 검색
        local last_key = keys[#keys]
        vim.fn.search(last_key .. ":")
        vim.cmd("normal! zz")
        vim.notify("정확한 경로를 찾지 못해 키로 검색: " .. last_key, vim.log.levels.WARN)
    end
    return true
end

return M
