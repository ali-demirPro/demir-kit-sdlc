// The panel <-> worker contract, declared once: src/panel.tsx and src/worker.ts both read it.

export interface StatusEpic {
  number: number
  title?: string
  state?: string
  risk?: string | null
  checkpoints?: { done: number; total: number }
  gate?: 'pass' | 'fail' | null
  open_findings?: number
  next_action?: string | null
}

export interface StatusCounts {
  epics: number
  leaves: number
  blocked: number
}

/** What `status.snapshot` answers: a demir-kit status.py snapshot, or a readable error. */
export interface StatusSnapshot {
  ok: boolean
  project: string | null
  epics: StatusEpic[]
  counts: StatusCounts
  stale: boolean
  generated_at: string | null
  warnings: string[]
  error?: string
}

declare module 'orca' {
  interface PluginRequests {
    /** The last demir-kit status, from status.py or the 30 s cache. */
    'status.snapshot': { output: StatusSnapshot }
  }
}
