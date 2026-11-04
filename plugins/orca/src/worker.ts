// demir-kit worker: reads `status.py --json` for every workspace and feeds the panel
// and the status bar. Orca transpiles this file when it loads: no build step, and no
// writes to the project.
import { execFile } from 'node:child_process'
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync
} from 'node:fs'
import * as os from 'node:os'
import { join } from 'node:path'
import type { OrcaWorkerApi } from 'orca/worker'
import type {
  ActionReply,
  AgentState,
  StatusAgent,
  StatusCheckpoint,
  StatusCheckpointSummary,
  StatusCounts,
  StatusEpic,
  StatusLive,
  StatusProject,
  StatusSnapshot
} from './protocol'

/** A second call inside this window answers from storage instead of running python. */
export const CACHE_MS = 30_000
const CACHE_PREFIX = 'project:'
const STATUS_TIMEOUT_MS = 10_000
/** Claim ve geçiş `gh` çağırır: durum okumasından daha uzun sürebilir. */
const ACTION_TIMEOUT_MS = 60_000
const TAIL_LINES = 12
const STATUS_SCRIPT = join('delivery', 'scripts', 'status.py')
const NO_KIT = 'demir-kit yok'
const ZERO_COUNTS: StatusCounts = { epics: 0, leaves: 0, blocked: 0 }
const AGENT_STATES: readonly AgentState[] = [
  'working',
  'blocked',
  'waiting',
  'idle',
  'done'
]

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
    agents: [],
    live: zeroLive(),
    warnings: [],
    stale: true
  }
}

function zeroLive(): StatusLive {
  return { working: 0, blocked: 0, waiting: 0, idle: 0, done: 0 }
}

function liveOf(agents: StatusAgent[]): StatusLive {
  const live = zeroLive()
  for (const agent of agents) {
    live[agent.state] += 1
  }
  return live
}

interface AgentListing {
  agents: StatusAgent[]
  live: StatusLive
  warning: string | null
}

/**
 * `agents.list` yalnız odaklı workspace'in ajanlarını verir; hata projeyi
 * düşürmez: `agents: []` ve bir uyarı kalır.
 */
async function readAgents(orca: OrcaWorkerApi): Promise<AgentListing> {
  try {
    const listed = (await call(orca)('agents.list')) as {
      agents?: Array<{
        terminalId?: string | null
        title?: string | null
        state?: string
      }>
    } | null
    const agents: StatusAgent[] = (listed?.agents ?? [])
      .filter(
        (item): item is { terminalId?: string | null; title?: string | null; state: AgentState } =>
          typeof item?.state === 'string' &&
          AGENT_STATES.includes(item.state as AgentState)
      )
      .map((item) => ({
        terminalId: typeof item.terminalId === 'string' ? item.terminalId : null,
        title: typeof item.title === 'string' ? item.title : null,
        state: item.state
      }))
    return { agents, live: liveOf(agents), warning: null }
  } catch (error) {
    return {
      agents: [],
      live: zeroLive(),
      warning: `ajan durumu okunamadı: ${messageOf(error)}`
    }
  }
}

/** Yeni dizi ya da eski `{done,total}`: ikisi de geçerli, panel çökmez. */
function isCheckpoints(value: StatusCheckpoint[] | StatusCheckpointSummary | undefined): boolean {
  if (value === undefined || Array.isArray(value)) return true
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as StatusCheckpointSummary).done === 'number' &&
    typeof (value as StatusCheckpointSummary).total === 'number'
  )
}

function isEpic(value: unknown): boolean {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as StatusEpic).number === 'number' &&
    isCheckpoints((value as StatusEpic).checkpoints)
  )
}

function isProject(value: unknown): value is StatusProject {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as StatusProject).id === 'string' &&
    typeof (value as StatusProject).path === 'string' &&
    typeof (value as StatusProject).ok === 'boolean' &&
    Array.isArray((value as StatusProject).epics) &&
    (value as StatusProject).epics.every(isEpic) &&
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
    // Eski `{done,total}` şekli dizi değildir: çökme yok, CP 0/0 görünür.
    const checkpoints = Array.isArray(epic.checkpoints) ? epic.checkpoints : []
    const done = checkpoints.filter((checkpoint) => checkpoint.done === true).length
    const total = checkpoints.length
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

