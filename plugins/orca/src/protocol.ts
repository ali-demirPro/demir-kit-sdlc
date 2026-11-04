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

/** status.py's own `source`, or `none` when the snapshot is a readable error. */
export type StatusSource = 'live' | 'cache' | 'none'

/** What `status.snapshot` answers: a demir-kit status.py snapshot, or a readable error. */
export interface StatusSnapshot {
  ok: boolean
  /** Where the data was read from: live, the script's cache, or nothing. */
  source: StatusSource
  /** Project directory the worker read. */
  project: string | null
  /** `project.name` from status.py, shown as the panel heading. */
  project_name: string | null
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
