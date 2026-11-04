// demir-kit worker: reads `status.py --json` and feeds the panel and the status bar.
// Orca transpiles this file when it loads: no build step, and no writes to the project.
import { execFile } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import type { OrcaWorkerApi } from 'orca/worker'
import type { StatusCounts, StatusEpic, StatusSnapshot } from './protocol'

const SNAPSHOT_KEY = 'snapshot'
const SAVED_AT_KEY = 'saved_at'
/** A second call inside this window answers from storage instead of running python. */
export const CACHE_MS = 30_000
const STATUS_TIMEOUT_MS = 10_000
const STATUS_SCRIPT = join('delivery', 'scripts', 'status.py')
const NO_KIT = 'demir-kit yok'

interface StatusJson {
  generated_at?: string
  stale?: boolean
  source?: string
  project?: { name?: string }
  epics?: StatusEpic[]
  counts?: StatusCounts
  warnings?: string[]
}

type HostCall = (method: string, params?: unknown) => Promise<unknown>

function call(orca: OrcaWorkerApi): HostCall {
  return orca.host.call as HostCall
}

/** `statusBar.update` names an item from `contributes.statusBarItems`. */
async function updateStatusBar(
  orca: OrcaWorkerApi,
  patch: { id: string; text?: string; tone?: 'neutral' | 'warning'; visible?: boolean }
): Promise<void> {
  await call(orca)('statusBar.update', patch)
}

function failed(error: string, warnings: string[], project: string | null = null): StatusSnapshot {
  return {
    ok: false,
    source: 'none',
    project,
    project_name: null,
    epics: [],
    counts: { epics: 0, leaves: 0, blocked: 0 },
    stale: true,
    generated_at: new Date().toISOString(),
    warnings: [...warnings, error],
    error
  }
}

/** The configured project path, else the first workspace that holds kit.config.yaml. */
async function resolveProject(orca: OrcaWorkerApi): Promise<string | null> {
  const configured = await orca.settings.get('projectPath')
  if (typeof configured === 'string' && configured.trim() !== '') {
    return configured.trim()
  }
  const listed = (await call(orca)('workspace.list')) as {
    workspaces?: Array<{ path?: string }>
  } | null
  for (const workspace of listed?.workspaces ?? []) {
    if (typeof workspace.path === 'string' && existsSync(join(workspace.path, 'kit.config.yaml'))) {
      return workspace.path
    }
  }
  return null
}

function runStatus(project: string): Promise<StatusJson> {
  return new Promise((resolve, reject) => {
    execFile(
      'python3',
      [join(project, STATUS_SCRIPT), '--json'],
      { cwd: project, timeout: STATUS_TIMEOUT_MS, maxBuffer: 4 * 1024 * 1024 },
      (error, stdout) => {
        if (error !== null) {
          reject(error)
          return
        }
        try {
          resolve(JSON.parse(stdout) as StatusJson)
        } catch (parseError) {
          reject(parseError)
        }
      }
    )
  })
}

function statusText(snapshot: StatusSnapshot): string {
  const epic = snapshot.epics[0]
  if (!epic || typeof epic.number !== 'number') {
    return NO_KIT
  }
  const done = epic.checkpoints?.done ?? 0
  const total = epic.checkpoints?.total ?? 0
  const gate = epic.gate ?? 'yok'
  return `EP-${epic.number} · CP ${done}/${total} · gate ${gate}`.slice(0, 64)
}

async function publish(orca: OrcaWorkerApi, snapshot: StatusSnapshot): Promise<void> {
  try {
    await updateStatusBar(orca, {
      id: 'epic',
      text: statusText(snapshot),
      tone: snapshot.ok ? 'neutral' : 'warning'
    })
    // Maliyet alanı henüz yok: status.py cost_delta null döndürüyor.
    await updateStatusBar(orca, { id: 'cost', text: '-' })
  } catch (error) {
    // No status bar (headless host): the panel still gets the snapshot.
    orca.log(`demir-kit: status bar güncellenemedi: ${String(error)}`)
  }
}

async function fromCache(orca: OrcaWorkerApi): Promise<StatusSnapshot | null> {
  const savedAt = await orca.storage.get(SAVED_AT_KEY)
  if (typeof savedAt !== 'number' || Date.now() - savedAt >= CACHE_MS) {
    return null
  }
  const snapshot = await orca.storage.get(SNAPSHOT_KEY)
  // Önbellekten gelen yanıt canlı değil: panel bunu `source` ile görür.
  return isSnapshot(snapshot) ? { ...snapshot, source: 'cache' } : null
}

function isSnapshot(value: unknown): value is StatusSnapshot {
  return (
    typeof value === 'object' &&
    value !== null &&
    'ok' in value &&
    typeof (value as { ok: unknown }).ok === 'boolean' &&
    'counts' in value
  )
}

async function refresh(orca: OrcaWorkerApi, force: boolean): Promise<StatusSnapshot> {
  const warnings: string[] = []
  let project: string | null = null
  try {
    if (!force) {
      const cached = await fromCache(orca)
      if (cached !== null) {
        return cached
      }
    }

    project = await resolveProject(orca)
    if (project === null) {
      const snapshot = failed('proje yolu bulunamadı: Ayarlar > demir-kit > Proje yolu', warnings)
      await publish(orca, snapshot)
      return snapshot
    }

    const data = await runStatus(project)
    const snapshot: StatusSnapshot = {
      ok: true,
      source: data.source === 'cache' ? 'cache' : 'live',
      project,
      project_name: typeof data.project?.name === 'string' ? data.project.name : null,
      epics: Array.isArray(data.epics) ? data.epics : [],
      counts: data.counts ?? { epics: 0, leaves: 0, blocked: 0 },
      stale: data.stale === true,
      generated_at: data.generated_at ?? new Date().toISOString(),
      warnings: [...warnings, ...(Array.isArray(data.warnings) ? data.warnings : [])]
    }
    await orca.storage.set(SNAPSHOT_KEY, snapshot)
    await orca.storage.set(SAVED_AT_KEY, Date.now())
    await publish(orca, snapshot)
    return snapshot
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    const snapshot = failed(message.slice(0, 500), warnings, project)
    await publish(orca, snapshot)
    return snapshot
  }
}

export default async function activate(orca: OrcaWorkerApi): Promise<void> {
  orca.panels.handle('status.snapshot', async () => refresh(orca, false))

  orca.commands.register('demir-kit.refresh', () => {
    void refresh(orca, true)
  })

  orca.events.on('workspace.changed', () => {
    void refresh(orca, true)
  })

  orca.settings.onDidChange(() => {
    void refresh(orca, true)
  })

  await refresh(orca, true)
}
