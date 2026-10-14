import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Mode, Question, QuestionBox, Tab } from '../types'
import { append, appendChild, editText, hasChildren, indent, move, outdent, remove, toggleAnswered, toMarkdown } from './outline'
import type { Change } from './outline'

const PANE = 'question-box'
const PANE_TITLE = '질문 상자'
const PANE_COLUMNS = 44
const COMMAND = 'qbox'
const KST_OFFSET_MS = 9 * 60 * 60 * 1000
const BULLETS = ['•', '◦', '▪', '‣', '·', '·']
// 지난 세션 탭은 최근 것만 보인다. 전체 기록은 아카이브 폴더의 마크다운 파일에 있다.
const ARCHIVE_LIMIT = 30
// 접은 상태는 세션을 넘어 기억한다: 접어 둔 채 새 세션을 열면 사이드바가 다시 튀어나오지 않게.
const COLLAPSED_STORE_KEY = 'isCollapsed'
const BOX_KEY_PREFIX = 'box:'

const NEW_INPUT_KEY = 'new-question'
const EDIT_INPUT_KEY = 'edit-question'
const CHILD_INPUT_KEY = 'child-question'
const CONFIRM_DELETE_KEY = 'confirm-delete'

const items = atom({ plugin: 'question-box', key: 'items' } as const, [])
const selected = atom({ plugin: 'question-box', key: 'selected' } as const, null)
const mode = atom({ plugin: 'question-box', key: 'mode' } as const, { kind: 'none' })
// 입력란의 글은 상태로 들고 있어야 추가가 끝난 뒤 비워 다시 그릴 수 있다.
const draft = atom({ plugin: 'question-box', key: 'draft' } as const, '')
const editDraft = atom({ plugin: 'question-box', key: 'editDraft' } as const, '')
const tab = atom({ plugin: 'question-box', key: 'tab' } as const, 'session')
const archive = atom({ plugin: 'question-box', key: 'archive' } as const, [])
const openArchive = atom({ plugin: 'question-box', key: 'openArchive' } as const, null)
const error = atom({ plugin: 'question-box', key: 'error' } as const, null)

// ---- 세션 상자의 정체와 저장 ----

type BoxMeta = { sessionId: string; cwd: string; createdAt: number; archivePath: string }

// 모듈 변수라 리로드되면 비고, 다음 저장 때 store 에서 createdAt 을 되읽어 같은 파일 이름을 다시 만든다.
let meta: BoxMeta | null = null
let idCounter = 0

function kstStamp(ms: number): string {
  return new Date(ms + KST_OFFSET_MS).toISOString().slice(0, 16).replace('T', ' ')
}

function basename(path: string): string {
  return path.replace(/\/+$/, '').split('/').pop() || path
}

async function boxMeta($: EngineInterface): Promise<BoxMeta> {
  const sessionId = await $.session.id()
  if (meta && meta.sessionId === sessionId) return meta
  const stored = (await $.store.get(BOX_KEY_PREFIX + sessionId)) as QuestionBox | undefined
  const cwd = stored?.cwd ?? (await $.session.cwd())
  const createdAt = stored?.createdAt ?? (await $.clock.now())
  const home = (await $.env.get('HOME')) ?? '~'
  const day = kstStamp(createdAt).slice(0, 10)
  const archivePath = `${home}/.claude/question-box/${day}_${basename(cwd)}_${sessionId.slice(0, 8)}.md`
  meta = { sessionId, cwd, createdAt, archivePath }
  return meta
}

function makeId(): string {
  idCounter += 1
  return `${Date.now().toString(36)}-${idCounter.toString(36)}-${Math.random().toString(36).slice(2, 6)}`
}

// 바뀔 때마다 두 곳에 남긴다: store(지난 세션 탭이 읽음)와 마크다운 파일(사람이 에디터로 읽음).
// 빈 상자는 파일을 만들지 않는다. 다 지웠을 때는 이미 있던 파일만 비운다.
async function persist($: EngineInterface, list: readonly Question[]): Promise<void> {
  try {
    const box = await boxMeta($)
    const now = await $.clock.now()
    const record: QuestionBox = { sessionId: box.sessionId, cwd: box.cwd, createdAt: box.createdAt, updatedAt: now, items: [...list] }
    await $.store.set(BOX_KEY_PREFIX + box.sessionId, record)
    if (list.length > 0 || (await $.fs.exists(box.archivePath))) {
      const heading = `질문 상자 ${kstStamp(box.createdAt)}`
      await $.fs.write(box.archivePath, toMarkdown(list, heading, [`session: ${box.sessionId}`, `cwd: ${box.cwd}`, `updated: ${kstStamp(now)}`]))
    }
    await update($, error, () => null)
  } catch (failure) {
    await update($, error, () => `저장 실패: ${String((failure as Error)?.message ?? failure)}`)
  }
  await showCollapsedSummary($)
}

