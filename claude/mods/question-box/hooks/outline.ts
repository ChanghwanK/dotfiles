import type { Question } from '../types'

// 사이드바 폭(44칸)에서 한 단계 2칸씩 들여 쓰면 6단계면 질문 글이 들어갈 자리가 남지 않는다.
export const MAX_DEPTH = 5

export type NewLine = { text: string; depth: number }

// 변경 함수는 바뀐 새 목록을 돌려주고, 할 수 없는 변경(맨 위 항목 들여쓰기 등)이면 null 을 돌려준다.
// 호출자는 null 이면 저장하지 않는다.
export type Change = Question[] | null

// 항목과 그 하위 전체의 [시작, 끝) 범위. 하위는 바로 뒤에 이어지는 더 깊은 항목들이다.
function subtreeRange(items: readonly Question[], index: number): [number, number] {
  const depth = items[index]!.depth
  let end = index + 1
  while (end < items.length && items[end]!.depth > depth) end++
  return [index, end]
}

function indexOf(items: readonly Question[], id: string): number {
  return items.findIndex(item => item.id === id)
}

export function hasChildren(items: readonly Question[], id: string): boolean {
  const index = indexOf(items, id)
  return index >= 0 && (items[index + 1]?.depth ?? -1) > items[index]!.depth
}

const BULLET = /^[-*+•◦▪‣]\s*/

// 입력 블록(한 줄 또는 붙여 넣은 여러 줄)을 깊이가 붙은 줄로 읽는다.
// - 앞 공백 2칸(또는 탭 1개)이 한 단계다: 마크다운 목록을 그대로 붙여 넣을 수 있게.
// - 한 줄만 쓸 때 `-` 로 시작하면 한 단계 하위다: todo mod 와 같은 입력 습관.
// - 여러 줄이면 가장 얕은 줄을 0으로 맞춘다: 붙여 넣은 `- a\n  - b` 가 하위로 밀려 들어가지 않게.
export function parseBlock(block: string): NewLine[] {
  const raw = block
    .split('\n')
    .map(line => line.replace(/\s+$/, ''))
    .filter(line => line.trim() !== '')
    .map(line => {
      const indent = /^[ \t]*/.exec(line)![0]
      const level = [...indent].reduce((sum, ch) => sum + (ch === '\t' ? 2 : 1), 0)
      const rest = line.slice(indent.length)
      const isBulleted = BULLET.test(rest)
      return { text: rest.replace(BULLET, '').trim(), depth: Math.floor(level / 2) + (isBulleted ? 1 : 0) }
    })
    .filter(line => line.text !== '')
  if (raw.length <= 1) return raw
  const shallowest = Math.min(...raw.map(line => line.depth))
  return raw.map(line => ({ ...line, depth: line.depth - shallowest }))
}

// 깊이가 바로 앞 줄보다 두 단계 이상 깊어지지 않게 깎는다: 부모 없는 하위 질문이 생기지 않게.
function clampDepths(lines: readonly NewLine[], previousDepth: number, base: number): NewLine[] {
  let previous = previousDepth
  return lines.map(line => {
    const depth = Math.min(base + line.depth, previous + 1, MAX_DEPTH)
    previous = depth
    return { ...line, depth }
  })
}

function toQuestions(lines: readonly NewLine[], makeId: () => string): Question[] {
  return lines.map(line => ({ id: makeId(), text: line.text, depth: line.depth, isAnswered: false }))
}

// 목록 끝에 붙인다.
export function append(items: readonly Question[], block: string, makeId: () => string): Change {
  const lines = parseBlock(block)
  if (lines.length === 0) return null
  const lastDepth = items.length === 0 ? -1 : items[items.length - 1]!.depth
  return [...items, ...toQuestions(clampDepths(lines, lastDepth, 0), makeId)]
}

