// The panel <-> worker contract, declared once: src/panel.tsx and src/worker.ts both read it.

export interface StatusLeaf {
  number: number
  title?: string
  state?: string
}

export interface StatusEpic {
  number: number
  title?: string
  state?: string
  risk?: string | null
  checkpoints?: { done: number; total: number }
  /** Epic `children` içinden issue listesinde ve demir-kit bloğu olanlar. */
  leaves?: StatusLeaf[]
  gate?: 'pass' | 'fail' | null
  open_findings?: number
  next_action?: string | null
}

export interface StatusCounts {
  epics: number
  leaves: number
  blocked: number
}

/** One workspace's demir-kit reading; an error stays inside its own project. */
export interface StatusProject {
  /** Orca workspace id, used by `workspace.open`. */
  id: string
  path: string
  /** `project.name` from status.py, else the workspace name. */
  name: string
  /** `project.tracker.repo`; aynı repo iki kez listelenmesin diye anahtar. */
  repo?: string
  /** `project.repo_root` (git ortak dizininin üstü); varsa ilk dedupe anahtarı. */
  repo_root?: string | null
  ok: boolean
  error?: string
  epics: StatusEpic[]
  counts: StatusCounts
  warnings: string[]
  stale: boolean
}

/** What `status.snapshot` answers: every workspace that carries a demir-kit. */
export interface StatusSnapshot {
  ok: boolean
  generated_at: string | null
  /** Workspace id of the focused project (listed first). */
  focused: string | null
  projects: StatusProject[]
  warnings: string[]
  error?: string
  /** `no-kit`: hiçbir workspace'te demir-kit yok; panel boş durum çizer. */
  code?: 'no-kit' | null
}

declare module 'orca' {
  interface PluginRequests {
    /** Every demir-kit workspace, from status.py or the 30 s per-project cache. */
    'status.snapshot': { output: StatusSnapshot }
    /** Panel asks the worker; the worker alone calls `workspace.open` on the host. */
    'workspace.open': { input: { id: string }; output: { ok: boolean; error?: string } }
  }
}