// 모든 변경이 지나는 길. 할 수 없는 변경(null)이면 이유를 토스트로 알리고 아무것도 바꾸지 않는다.
async function apply($: EngineInterface, change: (list: Question[]) => Change, refusal?: string): Promise<boolean> {
  const current = (await read($, items)) as Question[]
  const next = change(current)
  if (!next) {
    if (refusal) $.ui.toast(refusal)
    return false
  }
  await update($, items, () => next)
  await persist($, next)
  return true
}

// ---- 사용자 동작 ----

async function addTopLevel($: EngineInterface, block: string): Promise<void> {
  if (await apply($, list => append(list, block, makeId))) await update($, draft, () => '')
}

async function select($: EngineInterface, id: string): Promise<void> {
  const current = await read($, selected)
  await update($, mode, () => ({ kind: 'none' }) as Mode)
  await update($, selected, () => (current === id ? null : id))
}

async function startEdit($: EngineInterface, question: Question): Promise<void> {
  await update($, editDraft, () => question.text)
  await update($, mode, () => ({ kind: 'edit', id: question.id }) as Mode)
  await $.ui.focus({ requestId: PANE, key: EDIT_INPUT_KEY })
}

async function saveEdit($: EngineInterface, id: string, text: string): Promise<void> {
  if (await apply($, list => editText(list, id, text), '빈 질문으로는 바꿀 수 없습니다. 지우려면 ✕ 를 누르세요')) {
    await update($, mode, () => ({ kind: 'none' }) as Mode)
  }
}

async function startChild($: EngineInterface, id: string): Promise<void> {
  await update($, editDraft, () => '')
  await update($, mode, () => ({ kind: 'child', id }) as Mode)
  await $.ui.focus({ requestId: PANE, key: CHILD_INPUT_KEY })
}

// 하위 질문을 추가해도 입력란을 닫지 않는다: 하위 질문은 보통 몇 개씩 이어서 적는다.
async function addChild($: EngineInterface, parentId: string, block: string): Promise<void> {
  if (await apply($, list => appendChild(list, parentId, block, makeId), '더 깊이 들여 쓸 수 없습니다')) {
    await update($, editDraft, () => '')
  }
}

async function closeMode($: EngineInterface): Promise<void> {
  await update($, mode, () => ({ kind: 'none' }) as Mode)
}

// ✕ 는 바로 지우지 않고 확인을 묻는다: 하위 질문까지 함께 지워지고 되돌리기가 없다.
async function askDelete($: EngineInterface, id: string): Promise<void> {
  await update($, mode, () => ({ kind: 'confirmDelete', id }) as Mode)
  await $.ui.focus({ requestId: PANE, key: CONFIRM_DELETE_KEY })
}

async function confirmDelete($: EngineInterface, id: string): Promise<void> {
  await apply($, list => remove(list, id))
  await update($, mode, () => ({ kind: 'none' }) as Mode)
  await update($, selected, () => null)
}

// ---- 지난 세션 ----

async function loadArchive($: EngineInterface): Promise<void> {
  const currentId = await $.session.id()
  const keys = (await $.store.keys()).filter(key => key.startsWith(BOX_KEY_PREFIX) && key !== BOX_KEY_PREFIX + currentId)
  const boxes = (await Promise.all(keys.map(key => $.store.get(key)))) as (QuestionBox | undefined)[]
  const recent = boxes
    .filter((box): box is QuestionBox => !!box && box.items.length > 0)
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, ARCHIVE_LIMIT)
  await update($, archive, () => recent)
}

async function showTab($: EngineInterface, next: Tab): Promise<void> {
  await update($, tab, () => next)
  if (next === 'archive') await loadArchive($)
}

async function toggleArchive($: EngineInterface, sessionId: string): Promise<void> {
  await update($, openArchive, current => (current === sessionId ? null : sessionId))
}

// ---- 사이드바 접기/펼치기 ----

