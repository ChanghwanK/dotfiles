// 질문 한 줄. 트리는 depth 를 가진 평면 목록으로 들고 있는다(아웃라이너 방식):
// 들여쓰기/내어쓰기가 depth 덧셈 하나로 끝나고, 순서가 곧 화면 순서다.
export type Question = { id: string; text: string; depth: number; isAnswered: boolean }

// 세션 하나의 질문 상자. $.store 에 `box:<sessionId>` 로 남아 지난 세션 탭에서 다시 본다.
export type QuestionBox = {
  sessionId: string
  cwd: string
  createdAt: number
  updatedAt: number
  items: Question[]
}

// 선택한 행 아래에 펼쳐지는 작업. 한 번에 하나만 연다.
export type Mode =
  | { kind: 'none' }
  | { kind: 'edit'; id: string }
  | { kind: 'child'; id: string }
  | { kind: 'confirmDelete'; id: string }

export type Tab = 'session' | 'archive'

declare module 'claude-code' {
  interface PluginState {
    'question-box': {
      items: Question[]
      selected: string | null
      mode: Mode
      draft: string
      editDraft: string
      tab: Tab
      archive: QuestionBox[]
      openArchive: string | null
      error: string | null
    }
  }
}
