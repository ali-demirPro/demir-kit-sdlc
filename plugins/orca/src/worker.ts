// demir-kit worker: reads `status.py --json` and feeds the panel and the status bar.
// Orca transpiles this file when it loads: no build step, and no writes to the project.
import { execFile } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
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

function failed(
  error: string,
  warnings: string[],
  project: string | null = null,
  code: 'no-kit' | null = null
): StatusSnapshot {
  return {
    ok: false,
    code,
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

interface ProjectRef {
  path: string
  kitRoot: string
}

/** `kit.config.yaml` içindeki `kit.root`; status.py orada yoksa null. */
function kitRootFor(project: string): string | null {
  try {
    const text = readFileSync(join(project, 'kit.config.yaml'), 'utf8')
    const match = text.match(/^\s*root:\s*['"]?([^'"\n#]+)/m)
    const rel = match ? match[1].trim() : '.'
    if (rel.startsWith('/') || rel.split(/[\\/]/).includes('..')) {
      return null
    }
    const root = rel === '.' ? project : join(project, rel)
    return existsSync(join(root, STATUS_SCRIPT)) ? root : null
  } catch {
    return existsSync(join(project, STATUS_SCRIPT)) ? project : null
  }
}

function refFor(path: string): ProjectRef | null {
  const kitRoot = kitRootFor(path)
  return kitRoot === null ? null : { path, kitRoot }
}

/** Ayarlardaki yol; yoksa odaklı workspace; yoksa kit'i olan ilk workspace. */
async function resolveProject(orca: OrcaWorkerApi): Promise<ProjectRef | null> {
  const configured = await orca.settings.get('projectPath')
  if (typeof configured === 'string' && configured.trim() !== '') {
    return refFor(configured.trim())
  }
  const listed = (await call(orca)('workspace.list')) as {
    workspaces?: Array<{ path?: string; name?: string }>
  } | null
  const workspaces = (listed?.workspaces ?? []).filter(
    (workspace): workspace is { path: string; name?: string } =>
      typeof workspace.path === 'string'
  )
  const context = (await call(orca)('workspace.readContext')) as {
    displayName?: string
  } | null
  const focused = context?.displayName
  if (typeof focused === 'string') {
    const match = workspaces.find((workspace) => workspace.name === focused)
    const ref = match ? refFor(match.path) : null
    if (ref !== null) {
      return ref
    }
  }
  for (const workspace of workspaces) {
    const ref = refFor(workspace.path)
    if (ref !== null) {
      return ref
    }
  }
  return null
}

function runStatus(ref: ProjectRef): Promise<StatusJson> {
  return new Promise((resolve, reject) => {
    execFile(
      'python3',
      [join(ref.kitRoot, STATUS_SCRIPT), '--json'],
      { cwd: ref.path, timeout: STATUS_TIMEOUT_MS, maxBuffer: 4 * 1024 * 1024 },
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
  const host = call(orca)
  try {
    // Her çağrı `contributes.statusBarItems` içindeki bir öğeyi adlandırır.
    await host('statusBar.update', {
      id: 'epic',
      text: statusText(snapshot),
      tone: snapshot.ok ? 'neutral' : 'warning'
    })
    // Maliyet alanı henüz yok: status.py cost_delta null döndürüyor.
    await host('statusBar.update', { id: 'cost', text: '-' })
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
    typeof (value as { source?: unknown }).source === 'string' &&
    Array.isArray((value as { epics?: unknown }).epics) &&
    Array.isArray((value as { warnings?: unknown }).warnings) &&
    'counts' in value
  )
}

async function refresh(orca: OrcaWorkerApi, force: boolean): Promise<StatusSnapshot> {
  const warnings: string[] = []
  let project: string | null = null
  try {
    const ref = await resolveProject(orca)
    project = ref?.path ?? null
    if (ref === null) {
      const snapshot = failed(
        'demir-kit bulunamadı: Ayarlar > demir-kit > Proje yolu',
        warnings,
        null,
        'no-kit'
      )
      await publish(orca, snapshot)
      return snapshot
    }

    if (!force) {
      const cached = await fromCache(orca)
      if (cached !== null && cached.project === ref.path) {
        return cached
      }
    }

    const data = await runStatus(ref)
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