async function isCollapsed($: EngineInterface): Promise<boolean> {
  return (await $.store.get(COLLAPSED_STORE_KEY)) === true
}

// 접혀 있는 동안에는 상태줄에 남은 질문 수만 보여 잊지 않게 한다.
async function showCollapsedSummary($: EngineInterface): Promise<void> {
  if (!(await isCollapsed($))) {
    $.ui.status(undefined)
    return
  }
  const list = (await read($, items)) as Question[]
  const open = list.filter(item => !item.isAnswered).length
  $.ui.status(list.length === 0 ? undefined : `질문 ${open}/${list.length}  (/${COMMAND} 펼치기)`)
}

async function expand($: EngineInterface, isFocusWanted = false): Promise<void> {
  await $.store.set(COLLAPSED_STORE_KEY, false)
  await showCollapsedSummary($)
  await $.ui.open({ id: PANE, title: PANE_TITLE, columns: PANE_COLUMNS, ...(isFocusWanted ? { focus: true as const } : {}) })
}

// 기억은 ui.close 훅이 맡는다: 접기 버튼과 엔진의 닫기 키가 같은 길로 기록된다.
function collapse($: EngineInterface): Promise<unknown> {
  return $.ui.close({ id: PANE })
}

async function isPaneUp($: EngineInterface): Promise<boolean> {
  return (await $.ui.panes()).some(pane => pane.id === PANE)
}

