import { expect, test } from 'claude-code/testing'

import type { Question } from '../types'
import { append, appendChild, editText, indent, move, outdent, parseBlock, remove, toggleAnswered, toMarkdown } from '../hooks/outline'

function ids() {
  let n = 0
  return () => `q${++n}`
}

// 읽기 쉬운 모양으로 트리를 비교한다: "  텍스트" = 깊이 1.
const shape = (list: readonly Question[] | null) => list?.map(item => `${'  '.repeat(item.depth)}${item.text}`)

function tree(...lines: string[]): Question[] {
  return lines.map(line => {
    const depth = (line.length - line.trimStart().length) / 2
    return { id: line.trim(), text: line.trim(), depth, isAnswered: false }
  })
}

test('한 줄 입력에서 - 로 시작하면 한 단계 하위가 된다', async () => {
  expect(parseBlock('Loki 쿼리는 왜 느린가')).toEqual([{ text: 'Loki 쿼리는 왜 느린가', depth: 0 }])
  expect(parseBlock('- chunk 캐시 적중률은?')).toEqual([{ text: 'chunk 캐시 적중률은?', depth: 1 }])
})

test('붙여 넣은 마크다운 목록은 가장 얕은 줄을 최상위로 맞춘다', async () => {
  expect(parseBlock('- a\n  - b\n    - c\n- d')).toEqual([
    { text: 'a', depth: 0 },
    { text: 'b', depth: 1 },
    { text: 'c', depth: 2 },
    { text: 'd', depth: 0 },
  ])
})

test('빈 질문은 추가하지 않는다', async () => {
  expect(append([], '   \n  - ', ids())).toBeNull()
})

test('부모 없이 두 단계 깊어진 하위는 바로 앞 질문의 하위로 당겨진다', async () => {
  const added = append([], 'a\n      c', ids())

  expect(shape(added)).toEqual(['a', '  c'])
})

test('빈 목록에 하위 질문을 먼저 적으면 최상위가 된다', async () => {
  expect(shape(append([], '- 하위', ids()))).toEqual(['하위'])
})

test('하위 질문 추가는 부모의 하위 목록 끝에 들어간다', async () => {
  const list = tree('a', '  a1', 'b')

  expect(shape(appendChild(list, 'a', 'a2', ids()))).toEqual(['a', '  a1', '  a2', 'b'])
})

test('들여쓰기는 하위까지 함께 옮기고, 앞 형제가 없으면 거절한다', async () => {
  const list = tree('a', 'b', '  b1')

  expect(shape(indent(list, 'b'))).toEqual(['a', '  b', '    b1'])
  expect(indent(list, 'a')).toBeNull()
  expect(indent(list, 'b1')).toBeNull()
})

test('내어쓰기는 하위까지 함께 꺼내고, 최상위는 거절한다', async () => {
  const list = tree('a', '  b', '    b1')

  expect(shape(outdent(list, 'b'))).toEqual(['a', 'b', '  b1'])
  expect(outdent(list, 'a')).toBeNull()
})

test('위아래 이동은 같은 부모 안의 형제와 하위째 자리를 바꾼다', async () => {
  const list = tree('a', '  a1', 'b', '  b1', '  b2')

  expect(shape(move(list, 'b', -1))).toEqual(['b', '  b1', '  b2', 'a', '  a1'])
  expect(shape(move(list, 'b1', 1))).toEqual(['a', '  a1', 'b', '  b2', '  b1'])
  // 부모 경계를 넘지 않는다.
  expect(move(list, 'b1', -1)).toBeNull()
  expect(move(list, 'a1', 1)).toBeNull()
})

test('삭제는 하위 질문까지 지운다', async () => {
  expect(shape(remove(tree('a', '  a1', 'b'), 'a'))).toEqual(['b'])
})

test('편집은 빈 글로 바꾸지 않는다', async () => {
  const list = tree('a')

  expect(editText(list, 'a', '  ')).toBeNull()
  expect(editText(list, 'a', ' a 수정 ')?.[0]?.text).toBe('a 수정')
})

test('아카이브 마크다운은 해결 여부를 체크박스로, 깊이를 2칸 들여쓰기로 쓴다', async () => {
  const answered = toggleAnswered(tree('a', '  a1'), 'a1')!
  const markdown = toMarkdown(answered, '질문 상자', ['session: s1'])

  expect(markdown).toBe('# 질문 상자\n\n- session: s1\n\n- [ ] a\n  - [x] a1\n')
})
