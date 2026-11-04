// demir-kit worker: reads `status.py --json` for every workspace and feeds the panel
// and the status bar. Orca transpiles this file when it loads: no build step, and no
// writes to the project.
import { execFile } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { OrcaWorkerApi } from 'orca/worker'
import type {
  StatusCounts,
  StatusEpic,
  StatusProject,
  StatusSnapshot
} from './protocol'

/** A second call inside this window answers from storage instead of running python. */
export const CACHE_MS = 30_000
const CACHE_PREFIX = 'project:'
const STATUS_TIMEOUT_MS = 10_000
const STATUS_SCRIPT = join('delivery', 'scripts', 'status.py')
const NO_KIT = 'demir-kit yok'
const ZERO_COUNTS: StatusCounts = { epics: 0, leaves: 0, blocked: 0 }

interface StatusJson {
  stale?: boolean
  source?: string
  project?: {
    name?: string
    repo_root?: string | null
    tracker?: { repo?: string }
  }
  epics?: StatusEpic[]
  counts?: StatusCounts
  warnings?: string[]
}

interface CacheEntry {
  saved_at: number
  project: StatusProject
}

interface Workspace {
  id?: string
  name?: string
  path?: string
}

interface ProjectRef {
  id: string
  path: string
  name: string
  kitRoot: string
}

type HostCall = (method: string, params?: unknown) => Promise<unknown>

function call(orca: OrcaWorkerApi): HostCall {
  return orca.host.call as HostCall
}