/** Son yayımlanan anlık görüntü: ajan olayı yalnız tek kartı tazeler. */
let lastSnapshot: StatusSnapshot | null = null
/** Ajanların gerçekten okunduğu odaklı workspace; kit taşımıyorsa null. */
let lastAgentWorkspace: string | null = null

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
    lastSnapshot = snapshot
    lastAgentWorkspace = null
    await publish(orca, snapshot)
    return snapshot
  }

  if (refs.length === 0) {
    const snapshot = failedSnapshot(
      'demir-kit bulunamadı: Ayarlar > demir-kit > Proje yolu',
      warnings
    )
    lastSnapshot = snapshot
    lastAgentWorkspace = null
    await publish(orca, snapshot)
    return snapshot
  }

  // Promise.all: bir projenin hatası diğerlerini düşürmez, kendi alanında kalır.
  const snapshots = await Promise.all(
    refs.map((ref) => projectSnapshot(orca, ref, force))
  )
  // Aynı repo (ana checkout + epic worktree) tek kartta; odaklı önce gelir.
  const deduped = dedupeProjects(snapshots, focused)
  // Odaklı workspace kit taşımıyorsa hiçbir karta ajan yazılmaz.
  const agentTarget =
    focused !== null && deduped.some((project) => project.id === focused)
      ? focused
      : null
  const focusedId = agentTarget ?? deduped[0]?.id ?? null
  // Canlı ajanlar yalnız odaklı workspace'ten gelir; diğer kartlar sıfır taşır.
  let agentListing: AgentListing = {
    agents: [],
    live: zeroLive(),
    warning: null
  }
  if (agentTarget !== null) {
    agentListing = await readAgents(orca)
    if (agentListing.warning !== null) warnings.push(agentListing.warning)
  }
  const projects = deduped.map((project) =>
    project.id === agentTarget
      ? { ...project, agents: agentListing.agents, live: agentListing.live }
      : { ...project, agents: [], live: zeroLive() }
  )
  const snapshot: StatusSnapshot = {
    ok: projects.some((project) => project.ok),
    generated_at: new Date().toISOString(),
    focused: focusedId,
    projects,
    warnings
  }
  lastSnapshot = snapshot
  lastAgentWorkspace = agentTarget
  await publish(orca, snapshot)
  return snapshot
}

/** Olayın `workspaceId` alanı; yoksa null (olay workspace'e bağlanamadı). */
function workspaceIdOf(event: unknown): string | null {
  if (typeof event !== 'object' || event === null) return null
  const id = (event as { workspaceId?: unknown }).workspaceId
  return typeof id === 'string' && id !== '' ? id : null
}

/**
 * `agent.status.changed`: olayın workspace'i odaklıysa yalnız o kartın ajanları
 * tazelenir. Odaklı olmayan ya da kit'i olmayan workspace hiçbir karta yazmaz.
 */
async function refreshAgents(
  orca: OrcaWorkerApi,
  workspaceId: string | null
): Promise<void> {
  const current = lastSnapshot
  const target = workspaceId ?? lastAgentWorkspace
  if (current === null || target === null) {
    await refresh(orca, false)
    return
  }
  // Yalnız ajanları okunabilen (odaklı) workspace'in kartı güncellenir.
  if (target !== lastAgentWorkspace) return
  if (!current.projects.some((project) => project.id === target)) return
  const listing = await readAgents(orca)
  if (listing.warning !== null) orca.log(`demir-kit: ${listing.warning}`)
  const snapshot: StatusSnapshot = {
    ...current,
    projects: current.projects.map((project) =>
      project.id === target
        ? { ...project, agents: listing.agents, live: listing.live }
        : project
    )
  }
  lastSnapshot = snapshot
  await publish(orca, snapshot)
}

interface RunResult {
  code: number
  stdout: string
  stderr: string
}

