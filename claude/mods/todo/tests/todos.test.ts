import { expect, test } from 'claude-code/testing'

import { addItem, appendBlock, appendLine, moveItem, parseTodos, removeItem, serializeTodos } from '../hooks/todos'

// 2026-10-13 업무 일지의 Todo's 원문 (Notion API plain_text 그대로).
const NOTION_SAMPLE =
  '  • victoriametrics 메모리 개선 \n      ◦ go gc 적용 후 사용량 추이 파악\n      ◦ log 수집 활성화\n' +
  '  • node cpu spike 알럿 노이즈 줄이기\n  • ssh key 정리'

const plain = (segments: ReturnType<typeof serializeTodos>) => segments.map(s => s.text.content).join('')

test('Notion 불릿 본문을 상위 항목과 하위 항목으로 읽는다', async () => {
  const todos = parseTodos(NOTION_SAMPLE)

  expect(todos.open.map(item => item.text)).toEqual(['victoriametrics 메모리 개선', 'node cpu spike 알럿 노이즈 줄이기', 'ssh key 정리'])
  expect(todos.open[0]?.subs).toEqual(['go gc 적용 후 사용량 추이 파악', 'log 수집 활성화'])
  expect(todos.done).toEqual([])
})

test('템플릿의 빈 불릿은 할 일로 세지 않는다', async () => {
  expect(parseTodos('  • ')).toEqual({ open: [], done: [] })
})

test('체크한 항목은 하위 항목과 함께 완료 섹션으로 옮겨지고 다시 읽어도 같다', async () => {
  const todos = parseTodos(NOTION_SAMPLE)
  const moved = moveItem(todos, { text: 'victoriametrics 메모리 개선', subs: [] }, true)

  expect(moved?.open.map(item => item.text)).toEqual(['node cpu spike 알럿 노이즈 줄이기', 'ssh key 정리'])
  expect(moved?.done).toEqual([{ text: 'victoriametrics 메모리 개선', subs: ['go gc 적용 후 사용량 추이 파악', 'log 수집 활성화'] }])
  expect(parseTodos(plain(serializeTodos(moved!)))).toEqual(moved)
})

test('완료 항목은 취소선, 헤더는 굵게 Notion에 쓴다', async () => {
  const moved = moveItem(parseTodos(NOTION_SAMPLE), { text: 'ssh key 정리', subs: [] }, true)!
  const segments = serializeTodos(moved)

  expect(segments.find(s => s.text.content === '완료')?.annotations).toEqual({ bold: true })
  expect(segments.at(-1)?.annotations).toEqual({ strikethrough: true })
})

test('체크를 풀면 해야 할 일 끝으로 돌아온다', async () => {
  const done = moveItem(parseTodos(NOTION_SAMPLE), { text: 'ssh key 정리', subs: [] }, true)!
  const back = moveItem(done, { text: 'ssh key 정리', subs: [] }, false)

  expect(back?.open.at(-1)?.text).toBe('ssh key 정리')
  expect(back?.done).toEqual([])
})

test('Notion에서 이미 사라진 항목은 옮기지 않는다', async () => {
  expect(moveItem(parseTodos(NOTION_SAMPLE), { text: '없는 항목', subs: [] }, true)).toBeNull()
})

test('모두 완료하면 해야 할 일 자리에 템플릿 빈 불릿을 남긴다', async () => {
  const text = plain(serializeTodos({ open: [], done: [{ text: 'a', subs: [] }] }))

  expect(text.startsWith('  • \n완료')).toBe(true)
})

test('새 할 일은 해야 할 일 끝에 하위 항목 없이 붙는다', async () => {
  const added = addItem(parseTodos(NOTION_SAMPLE), '  PR 리뷰  ')

  expect(added?.open.at(-1)).toEqual({ text: 'PR 리뷰', subs: [] })
  expect(parseTodos(plain(serializeTodos(added!)))).toEqual(added)
})

test('빈 입력이나 이미 있는 이름은 추가하지 않는다', async () => {
  const todos = parseTodos(NOTION_SAMPLE)

  expect(addItem(todos, '   ')).toBeNull()
  expect(addItem(todos, 'ssh key 정리')).toBeNull()
})

test('삭제하면 하위 항목까지 함께 사라지고 다른 섹션은 그대로다', async () => {
  const done = moveItem(parseTodos(NOTION_SAMPLE), { text: 'ssh key 정리', subs: [] }, true)!
  const removed = removeItem(done, { text: 'victoriametrics 메모리 개선', subs: [] }, 'open')

  expect(removed?.open.map(item => item.text)).toEqual(['node cpu spike 알럿 노이즈 줄이기'])
  expect(removed?.done).toEqual(done.done)
})

test('완료 섹션의 항목도 지울 수 있다', async () => {
  const done = moveItem(parseTodos(NOTION_SAMPLE), { text: 'ssh key 정리', subs: [] }, true)!

  expect(removeItem(done, { text: 'ssh key 정리', subs: [] }, 'done')?.done).toEqual([])
})

test('Notion에서 이미 사라진 항목은 지우지 않는다', async () => {
  expect(removeItem(parseTodos(NOTION_SAMPLE), { text: '없는 항목', subs: [] }, 'open')).toBeNull()
})

test('빠른 입력 줄은 해야 할 일 끝에 상위 항목으로 붙는다', async () => {
  const appended = appendLine(parseTodos(NOTION_SAMPLE), '  Redis 메모리 점검 ')!

  expect(appended.open.at(-1)).toEqual({ text: 'Redis 메모리 점검', subs: [] })
})

test("빠른 입력 줄이 '-' 로 시작하면 마지막 상위 항목의 하위 항목이 된다", async () => {
  const appended = appendLine(parseTodos(NOTION_SAMPLE), '- 키 회전')!

  expect(appended.open.at(-1)).toEqual({ text: 'ssh key 정리', subs: ['키 회전'] })
  expect(plain(serializeTodos(appended))).toContain('  • ssh key 정리\n      ◦ 키 회전')
})

test("상위 항목이 없을 때 '-' 줄은 상위 항목으로 붙고, 빈 줄과 같은 하위 항목은 거절한다", async () => {
  expect(appendLine({ open: [], done: [] }, '- 첫 할 일')?.open).toEqual([{ text: '첫 할 일', subs: [] }])
  expect(appendLine(parseTodos(NOTION_SAMPLE), '-  ')).toBeNull()
  expect(appendLine(parseTodos(NOTION_SAMPLE), '   ')).toBeNull()
  expect(appendLine(appendLine(parseTodos(NOTION_SAMPLE), '- 키 회전')!, '- 키 회전')).toBeNull()
})

test("여러 줄 입력은 '-' 줄을 바로 위 상위 항목의 하위로 붙인다", async () => {
  const appended = appendBlock(parseTodos(NOTION_SAMPLE), 'Redis Tail Latency 개선\n- 테스트1\n  - 테스트2\n')!

  expect(appended.open.at(-1)).toEqual({ text: 'Redis Tail Latency 개선', subs: ['테스트1', '테스트2'] })
  expect(parseTodos(plain(serializeTodos(appended)))).toEqual(appended)
})

test('여러 줄 입력 중 한 줄이라도 거절되면 아무것도 붙이지 않는다', async () => {
  expect(appendBlock(parseTodos(NOTION_SAMPLE), '새 할 일\nssh key 정리')).toBeNull()
  expect(appendBlock(parseTodos(NOTION_SAMPLE), '\n  \n')).toBeNull()
})