function messageOf(error: unknown): string {
  return (error instanceof Error ? error.message : String(error)).slice(0, 500)
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

function refFor(workspace: Workspace): ProjectRef | null {
  if (typeof workspace.path !== 'string') return null
  const kitRoot = kitRootFor(workspace.path)
  if (kitRoot === null) return null
  return {
    id: typeof workspace.id === 'string' ? workspace.id : workspace.path,
    path: workspace.path,
    name: typeof workspace.name === 'string' ? workspace.name : '',
    kitRoot
  }
}

/**
 * Tüm workspace'ler; kit'i olanlar. Odaklı workspace, sonra ayarlardaki yol,
 * sonra kalanlar gelir. Aynı dizin bir kez sayılır.
 */
async function resolveProjects(
  orca: OrcaWorkerApi
): Promise<{ refs: ProjectRef[]; focused: string | null }> {
  const listed = (await call(orca)('workspace.list')) as {
    workspaces?: Workspace[]
  } | null
  const workspaces = (listed?.workspaces ?? []).filter(
    (workspace): workspace is Workspace => typeof workspace.path === 'string'
  )
  const context = (await call(orca)('workspace.readContext')) as {
    displayName?: string
  } | null
  const focusedName =
    typeof context?.displayName === 'string' ? context.displayName : null
  const focusedWorkspace =
    focusedName === null
      ? undefined
      : workspaces.find((workspace) => workspace.name === focusedName)

  const refs: ProjectRef[] = []
  const seen = new Set<string>()
  const push = (ref: ProjectRef | null): void => {
    if (ref === null || seen.has(ref.path)) return
    seen.add(ref.path)
    refs.push(ref)
  }

  const focusedRef = focusedWorkspace ? refFor(focusedWorkspace) : null
  push(focusedRef)

  const configured = await orca.settings.get('projectPath')
  if (typeof configured === 'string' && configured.trim() !== '') {
    const path = configured.trim()
    const match = workspaces.find((workspace) => workspace.path === path)
    push(match ? refFor(match) : refFor({ path }))
  }

  for (const workspace of workspaces) {
    push(refFor(workspace))
  }

  return { refs, focused: focusedRef?.id ?? refs[0]?.id ?? null }
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

function projectName(ref: ProjectRef, data: StatusJson): string {
  const reported = typeof data.project?.name === 'string' ? data.project.name : ''
  if (reported !== '') return reported
  if (ref.name !== '') return ref.name
  const parts = ref.path.split('/').filter(Boolean)
  return parts[parts.length - 1] ?? ref.path
}

function projectRepo(data: StatusJson): string {
  const repo = data.project?.tracker?.repo
  return typeof repo === 'string' ? repo.trim() : ''
}

function projectRepoRoot(data: StatusJson): string | null {
  const root = data.project?.repo_root
  return typeof root === 'string' && root.trim() !== '' ? root.trim() : null
}

/**
 * Aynı repo iki kez sayılmasın: önce git kökü (`repo_root`), sonra
 * `tracker.repo`, yoksa epic worktree son eki atılmış yol.
 */
function projectKey(project: StatusProject): string {
  const root = (project.repo_root ?? '').trim()
  if (root !== '') return `root:${normalizePath(root)}`
  const repo = (project.repo ?? '').trim().toLowerCase()
  if (repo !== '') return `repo:${repo}`
  return `path:${normalizePath(project.path.replace(/\/epic-\d+$/, ''))}`
}

function normalizePath(path: string): string {
  const slashed = path.replace(/\\/g, '/').replace(/\/+$/, '')
  const parts = slashed.split('/').filter((part) => part !== '' && part !== '.')
  return parts.join('/').toLowerCase()
}

/** Worktree yolu (`epic-185`) ana checkout'a göre ikinci sıradadır. */
function isWorktreePath(path: string): boolean {
  return path.replace(/\\/g, '/').includes('/epic-')
}

/** Odaklı, sonra worktree olmayan, sonra alfabetik olan aynı repo için kalır. */
function betterProject(
  current: StatusProject,
  candidate: StatusProject,
  focused: string | null
): StatusProject {
  if (current.id === focused) return current
  if (candidate.id === focused) return candidate
  const currentWorktree = isWorktreePath(current.path)
  const candidateWorktree = isWorktreePath(candidate.path)
  if (currentWorktree !== candidateWorktree) {
    return currentWorktree ? candidate : current
  }
  return current.path.localeCompare(candidate.path) <= 0 ? current : candidate
}

/** Aynı repo tek kartta: odaklı önce, sonra ada göre sıralı. */
function dedupeProjects(
  projects: StatusProject[],
  focused: string | null
): StatusProject[] {
  const byKey = new Map<string, StatusProject>()
  for (const project of projects) {
    const key = projectKey(project)
    const current = byKey.get(key)
    byKey.set(
      key,
      current === undefined ? project : betterProject(current, project, focused)
    )
  }
  return [...byKey.values()].sort((left, right) => {
    const leftRank = left.id === focused ? 0 : 1
    const rightRank = right.id === focused ? 0 : 1
    if (leftRank !== rightRank) return leftRank - rightRank
    return left.name.localeCompare(right.name)
  })
}

/** Bir projenin hatası yalnız o projede kalır: diğerleri ok:true döner. */
function failedProject(ref: ProjectRef, message: string): StatusProject {
  return {
    id: ref.id,
    path: ref.path,
    name: ref.name || ref.path,
    repo: '',
    repo_root: null,
    ok: false,
    error: message,
    epics: [],
    counts: { ...ZERO_COUNTS },
    warnings: [],
    stale: true
  }
}

function isProject(value: unknown): value is StatusProject {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as StatusProject).id === 'string' &&
    typeof (value as StatusProject).path === 'string' &&
    typeof (value as StatusProject).ok === 'boolean' &&
    Array.isArray((value as StatusProject).epics) &&
    typeof (value as StatusProject).counts === 'object' &&
    Array.isArray((value as StatusProject).warnings)
  )
}

function isCacheEntry(value: unknown): value is CacheEntry {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as CacheEntry).saved_at === 'number' &&
    isProject((value as CacheEntry).project)
  )
}

async function cachedProject(
  orca: OrcaWorkerApi,
  ref: ProjectRef
): Promise<StatusProject | null> {
  const raw = await orca.storage.get(`${CACHE_PREFIX}${ref.path}`)
  if (!isCacheEntry(raw)) return null
  if (Date.now() - raw.saved_at >= CACHE_MS) return null
  if (raw.project.path !== ref.path) return null
  return raw.project
}