/** Komut hatası fırlatmaz: çıkış kodu ve çıktı aksiyon yanıtına gider. */
function runCommand(
  file: string,
  args: string[],
  cwd: string
): Promise<RunResult> {
  return new Promise((resolve) => {
    execFile(
      file,
      args,
      { cwd, timeout: ACTION_TIMEOUT_MS, maxBuffer: 1024 * 1024 },
      (error, stdout, stderr) => {
        let code = 0
        if (error !== null) {
          const raw = (error as { code?: unknown }).code
          code = typeof raw === 'number' ? raw : 1
        }
        resolve({
          code,
          stdout: String(stdout ?? ''),
          stderr: String(stderr ?? '')
        })
      }
    )
  })
}

/** Son birkaç satır: panel uzun `gh` çıktısını taşımaz. */
function tailOf(result: RunResult): string {
  const text = `${result.stdout}\n${result.stderr}`.trim()
  if (text === '') return ''
  const lines = text.split('\n').filter((line) => line.trim() !== '')
  return lines.slice(-TAIL_LINES).join('\n').slice(-2000)
}

function actionReply(
  ok: boolean,
  message: string,
  exitCode: number,
  result?: RunResult,
  url = '',
  warning = ''
): ActionReply {
  const reply: ActionReply = {
    ok,
    message,
    exitCode,
    tail: result === undefined ? '' : tailOf(result),
    url
  }
  if (warning !== '') reply.warning = warning
  return reply
}

/** Panelin gönderdiği issue numarası; geçersizse null. */
function issueOf(input: unknown): number | null {
  const raw =
    typeof input === 'object' && input !== null
      ? (input as { issue?: unknown }).issue
      : undefined
  const issue = typeof raw === 'number' ? raw : Number(raw)
  return Number.isInteger(issue) && issue > 0 ? issue : null
}

/** Panelin gönderdiği proje yolu; boş ya da eksikse null. */
function projectPathOf(input: unknown): string | null {
  const raw =
    typeof input === 'object' && input !== null
      ? (input as { projectPath?: unknown }).projectPath
      : undefined
  return typeof raw === 'string' && raw.trim() !== '' ? raw.trim() : null
}

/**
 * Aksiyonun projesi: son anlık görüntüdeki kart, panelin verdiği `path` ile
 * eşleşir. Bulunamazsa null döner, başka projede çalışılmaz.
 */
function projectAt(path: string): StatusProject | null {
  const project = lastSnapshot?.projects.find((item) => item.path === path)
  return project === undefined ? null : project
}

/** Proje kartındaki claim hedefi: ilk `agent-approved` leaf; yoksa null. */
function nextClaimable(project: StatusProject): number | null {
  for (const epic of project.epics) {
    for (const leaf of epic.leaves ?? []) {
      if (leaf.state === 'agent-approved') return leaf.number
    }
  }
  return null
}