// parentId 의 하위 맨 끝에 붙인다. 블록의 0단계가 parent 의 바로 아래 단계가 된다.
export function appendChild(items: readonly Question[], parentId: string, block: string, makeId: () => string): Change {
  const index = indexOf(items, parentId)
  const lines = parseBlock(block)
  if (index < 0 || lines.length === 0) return null
  const parentDepth = items[index]!.depth
  if (parentDepth >= MAX_DEPTH) return null
  const [, end] = subtreeRange(items, index)
  const previousDepth = items[end - 1]!.depth
  const added = toQuestions(clampDepths(lines, previousDepth, parentDepth + 1), makeId)
  return [...items.slice(0, end), ...added, ...items.slice(end)]
}

export function editText(items: readonly Question[], id: string, text: string): Change {
  const index = indexOf(items, id)
  const trimmed = text.trim()
  if (index < 0 || trimmed === '') return null
  return items.map(item => (item.id === id ? { ...item, text: trimmed } : item))
}

export function toggleAnswered(items: readonly Question[], id: string): Change {
  if (indexOf(items, id) < 0) return null
  return items.map(item => (item.id === id ? { ...item, isAnswered: !item.isAnswered } : item))
}

// 하위까지 함께 지운다. 하위만 남기면 부모 없는 질문이 생긴다.
export function remove(items: readonly Question[], id: string): Change {
  const index = indexOf(items, id)
  if (index < 0) return null
  const [start, end] = subtreeRange(items, index)
  return [...items.slice(0, start), ...items.slice(end)]
}

function shiftSubtree(items: readonly Question[], index: number, delta: number): Question[] {
  const [start, end] = subtreeRange(items, index)
  return items.map((item, i) => (i >= start && i < end ? { ...item, depth: item.depth + delta } : item))
}

// 바로 앞 형제의 하위로 들어간다. 앞에 같은 깊이 이상의 항목이 없으면(첫 자식) 들어갈 부모가 없다.
export function indent(items: readonly Question[], id: string): Change {
  const index = indexOf(items, id)
  if (index <= 0) return null
  const depth = items[index]!.depth
  if (items[index - 1]!.depth < depth) return null
  const [start, end] = subtreeRange(items, index)
  const deepest = Math.max(...items.slice(start, end).map(item => item.depth))
  if (deepest >= MAX_DEPTH) return null
  return shiftSubtree(items, index, 1)
}

// 한 단계 위로 나온다. 뒤따르던 형제는 그대로 두므로 나온 항목의 하위가 된다(일반 아웃라이너와 같다).
export function outdent(items: readonly Question[], id: string): Change {
  const index = indexOf(items, id)
  if (index < 0 || items[index]!.depth === 0) return null
  return shiftSubtree(items, index, -1)
}

// 같은 부모 아래 앞/뒤 형제와 하위째 자리를 바꾼다.
function siblingIndex(items: readonly Question[], index: number, direction: -1 | 1): number {
  const depth = items[index]!.depth
  if (direction === -1) {
    for (let i = index - 1; i >= 0; i--) {
      if (items[i]!.depth < depth) return -1
      if (items[i]!.depth === depth) return i
    }
    return -1
  }
  const [, end] = subtreeRange(items, index)
  return end < items.length && items[end]!.depth === depth ? end : -1
}

export function move(items: readonly Question[], id: string, direction: -1 | 1): Change {
  const index = indexOf(items, id)
  if (index < 0) return null
  const other = siblingIndex(items, index, direction)
  if (other < 0) return null
  const [firstStart, firstEnd] = subtreeRange(items, Math.min(index, other))
  const [, secondEnd] = subtreeRange(items, Math.max(index, other))
  return [
    ...items.slice(0, firstStart),
    ...items.slice(firstEnd, secondEnd),
    ...items.slice(firstStart, firstEnd),
    ...items.slice(secondEnd),
  ]
}

// 아카이브 파일 본문. Obsidian·Zed 에서 체크리스트로 열리도록 GFM 작업 목록으로 쓴다.
export function toMarkdown(items: readonly Question[], heading: string, meta: readonly string[]): string {
  const lines = items.map(item => `${'  '.repeat(item.depth)}- [${item.isAnswered ? 'x' : ' '}] ${item.text}`)
  return [`# ${heading}`, '', ...meta.map(line => `- ${line}`), '', ...lines, ''].join('\n')
}
