// The panel <-> worker contract, declared once: src/panel.tsx and src/worker.ts both read it.

export interface StatusLeaf {
  number: number
  title?: string
  state?: string
}

/** One checkpoint of a child leaf: its entry plus that child's done state. */
export interface StatusCheckpoint {
  id: string
  title: string
  done: boolean
  /** Checkpoint'i taşıyan çocuk issue numarası; panel `#13 · CP-1` çizer. */
  leaf: number
}

/** Eski `status.py` biçimi: dizi değil `{done,total}`; panel onu boş sayar. */
export interface StatusCheckpointSummary {
  done: number
  total: number
}

export type AgentState = 'working' | 'blocked' | 'waiting' | 'idle' | 'done'

/** One agent Orca reports for the focused workspace. */
export interface StatusAgent {
  terminalId?: string | null
  title?: string | null
  state: AgentState
}

/** Live agent counts: `status.py` never supplies them, `agents.list` does. */
export interface StatusLive {
  working: number
  blocked: number
  waiting: number
  /** Boşta ajan; sessizce atılmaz, `boşta` diye sayılır. */
  idle: number
  done: number
}

export interface StatusEpic {
  number: number
  title?: string
  state?: string
  risk?: string | null
  /** Child checkpoint entries in child order; `done` is per child (`leaf-done`). */
  checkpoints?: StatusCheckpoint[] | StatusCheckpointSummary
  /** Issue `updatedAt`, or null when `gh` did not send it. */
  updated_at?: string | null
  /** GitHub issue link from `tracker.repo`, or null. */
  url?: string | null
  /** Epic `children` içinden issue listesinde ve demir-kit bloğu olanlar. */
  leaves?: StatusLeaf[]
  gate?: 'pass' | 'fail' | null
  open_findings?: number
  approvals?: { agent_approved: boolean; human_qa: boolean }
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
  /** Live agents of the focused workspace; empty for other projects. */
  agents?: StatusAgent[]
  live?: StatusLive
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

/** Panelden gelen aksiyonun yanıtı: hata fırlatılmaz, kısa sonuç döner. */
export interface ActionReply {
  ok: boolean
  message: string
  exitCode: number
  /** Komutun son satırları; panel uzun çıktıyı göstermez. */
  tail: string
  /** Aksiyonun issue bağlantısı; yoksa boş. */
  url: string
  /** Kısmi başarı: iş tamam, yan adım (issue kapatma) düştü; panel uyarı çizer. */
  warning?: string
}

declare module 'orca' {
  interface PluginRequests {
    /** Every demir-kit workspace, from status.py or the 30 s per-project cache. */
    'status.snapshot': { output: StatusSnapshot }
    /** Panel asks the worker; the worker alone calls `workspace.open` on the host. */
    'workspace.open': { input: { id: string }; output: { ok: boolean; error?: string } }
    /** İnsan kabul/red yorumu + `transition.sh`; worker çağırır. */
    'epic.decision': {
      input: {
        /** Panelin gördüğü proje kartının `path` değeri. */
        projectPath: string
        issue: number
        decision: 'accepted' | 'rejected'
      }
      output: ActionReply
    }
    /** Sıradaki leaf claim: `next-leaf.sh --claim`; worker çağırır. */
    'leaf.claim': { input: { projectPath: string }; output: ActionReply }
  }
}
