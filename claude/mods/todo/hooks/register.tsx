import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { PendingDelete, SyncStatus, Tab, TodoItem, TodoSnapshot } from '../types'
import { addItem, appendBlock, moveItem, parseTodos, removeItem, serializeTodos } from './todos'
import type { ParsedTodos, RichTextSegment, Section } from './todos'

// ---- Notion API ----
// Daily Todo DB (Personal HOME > Daily Todo DB) 의 data source.
const DATA_SOURCE_ID = '2bf64745-3170-80b4-8b72-000bc5fa2ddd'
const TODO_PROPERTY = "Todo's"
const NOTION_VERSION = '2025-09-03'
const API = 'https://api.notion.com/v1'

// 토큰은 notion-personal MCP 와 같은 Keychain 항목을 쓴다 (~/.claude/scripts/mcp-notion-personal.sh).
// $.state 는 세션 상태로 남으므로 토큰은 모듈 변수에만 둔다. 리로드되면 다시 읽는다.
let cachedToken: string | null = null

async function token($: EngineInterface): Promise<string> {
  if (cachedToken) return cachedToken
  const { exitCode, stdout, stderr } = await $.process.run([
    'security',
    'find-generic-password',
    '-a',
    'claude-mcp',
    '-s',
    'notion-personal-token',
    '-w',
  ])
  if (exitCode !== 0) throw new Error(`Keychain에서 notion-personal-token 을 못 읽었습니다: ${stderr.trim()}`)
  cachedToken = stdout.trim()
  return cachedToken
}