const ADD_SUBCOMMAND = /^(?:add|추가)\s+([\s\S]+)$/

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: COMMAND,
      description: '질문 상자 사이드바를 접고 펼친다. `/qbox add <질문>` 으로 프롬프트에서 바로 추가',
      argumentHint: '[add <질문>]',
    })
    // 리로드로 다시 시작할 때는 $.state 에 목록이 남아 있다. 비어 있을 때만 store 에서 되살린다(재개한 세션).
    const list = (await read($, items)) as Question[]
    if (list.length === 0) {
      const stored = (await $.store.get(BOX_KEY_PREFIX + (await $.session.id()))) as QuestionBox | undefined
      if (stored?.items.length) await update($, items, () => stored.items)
    }
    if (!(await isCollapsed($))) void expand($)
    await showCollapsedSummary($)
    return next(e)
  })

  // /clear 는 session.start 없이 새 세션 id 로 이어진다. 앞 세션 상자는 이미 저장돼 있으니 비우고 새로 시작한다.
  on('session.end', async ($, e, next) => {
    const ended = await next(e)
    if (e.reason === 'clear') {
      meta = null
      await update($, items, () => [])
      await update($, selected, () => null)
      await update($, mode, () => ({ kind: 'none' }) as Mode)
    }
    return ended
  })

  on('command.run', { command: COMMAND }, async ($, e) => {
    const addMatch = ADD_SUBCOMMAND.exec(e.args.trim())
    if (addMatch?.[1]) {
      const isAdded = await apply($, list => append(list, addMatch[1]!, makeId))
      return { text: isAdded ? `질문을 추가했습니다: ${addMatch[1].trim()}` : '추가할 질문이 비어 있습니다.' }
    }
    if (await isPaneUp($)) {
      await collapse($)
      return { text: '질문 상자를 접었습니다.' }
    }
    await expand($, true)
    return { text: '질문 상자를 펼쳤습니다.' }
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
    const { Box, Text, Button } = elements
    // mobile 표면에는 Input 이 없어 입력란 없이 목록만 그린다.
    const Input = 'Input' in elements ? elements.Input : null

    const list = (await read($, items)) as Question[]
    const picked = (await read($, selected)) as string | null
    const action = (await read($, mode)) as Mode
    const typed = (await read($, draft)) as string
    const editing = (await read($, editDraft)) as string
    const activeTab = (await read($, tab)) as Tab
    const past = (await read($, archive)) as QuestionBox[]
    const expanded = (await read($, openArchive)) as string | null
    const failure = (await read($, error)) as string | null
    const box = await boxMeta($)

    const bullet = (question: Question) => (question.isAnswered ? '✓' : (BULLETS[question.depth] ?? '·'))

    const questionText = (question: Question) => (
      <Text strikethrough={question.isAnswered} dimColor={question.isAnswered}>
        {question.text}
      </Text>
    )

    // 선택한 행 아래에 펼치는 조작 줄. 단축키는 사이드바가 키보드를 가진 동안만 듣는다.
    const actionBar = (question: Question) => (
      <Box flexDirection="column" paddingLeft={question.depth * 2 + 2}>
        <Box flexDirection="row">
          <Button key="act-edit" label="편집" hotkey="e" plain onPress={() => void startEdit($, question)} />
          <Text>  </Text>
          <Button key="act-child" label="+하위" hotkey="a" plain onPress={() => void startChild($, question.id)} />
          <Text>  </Text>
          <Button
            key="act-answer"
            label={question.isAnswered ? '미해결로' : '해결'}
            hotkey="d"
            plain
            onPress={() => void apply($, l => toggleAnswered(l, question.id))}
          />
          <Text>  </Text>
          <Button key="act-delete" label="✕" hotkey="x" plain dimColor onPress={() => void askDelete($, question.id)} />
        </Box>
        <Box flexDirection="row">
          <Button key="act-outdent" label="←" hotkey="h" plain dimColor onPress={() => void apply($, l => outdent(l, question.id), '이미 맨 바깥입니다')} />
          <Text> </Text>
          <Button key="act-indent" label="→" hotkey="l" plain dimColor onPress={() => void apply($, l => indent(l, question.id), '들어갈 상위 질문이 없거나 너무 깊습니다')} />
          <Text> </Text>
          <Button key="act-up" label="↑" hotkey="k" plain dimColor onPress={() => void apply($, l => move(l, question.id, -1), '위에 같은 단계 질문이 없습니다')} />
          <Text> </Text>
          <Button key="act-down" label="↓" hotkey="j" plain dimColor onPress={() => void apply($, l => move(l, question.id, 1), '아래에 같은 단계 질문이 없습니다')} />
        </Box>
      </Box>
    )

    const row = (question: Question) => {
      const isPicked = picked === question.id
      const isEditing = action.kind === 'edit' && action.id === question.id
      return (
        <Box flexDirection="column">
          <Box key={`row:${question.id}`} flexDirection="row" paddingLeft={question.depth * 2}>
            <Text color={isPicked ? 'suggestion' : undefined} dimColor={!isPicked}>
              {bullet(question)}{' '}
            </Text>
            <Box flexGrow={1} flexShrink={1}>
              {isEditing && Input ? (
                <Input
                  key={EDIT_INPUT_KEY}
                  value={editing}
                  submitLabel="저장"
                  onInput={(value: string) => void update($, editDraft, () => value)}
                  onSubmit={(value: string) => void saveEdit($, question.id, value)}
                />
              ) : (
                <Button key={`select:${question.id}`} plain onPress={() => void select($, question.id)}>
                  {isPicked ? <Text color="suggestion">{question.text}</Text> : questionText(question)}
                </Button>
              )}
            </Box>
          </Box>
          {isEditing && (
            <Box paddingLeft={question.depth * 2 + 2}>
              <Button key="cancel-edit" label="취소" plain dimColor onPress={() => void closeMode($)} />
            </Box>
          )}
          {isPicked && !isEditing && actionBar(question)}
          {action.kind === 'confirmDelete' && action.id === question.id && (
            <Box paddingLeft={question.depth * 2 + 2} flexDirection="row">
              <Text color="error">{hasChildren(list, question.id) ? '하위 질문까지 지울까요? ' : '이 질문을 지울까요? '}</Text>
              <Button key={CONFIRM_DELETE_KEY} label="삭제" hotkey="y" plain onPress={() => void confirmDelete($, question.id)} />
              <Text>  </Text>
              <Button key="cancel-delete" label="취소" hotkey="n" plain dimColor onPress={() => void closeMode($)} />
            </Box>
          )}
        </Box>
      )
    }

    // 하위 질문 입력란은 부모의 하위 목록 끝(새 질문이 들어갈 자리)에 그린다.
    const childInputAfter = (index: number) => {
      if (action.kind !== 'child' || !Input) return null
      const parentIndex = list.findIndex(item => item.id === action.id)
      if (parentIndex < 0) return null
      const parentDepth = list[parentIndex]!.depth
      let end = parentIndex + 1
      while (end < list.length && list[end]!.depth > parentDepth) end++
      if (index !== end - 1) return null
      return (
        <Box flexDirection="column" paddingLeft={(parentDepth + 1) * 2}>
          <Box borderStyle="round" borderColor="suggestion" paddingX={1} flexDirection="row">
            <Text color="suggestion">{BULLETS[parentDepth + 1] ?? '·'} </Text>
            <Box flexGrow={1} flexShrink={1}>
              <Input
                key={CHILD_INPUT_KEY}
                placeholder="하위 질문 입력 후 Enter"
                submitLabel="추가"
                value={editing}
                onInput={(value: string) => void update($, editDraft, () => value)}
                onSubmit={(value: string) => void addChild($, action.id, value)}
              />
            </Box>
          </Box>
          <Button key="close-child" label="닫기" plain dimColor onPress={() => void closeMode($)} />
        </Box>
      )
    }

    const tabButton = (target: Tab, label: string, hotkey: string) =>
      activeTab === target ? (
        <Button key={`tab-${target}`} label={label} hotkey={hotkey} plain variant="primary" onPress={() => void showTab($, target)} />
      ) : (
        <Button key={`tab-${target}`} label={label} hotkey={hotkey} plain dimColor onPress={() => void showTab($, target)} />
      )

    const openCount = list.filter(item => !item.isAnswered).length

    const sessionTab = (
      <Box flexDirection="column" marginTop={1}>
        {Input && (
          <Box flexDirection="column">
            <Box borderStyle="round" borderColor="suggestion" paddingX={1} flexDirection="row">
              <Text color="suggestion">? </Text>
              <Box flexGrow={1} flexShrink={1}>
                <Input
                  key={NEW_INPUT_KEY}
                  placeholder="궁금한 것 입력 후 Enter"
                  submitLabel="추가"
                  value={typed}
                  autoFocus
                  onInput={(value: string) => void update($, draft, () => value)}
                  onSubmit={(value: string) => void addTopLevel($, value)}
                />
              </Box>
            </Box>
            <Text dimColor>'-' 또는 공백 2칸으로 시작하면 한 단계 하위</Text>
          </Box>
        )}
        <Box flexDirection="column" marginTop={1}>
          <Text bold>
            이번 세션 <Text color="suggestion">{openCount}</Text>
            <Text dimColor> / {list.length}</Text>
          </Text>
          {list.length === 0 && <Text dimColor>아직 적은 질문이 없습니다</Text>}
          {list.map((question, index) => (
            <Box flexDirection="column">
              {row(question)}
              {childInputAfter(index)}
            </Box>
          ))}
        </Box>
      </Box>
    )

    const archiveTab = (
      <Box flexDirection="column" marginTop={1}>
        {past.length === 0 && <Text dimColor>질문을 남긴 지난 세션이 없습니다</Text>}
        {past.map(record => {
          const isOpen = expanded === record.sessionId
          const open = record.items.filter(item => !item.isAnswered).length
          return (
            <Box flexDirection="column">
              <Button key={`archive:${record.sessionId}`} plain onPress={() => void toggleArchive($, record.sessionId)}>
                {isOpen ? '▾ ' : '▸ '}
                {kstStamp(record.createdAt)} · {basename(record.cwd)} <Text dimColor>({open}/{record.items.length})</Text>
              </Button>
              {isOpen &&
                record.items.map(question => (
                  <Box flexDirection="row" paddingLeft={question.depth * 2 + 2}>
                    <Text dimColor>{bullet(question)} </Text>
                    <Box flexShrink={1}>{questionText(question)}</Box>
                  </Box>
                ))}
            </Box>
          )
        })}
      </Box>
    )

    return (
      <Box flexDirection="column">
        <Box flexDirection="row" justifyContent="space-between">
          <Box flexDirection="row">
            {tabButton('session', '이번 세션', '1')}
            <Text>  </Text>
            {tabButton('archive', '지난 세션', '2')}
          </Box>
          <Button key="collapse" label="접기" hotkey="q" plain dimColor onPress={() => void collapse($)} />
        </Box>

        {activeTab === 'session' ? sessionTab : archiveTab}

        <Box flexDirection="column" marginTop={1}>
          {failure && <Text color="error">{failure}</Text>}
          <Text dimColor>아카이브: {box.archivePath.replace(/^.*\/\.claude\//, '~/.claude/')}</Text>
          {e.props.isFocused && activeTab === 'session' && (
            <Text dimColor>행 클릭 선택 · e 편집 · a 하위 · d 해결 · h/l 내어/들여쓰기 · k/j 이동 · x 삭제</Text>
          )}
        </Box>
      </Box>
    )
  })
}
