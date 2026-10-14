import { expect, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'

// 사이드바를 실제로 그려 입력·클릭하고, Notion 에 쓰인 본문을 확인한다.
// Notion API 와 Keychain 은 테스트 hook 이 메모리로 대신 답한다.

const PAGE_ID = 'page-1'
const NOTION_TEXT = '  • victoriametrics 메모리 개선\n      ◦ go gc 적용 후 사용량 추이 파악\n  • ssh key 정리'

// previousText 가 있으면 "오늘보다 앞선 일지" 조회(Due Date before)에 그 본문의 다른 행으로 답한다.
const PREVIOUS_PAGE_ID = 'page-0'

function fakeNotion(on: Parameters<TestBody>[1], initial: string, previousText?: string) {
  const notion = { text: initial, writes: 0 }
  // 사이드바가 시작할 때 부르는 엔진 기능들. 테스트에서는 아무 일도 하지 않고 받아만 준다.
  // 엔진 기능 호출은 { value } 로 답한다.
  on('session.start', async (_$, e) => ({ cwd: e.cwd }) as any)
  for (const name of ['command.register', 'ui.status', 'store.set', 'clock.every'] as const) {
    on(name as any, async () => ({ value: undefined }) as any)
  }
  on('ui.open' as any, async () => ({ value: { isPlaced: true } }) as any)
  on('store.get' as any, async () => ({ value: undefined }) as any)
  on('clock.now' as any, async () => ({ value: 0 }) as any)
  on('process.run' as any, async () => ({ value: { exitCode: 0, stdout: 'token', stderr: '' } }) as any)
  on('http.fetch' as any, async (_$: unknown, e: any) => ({ value: await answer(e) }) as any)
  async function answer(e: any) {
    const method = e.init?.method ?? 'GET'
    const reply = (body: unknown) => ({ status: 200, ok: true, headers: {}, text: JSON.stringify(body) })
    if (method === 'POST' && e.url.includes('/query')) {
      const query = JSON.parse(String(e.init?.body))
      const isPreviousQuery = query.filter?.and?.some((condition: any) => condition.date?.before)
      if (isPreviousQuery) {
        if (previousText === undefined) return reply({ results: [] })
        return reply({
          results: [
            {
              id: PREVIOUS_PAGE_ID,
              url: 'https://notion.so/page-0',
              properties: { 이름: { type: 'title', title: [{ plain_text: '어제 업무 일지' }] }, "Todo's": { id: 'todo' } },
            },
          ],
        })
      }
      return reply({
        results: [
          {
            id: PAGE_ID,
            url: 'https://notion.so/page-1',
            properties: { 이름: { type: 'title', title: [{ plain_text: '오늘 업무 일지' }] }, "Todo's": { id: 'todo' } },
          },
        ],
      })
    }
    if (method === 'GET') {
      const text = e.url.includes(`/pages/${PREVIOUS_PAGE_ID}/`) ? (previousText ?? '') : notion.text
      return reply({ results: [{ rich_text: { plain_text: text } }], has_more: false })
    }
    // PATCH: 쓴 rich_text 를 이어 붙여 본문으로 둔다.
    const body = JSON.parse(String(e.init?.body))
    notion.text = body.properties["Todo's"].rich_text.map((segment: any) => segment.text.content).join('')
    notion.writes++
    return reply({})
  }
  return notion
}

// session.start 가 Notion(가짜)에서 오늘 행을 읽어 사이드바 상태를 채운다.
async function mountPane($: any) {
  await $.session.start({ cwd: '/' })
  return $.ui.mount({
    plugin: 'todo',
    surface: 'terminal',
    component: 'Pane',
    requestId: 'todo',
    props: { title: '오늘 할 일', isFocused: true, bodyColumns: 44 },
  })
}

// 버튼·입력 handler 는 쓰기를 기다리지 않고(void) 돌려준다. 쓰기 줄이 비도록 몇 tick 넘긴다.
async function settle(ui: any) {
  for (let i = 0; i < 20; i++) await ui.find({ key: 'refresh' })
}

test('새 할 일 입력 박스가 해야 할 일 목록보다 위에 따로 그려진다', async ($, on) => {
  fakeNotion(on, NOTION_TEXT)
  const ui = await mountPane($)

  const headings = (await ui.findAll({ type: 'Text', text: /^(새 할 일|해야 할 일)/ })).map((found: any) => found.text)
  expect(headings[0]).toBe('새 할 일')
  expect(headings[1]).toMatch(/^해야 할 일\s*2/)
  expect(await ui.find({ key: 'quick-input' })).toBeDefined()
  expect(await ui.find({ key: 'toggle:open:ssh key 정리' })).toBeDefined()
})

test('해야 할 일 행을 누르면 하위 항목과 함께 완료 섹션으로 옮겨 Notion 에 쓴다', async ($, on) => {
  const notion = fakeNotion(on, NOTION_TEXT)
  const ui = await mountPane($)

  await ui.press({ key: 'toggle:open:victoriametrics 메모리 개선' })
  await settle(ui)

  expect(notion.writes).toBe(1)
  expect(notion.text).toBe(
    '  • ssh key 정리\n완료\n  • victoriametrics 메모리 개선\n      ◦ go gc 적용 후 사용량 추이 파악',
  )
  expect(await ui.find({ key: 'toggle:done:victoriametrics 메모리 개선' })).toBeDefined()
})

test('새 할 일 박스에 적고 Enter 를 누르면 해야 할 일 끝에 붙는다', async ($, on) => {
  const notion = fakeNotion(on, NOTION_TEXT)
  const ui = await mountPane($)

  await ui.input({ key: 'quick-input', text: 'PR 리뷰' })
  await settle(ui)

  expect(notion.writes).toBe(1)
  expect(notion.text).toBe(`${NOTION_TEXT}\n  • PR 리뷰`)
  expect(await ui.find({ key: 'toggle:open:PR 리뷰' })).toBeDefined()
})

test("여러 줄로 적은 '-' 줄은 같은 입력의 상위 항목 아래 하위 항목으로 들어간다", async ($, on) => {
  const notion = fakeNotion(on, NOTION_TEXT)
  const ui = await mountPane($)

  await ui.input({ key: 'quick-input', text: 'Redis Tail Latency 개선\n- 테스트1\n- 테스트2' })
  await settle(ui)

  expect(notion.writes).toBe(1)
  expect(notion.text).toBe(`${NOTION_TEXT}\n  • Redis Tail Latency 개선\n      ◦ 테스트1\n      ◦ 테스트2`)
  expect(await ui.find({ key: 'toggle:open:Redis Tail Latency 개선' })).toBeDefined()
  expect(await ui.find({ key: 'toggle:open:- 테스트1' })).toBeUndefined()
})


const PREVIOUS_TEXT = '  • yoyo 개발\n      ◦ 디자인 QA\n완료\n  • ssh key 정리'

test('어제 탭은 오늘보다 앞선 일지를 읽기 전용으로 보여 주고 Notion 에 쓰지 않는다', async ($, on) => {
  const notion = fakeNotion(on, NOTION_TEXT, PREVIOUS_TEXT)
  const ui = await mountPane($)

  await ui.press({ key: 'tab-previous' })
  await settle(ui)

  expect(await ui.find({ type: 'Markdown', text: /어제 업무 일지/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /yoyo 개발/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /디자인 QA/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^완료 1/ })).toBeDefined()
  // 읽기 전용: 입력 박스와 체크·삭제 버튼이 없다
  expect(await ui.find({ key: 'quick-input' })).toBeUndefined()
  expect(await ui.find({ key: 'toggle:open:yoyo 개발' })).toBeUndefined()
  expect(notion.writes).toBe(0)

  await ui.press({ key: 'tab-today' })
  expect(await ui.find({ key: 'toggle:open:ssh key 정리' })).toBeDefined()
})

test('앞선 일지가 없으면 어제 탭은 빈 안내만 보여 준다', async ($, on) => {
  fakeNotion(on, NOTION_TEXT)
  const ui = await mountPane($)

  await ui.press({ key: 'tab-previous' })
  await settle(ui)

  expect(await ui.find({ type: 'Text', text: /앞선 업무 일지가 없습니다/ })).toBeDefined()
})
