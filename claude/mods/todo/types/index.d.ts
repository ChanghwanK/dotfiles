export type TodoItem = { text: string; subs: string[] }

export type TodoSnapshot = {
  pageId: string
  title: string
  url: string
  open: TodoItem[]
  done: TodoItem[]
  syncedAt: number
}

export type SyncStatus = { isBusy: boolean; error: string | null }

// 삭제 확인을 기다리는 행 id (`open:<text>` 또는 `done:<text>`). 없으면 null.
export type PendingDelete = string | null

// 사이드바 탭: 오늘 일지(편집) / 앞선 가장 최근 일지(읽기 전용).
export type Tab = 'today' | 'previous'

declare module 'claude-code' {
  interface PluginState {
    'todo': { snapshot: TodoSnapshot | null; status: SyncStatus; pendingDelete: PendingDelete; draft: string; tab: Tab; previous: TodoSnapshot | null }
  }
}