/** Issue bağlantısı `tracker.repo`'dan; repo yoksa boş kalır. */
function issueUrl(project: StatusProject, issue: number): string {
  const repo = (project.repo ?? '')
    .trim()
    .replace(/^https?:\/\/github\.com\//, '')
    .replace(/\.git$/, '')
  return repo === '' ? '' : `https://github.com/${repo}/issues/${issue}`
}

/** `approvals.py` biçimi: ```yaml demir-kit-accept ... ``` bloğu. */
function decisionBody(
  issue: number,
  decision: 'accepted' | 'rejected',
  login: string
): string {
  const decisionLine =
    decision === 'accepted' ? 'decision: accepted' : 'decision: rejected'
  return [
    '```yaml demir-kit-accept',
    `epic: ${issue}`,
    decisionLine,
    `by: ${login}`,
    '```',
    ''
  ].join('\n')
}

/** Geçici dizin `os.tmpdir()` altında, 0700; dosya 0600; iş bitince dizin silinir. */
interface TempBody {
  dir: string
  path: string
}

function writeTempBody(issue: number, body: string): TempBody {
  const dir = mkdtempSync(join(os.tmpdir(), 'demir-kit-'))
  const path = join(dir, `accept-${issue}.md`)
  writeFileSync(path, body, { encoding: 'utf8', mode: 0o600 })
  return { dir, path }
}

function removeTempDir(dir: string): void {
  try {
    rmSync(dir, { recursive: true, force: true })
  } catch {
    // Geçici dizin zaten silinmişse sorun değil.
  }
}

/** `gh issue comment` çıktısındaki `#issuecomment-<id>` bağlantısı. */
function commentIdOf(stdout: string): string {
  const match = stdout.match(/#issuecomment-(\d+)/)
  return match === null ? '' : match[1]
}

/** Başarısız kabulde az önce yazılan yorumu geri alır; en iyi çaba. */
async function deleteComment(cwd: string, stdout: string): Promise<boolean> {
  const id = commentIdOf(stdout)
  const match = stdout.match(
    /github\.com\/([^/\s]+\/[^/\s]+)\/issues\/\d+#issuecomment-\d+/
  )
  if (id === '' || match === null) return false
  const result = await runCommand(
    'gh',
    ['api', '-X', 'DELETE', `repos/${match[1]}/issues/comments/${id}`],
    cwd
  )
  return result.code === 0
}

type GateKind = 'decision' | 'claim'

interface GateResult {
  ok: boolean
  reason: string
  result: RunResult
}

/**
 * Sunucu tarafı kapı: yorum yazmadan önce etiketler `gh issue view` ile
 * doğrulanır. Karar `human-qa`, claim `agent-approved` ve başlamamış olmak ister.
 */
async function checkGate(
  kind: GateKind,
  issue: number,
  cwd: string
): Promise<GateResult> {
  const result = await runCommand(
    'gh',
    ['issue', 'view', String(issue), '--json', 'labels'],
    cwd
  )
  if (result.code !== 0) {
    return { ok: false, reason: 'etiketler okunamadı', result }
  }
  let labels: string[] = []
  try {
    const parsed = JSON.parse(result.stdout) as {
      labels?: Array<{ name?: unknown }>
    }
    labels = (parsed.labels ?? [])
      .map((label) => (typeof label?.name === 'string' ? label.name : ''))
      .filter((name) => name !== '')
  } catch {
    return { ok: false, reason: 'etiketler okunamadı', result }
  }
  const has = (name: string): boolean => labels.includes(name)
  if (kind === 'decision' && !has('human-qa')) {
    return { ok: false, reason: 'human-qa etiketi yok', result }
  }
  if (kind === 'claim' && !has('agent-approved')) {
    return { ok: false, reason: 'agent-approved etiketi yok', result }
  }
  if (kind === 'claim' && (has('executing') || has('leaf-done'))) {
    return { ok: false, reason: 'leaf zaten başlamış ya da bitmiş', result }
  }
  return { ok: true, reason: '', result }
}

/** Aksiyondan sonra önbelleği atlayıp paneli tazele; hata aksiyonu düşürmez. */
async function refreshAfterAction(orca: OrcaWorkerApi): Promise<void> {
  try {
    await refresh(orca, true)
  } catch (error) {
    orca.log(`demir-kit: aksiyon sonrası tazeleme başarısız: ${messageOf(error)}`)
  }
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

  // İnsan kararı: önce etiket kapısı, sonra yorum; kabulde `transition.sh`.
  orca.panels.handle('epic.decision', async (input) => {
    try {
      const path = projectPathOf(input)
      if (path === null) {
        return actionReply(false, 'proje yolu yok', 1)
      }
      const issue = issueOf(input)
      if (issue === null) {
        return actionReply(false, 'issue yok', 1)
      }
      const rawDecision =
        typeof input === 'object' && input !== null
          ? (input as { decision?: unknown }).decision
          : undefined
      if (rawDecision !== 'accepted' && rawDecision !== 'rejected') {
        return actionReply(false, 'karar yok', 1)
      }
      const decision: 'accepted' | 'rejected' = rawDecision
      const project = projectAt(path)
      if (project === null) {
        return actionReply(false, 'proje bulunamadı', 1)
      }
      const kitRoot = kitRootFor(project.path)
      if (kitRoot === null) {
        return actionReply(false, NO_KIT, 1)
      }
      const url = issueUrl(project, issue)
      // Kapı: karar yalnız `human-qa` etiketli issue'ya yazılır.
      const gate = await checkGate('decision', issue, project.path)
      if (!gate.ok) {
        return actionReply(
          false,
          gate.reason,
          gate.result.code === 0 ? 1 : gate.result.code,
          gate.result,
          url
        )
      }
      const user = await runCommand(
        'gh',
        ['api', 'user', '--jq', '.login'],
        project.path
      )
      const login = user.stdout.trim()
      if (user.code !== 0 || login === '') {
        return actionReply(
          false,
          'GitHub kullanıcısı okunamadı',
          user.code,
          user,
          url
        )
      }

      const temp = writeTempBody(issue, decisionBody(issue, decision, login))
      let comment: RunResult
      try {
        comment = await runCommand(
          'gh',
          ['issue', 'comment', String(issue), '--body-file', temp.path],
          project.path
        )
      } finally {
        removeTempDir(temp.dir)
      }
      if (comment.code !== 0) {
        return actionReply(false, 'yorum yazılamadı', comment.code, comment, url)
      }

      // Red yalnız yorum yazar; durum geçişi çağrılmaz (AC-4).
      if (decision === 'rejected') {
        await refreshAfterAction(orca)
        return actionReply(true, 'epic reddedildi', 0, comment, url)
      }

      const script = join(kitRoot, 'delivery', 'scripts', 'transition.sh')
      const transition = await runCommand(
        'bash',
        [
          script,
          '--issue',
          String(issue),
          '--to',
          'epic-done',
          '--accept',
          login
        ],
        project.path
      )
      if (transition.code !== 0) {
        // Geçiş düşerse az önce yazılan yorum GitHub'da artık kalmasın.
        const removed = await deleteComment(project.path, comment.stdout)
        await refreshAfterAction(orca)
        const message = removed
          ? 'geçiş başarısız; yorum geri alındı'
          : 'geçiş başarısız; yorum kaldı'
        return actionReply(false, message, transition.code, transition, url)
      }
      // Geçiş korunur: issue kapanışı ayrı adımdır, hatası geçişi geri almaz.
      const closed = await runCommand(
        'gh',
        ['issue', 'close', String(issue), '--reason=completed'],
        project.path
      )
      await refreshAfterAction(orca)
      if (closed.code !== 0) {
        const reason = tailOf(closed).split('\n')[0] || 'gh hata verdi'
        return actionReply(
          true,
          'epic kabul edildi',
          0,
          transition,
          url,
          `issue kapatılamadı: ${reason}`
        )
      }
      return actionReply(true, 'epic kabul edildi', 0, transition, url)
    } catch (error) {
      return actionReply(false, messageOf(error), 1)
    }
  })

  // Leaf claim: proje kartından; hedef leaf sunucuda etiketle doğrulanır.
  orca.panels.handle('leaf.claim', async (input) => {
    try {
      const path = projectPathOf(input)
      if (path === null) {
        return actionReply(false, 'proje yolu yok', 1)
      }
      const project = projectAt(path)
      if (project === null) {
        return actionReply(false, 'proje bulunamadı', 1)
      }
      const kitRoot = kitRootFor(project.path)
      if (kitRoot === null) {
        return actionReply(false, NO_KIT, 1)
      }
      const leaf = nextClaimable(project)
      if (leaf === null) {
        return actionReply(false, 'sıradaki leaf yok', 1)
      }
      const url = issueUrl(project, leaf)
      // Kapı: claim yalnız `agent-approved` ve başlamamış leaf'e yazılır.
      const gate = await checkGate('claim', leaf, project.path)
      if (!gate.ok) {
        return actionReply(
          false,
          gate.reason,
          gate.result.code === 0 ? 1 : gate.result.code,
          gate.result,
          url
        )
      }
      const script = join(kitRoot, 'delivery', 'scripts', 'next-leaf.sh')
      const claim = await runCommand('bash', [script, '--claim'], project.path)
      await refreshAfterAction(orca)
      return actionReply(
        claim.code === 0,
        claim.code === 0 ? 'claim alındı' : 'claim başarısız',
        claim.code,
        claim,
        url
      )
    } catch (error) {
      return actionReply(false, messageOf(error), 1)
    }
  })

  orca.commands.register('demir-kit.refresh', () => {
    void refresh(orca, true)
  })

  orca.events.on('workspace.changed', () => {
    void refresh(orca, true)
  })

  // Ajan durumu değişince yalnız olayın workspace'inin kartı tazelenir.
  orca.events.on('agent.status.changed', (event) => {
    void refreshAgents(orca, workspaceIdOf(event))
  })

  orca.settings.onDidChange(() => {
    void refresh(orca, true)
  })

  await refresh(orca, true)
}