async function call($: EngineInterface, method: string, path: string, body?: unknown): Promise<any> {
  const response = await $.http.fetch(`${API}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${await token($)}`,
      'Notion-Version': NOTION_VERSION,
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const json = response.text ? JSON.parse(response.text) : {}
  if (!response.ok) {
    if (response.status === 401) cachedToken = null
    throw new Error(`Notion ${method} ${path} → ${response.status}: ${json.message ?? response.text}`)
  }
  return json
}

type TodayPage = { pageId: string; title: string; url: string; todoPropertyId: string }

async function findTodayPage($: EngineInterface, date: string, group: string): Promise<TodayPage | null> {
  return findPage($, date, { and: [{ property: 'Due Date', date: { equals: date } }, { property: 'Group', select: { equals: group } }] })
}

// 오늘보다 앞선 가장 최근 일지. 달력상 어제가 아니다: 주말·휴가에는 행이 없어서
// 월요일에 "어제"를 열면 금요일 일지가 나와야 한다.
async function findPreviousPage($: EngineInterface, today: string, group: string): Promise<TodayPage | null> {
  return findPage(
    $,
    today,
    { and: [{ property: 'Due Date', date: { before: today } }, { property: 'Group', select: { equals: group } }] },
    [{ property: 'Due Date', direction: 'descending' }],
  )
}

async function findPage($: EngineInterface, fallbackTitle: string, filter: unknown, sorts?: unknown): Promise<TodayPage | null> {
  const result = await call($, 'POST', `/data_sources/${DATA_SOURCE_ID}/query`, { page_size: 1, filter, ...(sorts ? { sorts } : {}) })
  const page = result.results?.[0]
  if (!page) return null
  const date = page.properties['Due Date']?.date?.start ?? fallbackTitle

  const titleProperty = Object.values<any>(page.properties).find(p => p.type === 'title')
  return {
    pageId: page.id,
    title: (titleProperty?.title ?? []).map((t: any) => t.plain_text).join('') || date,
    url: page.url,
    todoPropertyId: page.properties[TODO_PROPERTY].id,
  }
}

// 페이지 조회는 rich_text 를 25개 요소에서 자르므로, 속성 전용 엔드포인트로 끝까지 읽는다.
async function readTodoText($: EngineInterface, page: TodayPage): Promise<string> {
  let text = ''
  let cursor: string | undefined
  do {
    const query = cursor ? `?start_cursor=${encodeURIComponent(cursor)}` : ''
    const result = await call($, 'GET', `/pages/${page.pageId}/properties/${encodeURIComponent(page.todoPropertyId)}${query}`)
    for (const item of result.results ?? []) text += item.rich_text?.plain_text ?? ''
    cursor = result.has_more ? result.next_cursor : undefined
  } while (cursor)
  return text
}

async function writeTodoText($: EngineInterface, pageId: string, richText: RichTextSegment[]): Promise<void> {
  await call($, 'PATCH', `/pages/${pageId}`, { properties: { [TODO_PROPERTY]: { rich_text: richText } } })
}

// ---- 사이드바 ----
const PANE = 'todo'
const PANE_TITLE = '오늘 할 일'
const PANE_COLUMNS = 44
// 업무 일지 행만 대상으로 한다 (Group=My 는 개인 일지).
const GROUP = 'Working'
// Notion 에서 직접 고친 내용을 따라잡는 주기.
const REFRESH_MS = 5 * 60 * 1000
const KST_OFFSET_MS = 9 * 60 * 60 * 1000
// 접은 상태는 세션을 넘어 기억한다: 접어 둔 채 새 세션을 열면 사이드바가 다시 튀어나오지 않게.
const COLLAPSED_STORE_KEY = 'isCollapsed'

// 포커스를 옮길 때 이름으로 찾는 요소들.
const CONFIRM_DELETE_KEY = 'confirm-delete'
const QUICK_INPUT_KEY = 'quick-input'

const snapshot = atom({ plugin: 'todo', key: 'snapshot' } as const, null)
const status = atom({ plugin: 'todo', key: 'status' } as const, { isBusy: false, error: null })
const pendingDelete = atom({ plugin: 'todo', key: 'pendingDelete' } as const, null)
// 빠른 입력 줄의 글. 상태로 들고 있어야 추가가 끝난 뒤 비워 다시 그릴 수 있다.
const draft = atom({ plugin: 'todo', key: 'draft' } as const, '')
// 보고 있는 탭과, 지난 일지(읽기 전용). 지난 일지는 탭을 열 때와 ↻ 에서만 읽는다.
const tab = atom({ plugin: 'todo', key: 'tab' } as const, 'today')
const previous = atom({ plugin: 'todo', key: 'previous' } as const, null)

async function todayInKst($: EngineInterface): Promise<string> {
  return new Date((await $.clock.now()) + KST_OFFSET_MS).toISOString().slice(0, 10)
}

// 체크를 연달아 눌러도 Notion 쓰기가 겹치지 않도록 한 줄로 세운다.
// 겹치면 두 쓰기가 같은 옛 본문에서 출발해 앞의 체크가 사라진다.
let queue: Promise<void> = Promise.resolve()

function serialized($: EngineInterface, work: () => Promise<void>): Promise<void> {
  queue = queue.then(async () => {
    await update($, status, s => ({ ...s, isBusy: true }))
    try {
      await work()
      await update($, status, () => ({ isBusy: false, error: null }))
    } catch (error) {
      await update($, status, () => ({ isBusy: false, error: String((error as Error)?.message ?? error) }))
    }
  })
  return queue
}

async function loadToday($: EngineInterface): Promise<{ page: TodayPage; todos: ParsedTodos } | null> {
  const date = await todayInKst($)
  const page = await findTodayPage($, date, GROUP)
  if (!page) return null
  return { page, todos: parseTodos(await readTodoText($, page)) }
}

async function publish($: EngineInterface, page: TodayPage, todos: ParsedTodos): Promise<void> {
  const next: TodoSnapshot = {
    pageId: page.pageId,
    title: page.title,
    url: page.url,
    open: todos.open,
    done: todos.done,
    syncedAt: await $.clock.now(),
  }
  await update($, snapshot, () => next)
  await showCollapsedSummary($)
}

async function isCollapsed($: EngineInterface): Promise<boolean> {
  return (await $.store.get(COLLAPSED_STORE_KEY)) === true
}

// 접혀 있는 동안에는 상태줄에 남은 개수만 보여 할 일을 잊지 않게 한다.
async function showCollapsedSummary($: EngineInterface): Promise<void> {
  if (!(await isCollapsed($))) {
    $.ui.status(undefined)
    return
  }
  const current = await read($, snapshot)
  $.ui.status(current ? `todo ☐ ${current.open.length} · ☑ ${current.done.length}  (/todo 펼치기)` : 'todo (/todo 펼치기)')
}

// 지난 일지는 고치지 않으므로 오늘 쓰기 줄(serialized)에 세우지 않는다.
async function loadPrevious($: EngineInterface): Promise<void> {
  try {
    const page = await findPreviousPage($, await todayInKst($), GROUP)
    if (!page) {
      await update($, previous, () => null)
      return
    }
    const todos = parseTodos(await readTodoText($, page))
    const next: TodoSnapshot = { pageId: page.pageId, title: page.title, url: page.url, open: todos.open, done: todos.done, syncedAt: await $.clock.now() }
    await update($, previous, () => next)
  } catch (error) {
    await update($, status, s => ({ ...s, error: String((error as Error)?.message ?? error) }))
  }
}

async function showTab($: EngineInterface, next: Tab): Promise<void> {
  await update($, tab, () => next)
  if (next === 'previous') await loadPrevious($)
}

function refresh($: EngineInterface): Promise<void> {
  return serialized($, async () => {
    const today = await loadToday($)
    if (!today) {
      await update($, snapshot, () => null)
      throw new Error(`오늘(${await todayInKst($)}) ${GROUP} 업무 일지 행이 Daily Todo DB에 없습니다`)
    }
    await publish($, today.page, today.todos)
  })
}

// 항상 Notion 최신 본문을 다시 읽고 그 위에 변경을 적용한다: 화면을 그린 뒤
// Notion 에서 손으로 고친 내용을 덮어쓰지 않기 위해서다.
// 쓰기에 성공했을 때만 true 로 끝나, 호출자가 입력란 비우기 같은 뒷정리를 결정한다.
async function mutate(
  $: EngineInterface,
  change: (todos: ParsedTodos) => ParsedTodos | null,
  missing: string,
): Promise<boolean> {
  let isWritten = false
  await serialized($, async () => {
    const today = await loadToday($)
    if (!today) throw new Error('오늘 업무 일지 행을 찾지 못했습니다')
    const changed = change(today.todos)
    if (!changed) {
      await publish($, today.page, today.todos)
      throw new Error(missing)
    }
    await writeTodoText($, today.page.pageId, serializeTodos(changed))
    await publish($, today.page, changed)
    isWritten = true
  })
  return isWritten
}

function rowId(section: Section, item: TodoItem): string {
  return `${section}:${item.text}`
}

async function toggle($: EngineInterface, item: TodoItem, toDone: boolean): Promise<void> {
  await update($, pendingDelete, () => null)
  await mutate($, todos => moveItem(todos, item, toDone), `"${item.text}" 항목이 Notion에서 바뀌어 다시 불러왔습니다`)
}

// ✕ 는 바로 지우지 않고 확인 줄을 연다: 체크(행 클릭)와 삭제가 한 줄에 붙어 있어
// 잘못 누르기 쉽고, Notion 본문에서 지운 항목은 이 사이드바로 되돌릴 수 없다.
async function askDelete($: EngineInterface, id: string): Promise<void> {
  await update($, pendingDelete, () => id)
  // 키보드로 ✕ 를 눌렀다면 Enter 한 번 더로 확정하게 확인 버튼으로 옮긴다. 마우스면 거절돼도 무방하다.
  await $.ui.focus({ requestId: PANE, key: CONFIRM_DELETE_KEY })
}

async function cancelDelete($: EngineInterface): Promise<void> {
  await update($, pendingDelete, () => null)
}

async function remove($: EngineInterface, item: TodoItem, section: Section): Promise<void> {
  await update($, pendingDelete, () => null)
  await mutate($, todos => removeItem(todos, item, section), `"${item.text}" 항목이 Notion에서 바뀌어 다시 불러왔습니다`)
}

// /todo 로 펼칠 때는 패널 포커스를 요청해 새 할 일 입력란(autoFocus)이 키보드를 받게 한다
// ($.ui.focus 로 Client 편집기에 키보드를 넘기는 길은 2026-10-14 실측에서 거절됐다). 세션 시작 때는
// 요청하지 않는다: 키보드를 가져가면 프롬프트에 바로 칠 수 없다.
async function expand($: EngineInterface, isFocusWanted = false): Promise<void> {
  await $.store.set(COLLAPSED_STORE_KEY, false)
  await showCollapsedSummary($)
  await $.ui.open({ id: PANE, title: PANE_TITLE, columns: PANE_COLUMNS, ...(isFocusWanted ? { focus: true as const } : {}) })
}

// 빠른 입력 박스의 Enter. 여러 줄이면 `-` 줄을 바로 위 상위 항목의 하위로 붙인다.
// 실패하면 입력한 글을 남겨 고쳐서 다시 보낼 수 있게 한다.
async function quickAdd($: EngineInterface, block: string): Promise<void> {
  if (block.trim() === '') return
  const isAdded = await mutate($, todos => appendBlock(todos, block), '비었거나 이미 목록에 있는 항목이 있어 추가하지 않았습니다')
  if (isAdded) await update($, draft, () => '')
}

// 기억은 ui.close 훅이 맡는다: 접기 버튼과 ctrl+x x 같은 엔진 닫기 키가 같은 길로 기록된다.
function collapse($: EngineInterface): Promise<void> {
  return $.ui.close({ id: PANE })
}

async function isPaneUp($: EngineInterface): Promise<boolean> {
  return (await $.ui.panes()).some(pane => pane.id === PANE)
}

function clock(ms: number): string {
  return new Date(ms + KST_OFFSET_MS).toISOString().slice(11, 16)
}

const ADD_SUBCOMMAND = /^(?:add|추가)\s+([\s\S]+)$/

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'todo',
      description: 'Notion 오늘 할 일 사이드바를 접고 펼친다. `/todo add <할 일>` 로 바로 추가 (Daily Todo DB 동기화)',
      argumentHint: '[add <할 일>]',
    })
    if (!(await isCollapsed($))) void expand($)
    void refresh($)
    $.clock.every(REFRESH_MS, () => void refresh($))
    return next(e)
  })

  on('command.run', { command: 'todo' }, async ($, e) => {
    // 사이드바에 포커스를 옮기지 않고 프롬프트에서 바로 적는 길.
    const addMatch = ADD_SUBCOMMAND.exec(e.args.trim())
    if (addMatch?.[1]) {
      const text = addMatch[1].trim()
      const isAdded = await mutate($, todos => addItem(todos, text), `"${text}" 은(는) 이미 목록에 있습니다`)
      const sync = (await read($, status)) as SyncStatus
      return { text: isAdded ? `할 일을 추가했습니다: ${text}` : `추가하지 못했습니다: ${sync.error ?? '알 수 없는 오류'}` }
    }

    if (await isPaneUp($)) {
      await collapse($)
      return { text: '오늘 할 일 사이드바를 접었습니다.' }
    }
    await expand($, true)
    void refresh($)
    return { text: '오늘 할 일 사이드바를 펼치고 Notion에서 다시 불러옵니다.' }
  })

  on('ui.close', { id: PANE }, async ($, e, next) => {
    const closed = await next(e)
    // 플러그인 리로드(unload)로 닫힌 것은 사람이 접은 게 아니다.
    if (e.origin.kind !== 'unload') {
      await $.store.set(COLLAPSED_STORE_KEY, true)
      await showCollapsedSummary($)
    }
    return closed
  })
    // 접힘 기억에 실패해도 닫기 자체는 막지 않는다.
    .catch(($, e, next) => next(e))

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const elements = $.ui.resolve(e)
    const { Box, Text, Button, Markdown } = elements
    // mobile 표면에는 Input 이 없어 새 할 일 입력 박스를 그리지 않는다.
    const Input = 'Input' in elements ? elements.Input : null
    const typed = (await read($, draft)) as string
    const current = await read($, snapshot)
    const sync = (await read($, status)) as SyncStatus
    const pending = (await read($, pendingDelete)) as PendingDelete
    const activeTab = (await read($, tab)) as Tab
    const past = (await read($, previous)) as TodoSnapshot | null

    const subs = (item: TodoItem, isDone: boolean) =>
      item.subs.map(sub => (
        <Box paddingLeft={4}>
          <Text dimColor>
            ◦ <Text strikethrough={isDone}>{sub}</Text>
          </Text>
        </Box>
      ))

    // 행 = [체크 토글(행 대부분)] [✕]. 해야 할 일과 완료가 같은 모양을 쓰고 체크 방향만 다르다.
    // 행 Box 에 key 를 줘 마우스를 올리면 ✕ 가 빨갛게 켜진다.
    const itemRow = (item: TodoItem, section: Section) => {
      const id = rowId(section, item)
      const isDone = section === 'done'
      return (
        <Box flexDirection="column">
          <Box key={`row:${id}`} flexDirection="row">
            <Box flexGrow={1} flexShrink={1}>
              <Button key={`toggle:${id}`} plain dimColor={isDone} onPress={() => void toggle($, item, !isDone)}>
                {isDone ? '☑ ' : '☐ '}
                <Text strikethrough={isDone}>{item.text}</Text>
              </Button>
            </Box>
            <Text> </Text>
            <Button
              key={`delete:${id}`}
              label="✕"
              plain
              dimColor
              hover={{ color: 'error', dimColor: false }}
              onPress={() => void askDelete($, id)}
            />
          </Box>
          {pending === id && (
            <Box paddingLeft={2} flexDirection="row">
              <Text color="error">이 항목을 삭제할까요? </Text>
              <Button key={CONFIRM_DELETE_KEY} label="삭제" hotkey="y" plain onPress={() => void remove($, item, section)} />
              <Text>  </Text>
              <Button key="cancel-delete" label="취소" hotkey="n" plain dimColor onPress={() => void cancelDelete($)} />
            </Box>
          )}
          {subs(item, isDone)}
        </Box>
      )
    }

    // 탭 버튼: 보고 있는 탭은 primary 로 켜 둔다.
    const tabButton = (target: Tab, label: string, hotkey: string) =>
      activeTab === target ? (
        <Button key={`tab-${target}`} label={label} hotkey={hotkey} plain variant="primary" onPress={() => void showTab($, target)} />
      ) : (
        <Button key={`tab-${target}`} label={label} hotkey={hotkey} plain dimColor onPress={() => void showTab($, target)} />
      )

    // 지난 일지는 읽기 전용이라 체크·삭제 버튼 없이 글로만 그린다.
    const readOnlyItem = (item: TodoItem, isDone: boolean) => (
      <Box flexDirection="column">
        <Text dimColor={isDone}>
          {isDone ? '☑ ' : '• '}
          <Text strikethrough={isDone}>{item.text}</Text>
        </Text>
        {subs(item, isDone)}
      </Box>
    )

    const shown = activeTab === 'today' ? current : past

    return (
      <Box flexDirection="column">
        <Box flexDirection="row" justifyContent="space-between">
          <Box flexDirection="row">
            {tabButton('today', '오늘', '1')}
            <Text>  </Text>
            {tabButton('previous', '어제', '2')}
          </Box>
          <Box flexDirection="row">
            <Button
              key="refresh"
              label="↻"
              hotkey="r"
              plain
              dimColor
              onPress={() => void (activeTab === 'previous' ? loadPrevious($) : refresh($))}
            />
            <Text> </Text>
            <Button key="collapse" label="접기" hotkey="h" plain dimColor onPress={() => void collapse($)} />
          </Box>
        </Box>
        <Markdown text={shown ? `**[${shown.title}](${shown.url})**` : activeTab === 'today' ? '**오늘 할 일**' : '**지난 일지**'} />

        {activeTab === 'previous' && (
          <Box flexDirection="column" marginTop={1}>
            {!past && <Text dimColor>불러오는 중이거나, 오늘보다 앞선 업무 일지가 없습니다</Text>}
            {past && past.open.length === 0 && past.done.length === 0 && <Text dimColor>적힌 할 일이 없습니다</Text>}
            {past?.open.map(item => readOnlyItem(item, false))}
            {past && past.done.length > 0 && (
              <Box flexDirection="column" marginTop={1}>
                <Text bold dimColor>
                  완료 {past.done.length}
                </Text>
                {past.done.map(item => readOnlyItem(item, true))}
              </Box>
            )}
          </Box>
        )}

        {activeTab === 'today' && current && (
          <Box flexDirection="column" marginTop={1}>
            {Input && (
              <Box flexDirection="column">
                <Text bold>새 할 일</Text>
                <Box borderStyle="round" borderColor="suggestion" paddingX={1} flexDirection="row">
                  <Text color="suggestion">› </Text>
                  <Box flexGrow={1} flexShrink={1}>
                    <Input
                      key={QUICK_INPUT_KEY}
                      placeholder="입력 후 Enter ('-'로 시작하면 하위)"
                      submitLabel="추가"
                      value={typed}
                      autoFocus
                      onInput={(value: string) => void update($, draft, () => value)}
                      onSubmit={(value: string) => void quickAdd($, value)}
                    />
                  </Box>
                </Box>
              </Box>
            )}

            <Box flexDirection="column" marginTop={Input ? 1 : 0}>
              <Text bold>
                해야 할 일 <Text color="suggestion">{current.open.length}</Text>
              </Text>
              {current.open.length === 0 ? (
                <Text dimColor>남은 할 일이 없습니다</Text>
              ) : (
                current.open.map(item => itemRow(item, 'open'))
              )}
            </Box>

            {current.done.length > 0 && (
              <Box flexDirection="column" marginTop={1}>
                <Text bold dimColor>
                  완료 {current.done.length}
                </Text>
                {current.done.map(item => itemRow(item, 'done'))}
              </Box>
            )}
          </Box>
        )}

        <Box flexDirection="column" marginTop={1}>
          <Text dimColor>
            {sync.isBusy ? 'Notion 동기화 중…' : shown ? `동기화 ${clock(shown.syncedAt)}` : '불러오는 중…'}
          </Text>
          {sync.error && <Text color="error">{sync.error}</Text>}
          {e.props.isFocused && (
            <Text dimColor>1 오늘 · 2 어제 · Enter 추가 · '-'로 시작하면 하위 · 행 클릭 완료/되돌리기 · ✕ 삭제 · 글 수정은 Notion에서</Text>
          )}
        </Box>
      </Box>
    )
  })
}
