import type { TodoItem } from '../types'

// Notion `Todo's` 속성은 체크 상태가 없는 rich_text 다. 완료 여부는 같은 필드 안의
// `완료` 헤더 줄로 구분한다: 헤더 위는 해야 할 일, 아래는 완료한 일.
// Notion 표에서도 완료 항목이 그대로 보이게 하려는 선택이다 (별도 속성 추가 없이).
export const DONE_HEADER = '완료'

const TOP_BULLET = /^[•\-*]\s*/
const SUB_BULLET = /^[◦▪○]\s*/
const SUB_INDENT_MIN = 4

export type ParsedTodos = { open: TodoItem[]; done: TodoItem[] }

export function parseTodos(raw: string): ParsedTodos {
  const parsed: ParsedTodos = { open: [], done: [] }
  let section = parsed.open

  for (const line of raw.split('\n')) {
    const trimmed = line.trim()
    if (trimmed === DONE_HEADER) {
      section = parsed.done
      continue
    }
    if (trimmed === '') continue

    const indent = line.length - line.trimStart().length
    const hasSubBullet = SUB_BULLET.test(trimmed)
    const isSub = hasSubBullet || (indent >= SUB_INDENT_MIN && TOP_BULLET.test(trimmed))
    const text = trimmed.replace(hasSubBullet ? SUB_BULLET : TOP_BULLET, '').trim()
    // 템플릿이 남긴 빈 불릿(`  • `)은 할 일이 아니다.
    if (text === '') continue

    const parent = section[section.length - 1]
    if (isSub && parent) parent.subs.push(text)
    else section.push({ text, subs: [] })
  }

  return parsed
}

function renderItems(items: readonly TodoItem[]): string {
  return items
    .map(item => [`  • ${item.text}`, ...item.subs.map(sub => `      ◦ ${sub}`)].join('\n'))
    .join('\n')
}

export type RichTextSegment = {
  type: 'text'
  text: { content: string }
  annotations?: { bold?: boolean; strikethrough?: boolean }
}

// Notion API 는 rich_text 객체 하나의 content 를 2000자로 제한한다.
const NOTION_TEXT_LIMIT = 2000

function segments(content: string, annotations?: RichTextSegment['annotations']): RichTextSegment[] {
  const out: RichTextSegment[] = []
  for (let i = 0; i < content.length; i += NOTION_TEXT_LIMIT) {
    const piece: RichTextSegment = { type: 'text', text: { content: content.slice(i, i + NOTION_TEXT_LIMIT) } }
    if (annotations) piece.annotations = annotations
    out.push(piece)
  }
  return out
}

// 세그먼트 수를 최소로 유지한다: 페이지 조회 API 는 rich_text 를 25개 요소에서 자르므로
// 항목마다 세그먼트를 나누면 긴 목록이 잘려 읽힐 수 있다.
export function serializeTodos(todos: ParsedTodos): RichTextSegment[] {
  // 해야 할 일이 비면 Notion 템플릿과 같은 빈 불릿을 남겨 손으로 이어 쓰기 쉽게 한다.
  const openText = todos.open.length > 0 ? renderItems(todos.open) : '  • '
  if (todos.done.length === 0) return segments(openText)

  return [
    ...segments(`${openText}\n`),
    ...segments(DONE_HEADER, { bold: true }),
    ...segments(`\n${renderItems(todos.done)}`, { strikethrough: true }),
  ]
}

export function sameItem(a: TodoItem, b: TodoItem): boolean {
  return a.text === b.text
}

// 체크한 항목을 반대쪽 섹션 끝으로 옮긴다. 화면을 그린 뒤 Notion 에서 내용이
// 바뀌었을 수 있으므로 항상 최신 본문에 적용하고, 항목이 사라졌으면 null 을 돌려준다.
export function moveItem(todos: ParsedTodos, item: TodoItem, toDone: boolean): ParsedTodos | null {
  const from = toDone ? todos.open : todos.done
  const index = from.findIndex(candidate => sameItem(candidate, item))
  if (index < 0) return null

  const moved = from[index]
  if (!moved) return null
  const rest = from.filter((_, i) => i !== index)
  return toDone
    ? { open: rest, done: [...todos.done, moved] }
    : { open: [...todos.open, moved], done: rest }
}

export type Section = 'open' | 'done'

// 새 할 일은 해야 할 일 끝에 붙인다. 이미 같은 이름이 있으면 null: 항목을 이름으로
// 찾아 옮기고 지우므로, 이름이 겹치면 체크·삭제가 엉뚱한 쪽에 걸린다.
export function addItem(todos: ParsedTodos, text: string): ParsedTodos | null {
  const trimmed = text.trim()
  if (trimmed === '') return null
  const isDuplicate = [...todos.open, ...todos.done].some(item => item.text === trimmed)
  if (isDuplicate) return null
  return { ...todos, open: [...todos.open, { text: trimmed, subs: [] }] }
}

// 하위 항목까지 통째로 지운다. 화면을 그린 뒤 Notion 에서 사라졌으면 null.
export function removeItem(todos: ParsedTodos, item: TodoItem, section: Section): ParsedTodos | null {
  const from = todos[section]
  const index = from.findIndex(candidate => sameItem(candidate, item))
  if (index < 0) return null
  return { ...todos, [section]: from.filter((_, i) => i !== index) }
}


// 빠른 입력 줄의 한 줄을 해야 할 일 끝에 붙인다. `-` 로 시작하면 마지막 상위 항목의
// 하위 항목이 된다(Notion 에서 `-` 가 불릿을 만드는 것과 같은 손버릇). 상위 항목이
// 없으면 그냥 상위 항목으로 붙인다. 빈 글이거나 같은 이름이 이미 있으면 null.
export const SUB_PREFIX = /^-\s*/

export function appendLine(todos: ParsedTodos, line: string): ParsedTodos | null {
  const trimmed = line.trim()
  const parent = todos.open[todos.open.length - 1]
  if (!SUB_PREFIX.test(trimmed) || !parent) return addItem(todos, trimmed.replace(SUB_PREFIX, ''))

  const sub = trimmed.replace(SUB_PREFIX, '').trim()
  if (sub === '' || parent.subs.includes(sub)) return null
  const open = [...todos.open.slice(0, -1), { ...parent, subs: [...parent.subs, sub] }]
  return { ...todos, open }
}

// 입력 박스에 여러 줄을 적어 한 번에 보낸 경우. 줄마다 appendLine 을 차례로 적용하므로
// `-` 줄은 바로 위에 적은 상위 항목의 하위가 된다. 통째로 한 항목에 넣으면 줄바꿈이
// 본문에 그대로 들어가 다시 읽을 때 `-` 줄이 들여쓰기 없는 상위 항목으로 흩어진다.
// 한 줄이라도 거절되면(중복 등) 전체를 거절해 입력한 글을 고쳐 다시 보내게 한다.
export function appendBlock(todos: ParsedTodos, block: string): ParsedTodos | null {
  const lines = block.split(/\r?\n/).filter(line => line.trim() !== '')
  if (lines.length === 0) return null

  let next = todos
  for (const line of lines) {
    const appended = appendLine(next, line)
    if (!appended) return null
    next = appended
  }
  return next
}