async function projectSnapshot(
  orca: OrcaWorkerApi,
  ref: ProjectRef,
  force: boolean
): Promise<StatusProject> {
  if (!force) {
    try {
      const cached = await cachedProject(orca, ref)
      if (cached !== null) return cached
    } catch (error) {
      // Önbellek okunamazsa yalnız bu proje canlı hesaplamaya düşer.
      orca.log(`demir-kit: önbellek okunamadı (${ref.path}): ${String(error)}`)
    }
  }
  try {
    const data = await runStatus(ref)
    const project: StatusProject = {
      id: ref.id,
      path: ref.path,
      name: projectName(ref, data),
      repo: projectRepo(data),
      repo_root: projectRepoRoot(data),
      ok: true,
      epics: Array.isArray(data.epics) ? data.epics : [],
      counts: data.counts ?? { ...ZERO_COUNTS },
      warnings: Array.isArray(data.warnings) ? data.warnings : [],
      stale: data.stale === true
    }
    await orca.storage.set(`${CACHE_PREFIX}${ref.path}`, {
      saved_at: Date.now(),
      project
    })
    return project
  } catch (error) {
    return failedProject(ref, messageOf(error))
  }
}

/** Durum çubuğu odaklı projeyi anlatır; yoksa sağlıklı proje sayısını. */
export function statusText(snapshot: StatusSnapshot): string {
  const focused = snapshot.projects.find((item) => item.id === snapshot.focused)
  const epic = focused?.ok === true ? focused.epics?.[0] : undefined
  if (epic !== undefined && typeof epic.number === 'number') {
    const done = epic.checkpoints?.done ?? 0
    const total = epic.checkpoints?.total ?? 0
    const gate = epic.gate ?? 'yok'
    return `EP-${epic.number} · CP ${done}/${total} · gate ${gate}`.slice(0, 64)
  }
  const healthy = snapshot.projects.filter((item) => item.ok).length
  return healthy > 0 ? `${healthy} proje` : NO_KIT
}

function failedSnapshot(message: string, warnings: string[]): StatusSnapshot {
  return {
    ok: false,
    code: 'no-kit',
    generated_at: new Date().toISOString(),
    focused: null,
    projects: [],
    warnings: [...warnings, message],
    error: message
  }
}

async function publish(
  orca: OrcaWorkerApi,
  snapshot: StatusSnapshot
): Promise<void> {
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

async function refresh(
  orca: OrcaWorkerApi,
  force: boolean
): Promise<StatusSnapshot> {
  const warnings: string[] = []
  let refs: ProjectRef[] = []
  let focused: string | null = null
  try {
    const resolved = await resolveProjects(orca)
    refs = resolved.refs
    focused = resolved.focused
  } catch (error) {
    const snapshot = failedSnapshot(messageOf(error), warnings)
    await publish(orca, snapshot)
    return snapshot
  }

  if (refs.length === 0) {
    const snapshot = failedSnapshot(
      'demir-kit bulunamadı: Ayarlar > demir-kit > Proje yolu',
      warnings
    )
    await publish(orca, snapshot)
    return snapshot
  }

  // Promise.all: bir projenin hatası diğerlerini düşürmez, kendi alanında kalır.
  const snapshots = await Promise.all(
    refs.map((ref) => projectSnapshot(orca, ref, force))
  )
  // Aynı repo (ana checkout + epic worktree) tek kartta; odaklı önce gelir.
  const projects = dedupeProjects(snapshots, focused)
  const focusedId =
    focused !== null && projects.some((project) => project.id === focused)
      ? focused
      : (projects[0]?.id ?? null)
  const snapshot: StatusSnapshot = {
    ok: projects.some((project) => project.ok),
    generated_at: new Date().toISOString(),
    focused: focusedId,
    projects,
    warnings
  }
  await publish(orca, snapshot)
  return snapshot
}

export default async function activate(orca: OrcaWorkerApi): Promise<void> {
  orca.panels.handle('status.snapshot', async () => refresh(orca, false))

  // Panel yalnız ister; `workspace.open` yetkisi manifestteki `workspace:write`.
  orca.panels.handle('workspace.open', async (input) => {
    const raw =
      typeof input === 'object' && input !== null
        ? (input as { id?: unknown }).id
        : undefined
    if (typeof raw !== 'string' || raw === '') {
      return { ok: false, error: 'workspace id yok' }
    }
    try {
      await call(orca)('workspace.open', { workspaceId: raw })
      return { ok: true }
    } catch (error) {
      return { ok: false, error: messageOf(error) }
    }
  })

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
