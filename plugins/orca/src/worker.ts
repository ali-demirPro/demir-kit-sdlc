// demir-kit worker: reads `status.py --json` for every workspace and feeds the panel
// and the status bar. Orca transpiles this file when it loads: no build step, and no
// writes to the project.
import { execFile } from 'node:child_process'
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  rmSync,
  writeFileSync
} from 'node:fs'
import * as os from 'node:os'
import { join } from 'node:path'
import type { OrcaWorkerApi } from 'orca/worker'
import type {
  ActionReply,
  AgentState,
  FocusSource,
  StatusActive,
  StatusAgent,
  StatusCheckpoint,
  StatusCheckpointSummary,
  StatusCounts,
  StatusEpic,
  StatusLive,
  StatusProject,
  StatusSnapshot
} from './protocol'
import { fleetPulse } from './pulse'

/**
 * İkinci çağrı bu pencerede python yerine depodan yanıtlanır. Pencere 120 sn:
 * panel 60 sn'de bir tazeler, saatte en fazla 30 status.py çağrısı düşer.
 */
export const CACHE_MS = 120_000
const CACHE_PREFIX = 'project:'
const STATUS_TIMEOUT_MS = 10_000
/** Claim ve geçiş `gh` çağırır: durum okumasından daha uzun sürebilir. */
const ACTION_TIMEOUT_MS = 60_000
const TAIL_LINES = 12
const STATUS_SCRIPT = join('delivery', 'scripts', 'status.py')
/** `status.py` her zaman bu argümanlarla koşar; `--cache-ttl 120`: dosya önbelleği 120 sn taze kalır. */
export const STATUS_ARGS = ['--json', '--cache-ttl', '120'] as const
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
  /** status.py'nin ürettiği an (`from_cache` eskisi kalır); 0-dışı çıkışta da taşınır. */
  generated_at?: string
  project?: {
    name?: string
    repo_root?: string | null
    tracker?: { repo?: string }
  }
  epics?: StatusEpic[]
  counts?: StatusCounts
  warnings?: string[]
  pulse?: StatusProject['pulse']
}

interface CacheEntry {
  saved_at: number
  project: StatusProject
}

export interface Workspace {
  id?: string
  name?: string
  path?: string
  /** Host kimliği; bu makine `local` döndürür, kaydetmeyen hostta null. */
  hostId?: string | null
}

/** Odak sinyali: olaydan gelen id/path; ad yalnız tek eşleşirse kullanılır. */
export interface FocusSignal {
  id?: string
  path?: string
  name?: string
}

/** Son `workspace.changed` gövdesi: odak için ana sinyal. */
let focusSignal: FocusSignal | null = null

/** Kalıcı terminal haritası: en fazla 200 kayıt, 30 gün TTL, LRU temizliği. */
const TERMINAL_MAP_LIMIT = 200
const TERMINAL_TTL_MS = 30 * 24 * 60 * 60 * 1000
const TERMINAL_STORE_KEY = 'agents.terminals.v1'
const TERMINAL_STORE_VERSION = 1
const TERMINAL_SAVE_MS = 1000

/** `workspaceId` biçiminden çıkarılan kimlik: id ya da gerçek yol. */
export interface WorkspaceHint {
  id?: string
  path?: string
}

export interface TerminalEntry {
  hint: WorkspaceHint
  lastSeenAt: number
}

/** Terminal eşlemesinden çıkan odak; `conflict` sinyallerin çeliştiğini söyler. */
export interface TerminalFocus {
  workspace: Workspace | null
  conflict: boolean
}

/** Odak çözümünün kaynağı; `pickFocused` davranışını değiştirmez. */
export interface FocusMatch {
  workspace: Workspace | null
  source: FocusSource
}

const terminalWorkspaces = new Map<string, TerminalEntry>()
let terminalMapLoaded = false
let terminalMapDirty = false
let terminalSaveTimer: ReturnType<typeof setTimeout> | null = null

/** Aktif ajan ipuçları: aynı anda tek workspace varsa odak için kullanılır. */
const AGENT_HINT_TTL_MS = 10 * 60 * 1000
interface ActiveAgentHint {
  hint: WorkspaceHint
  at: number
  /** `agents.list` ile birebir eşleşen durum başlangıcı; yoksa undefined. */
  stateStartedAt?: number
}
const activeAgentHints = new Map<string, ActiveAgentHint>()

function textOf(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const text = value.trim()
  return text === '' ? null : text
}

/** `workspaceId` `<repo>::/yol`, `identity:...` ya da çıplak yol olabilir. */
export function hintsFromWorkspaceId(value: unknown): WorkspaceHint | null {
  const text = textOf(value)
  if (text === null) return null
  if (text.startsWith('identity:')) return { id: text }
  const cut = text.indexOf('::')
  if (cut >= 0) {
    const path = text.slice(cut + 2).trim()
    return path === '' ? null : { path }
  }
  if (/^[a-zA-Z]:[\\/]/.test(text) || text.startsWith('/')) return { path: text }
  if (text.startsWith('~/')) return { path: join(os.homedir(), text.slice(2)) }
  return { id: text }
}

/** Kayıtlı bir ipucunu listedeki tek workspace'e bağlar; belirsizse null. */
export function matchWorkspaceHint(
  workspaces: readonly Workspace[],
  hint: WorkspaceHint | null
): Workspace | null {
  if (hint === null) return null
  const id = textOf(hint.id)
  if (id !== null) {
    const byId = workspaces.find((workspace) => workspace.id === id)
    if (byId !== undefined) return byId
    // Eski kayıt iç id taşıyorsa (`<repo>::/yol`) yol kısmını dene.
    const cut = id.indexOf('::')
    if (cut >= 0) {
      const byPath = matchWorkspacePath(workspaces, id.slice(cut + 2))
      if (byPath !== null) return byPath
    }
  }
  const path = textOf(hint.path)
  return path === null ? null : matchWorkspacePath(workspaces, path)
}

/**
 * Yeni eşleme ekler; `lastSeenAt` sıralamasıyla en eski kayıt düşer.
 * Yeniden görülen terminal silinip sona yazılır: sıcak terminal ilk düşmez.
 */
export function rememberTerminal(
  terminalId: string,
  hint: WorkspaceHint,
  now = Date.now()
): void {
  terminalWorkspaces.delete(terminalId)
  if (terminalWorkspaces.size >= TERMINAL_MAP_LIMIT) {
    let oldestId: string | null = null
    let oldestAt = Number.POSITIVE_INFINITY
    for (const [id, entry] of terminalWorkspaces) {
      if (entry.lastSeenAt < oldestAt) {
        oldestAt = entry.lastSeenAt
        oldestId = id
      }
    }
    if (oldestId !== null) terminalWorkspaces.delete(oldestId)
  }
  terminalWorkspaces.set(terminalId, { hint, lastSeenAt: now })
  terminalMapDirty = true
}

/**
 * `agent.status.changed` gövdesinden workspace ipucu: `workspaceId`,
 * `worktreeId` ya da bağlam id'si. Orca 1.4.248 satırı `worktreeId` taşır.
 */
export function agentWorkspaceHint(event: unknown): WorkspaceHint | null {
  if (typeof event !== 'object' || event === null) return null
  const payload = event as {
    workspaceId?: unknown
    worktreeId?: unknown
    context?: { workspaceId?: unknown; id?: unknown }
  }
  const raw =
    textOf(payload.workspaceId) ??
    textOf(payload.worktreeId) ??
    textOf(payload.context?.workspaceId) ??
    textOf(payload.context?.id)
  return hintsFromWorkspaceId(raw)
}

/** Olayın ajan durumu; bilinmeyen/eksik değer null. */
export function agentStateOf(event: unknown): AgentState | null {
  if (typeof event !== 'object' || event === null) return null
  const state = (event as { state?: unknown }).state
  return typeof state === 'string' && AGENT_STATES.includes(state as AgentState)
    ? (state as AgentState)
    : null
}

/**
 * `agent.status.changed` gövdesinden terminal/workspace eşlemesini öğrenir.
 * `workspaceId` ya da `terminalId` yoksa hiçbir şey saklanmaz.
 */
export function learnAgentTerminal(event: unknown): boolean {
  const hint = agentWorkspaceHint(event)
  if (hint === null) return false
  const terminalId =
    typeof event === 'object' && event !== null
      ? textOf((event as { terminalId?: unknown }).terminalId)
      : null
  if (terminalId !== null) rememberTerminal(terminalId, hint)
  return true
}

/** Aktif ajanın workspace ipucunu saklar; `idle`/`done` ipucu düşürür. */
export function rememberAgentHint(
  hint: WorkspaceHint | null,
  state: AgentState | null,
  now = Date.now(),
  stateStartedAt?: number
): boolean {
  if (hint === null) return false
  const key = hint.id ?? hint.path ?? ''
  if (key === '') return false
  if (state === null) return false
  if (state === 'idle' || state === 'done') {
    return activeAgentHints.delete(key)
  }
  activeAgentHints.set(key, {
    hint,
    at: now,
    ...(typeof stateStartedAt === 'number' && Number.isFinite(stateStartedAt)
      ? { stateStartedAt }
      : {})
  })
  return true
}

/**
 * Odaklı ajanlarla aktif workspace ipuçlarını eşler. Önce `stateStartedAt`
 * birebir eşleşmesi denenir; yoksa tüm ipuçları tek workspace'e çıkıyorsa
 * kullanılır. İki farklı workspace varsa sinyal çelişir: null (tahmin yok).
 */
export function activeAgentFocus(
  workspaces: readonly Workspace[],
  focusedAgents: readonly StatusAgent[] = [],
  now = Date.now()
): Workspace | null {
  for (const [key, entry] of activeAgentHints) {
    if (now - entry.at > AGENT_HINT_TTL_MS) activeAgentHints.delete(key)
  }
  if (activeAgentHints.size === 0) return null
  const starts = new Set(
    focusedAgents
      .map((agent) => agent.stateStartedAt)
      .filter((value): value is number => typeof value === 'number')
  )
  if (starts.size > 0) {
    const matched = new Map<string, Workspace>()
    for (const entry of activeAgentHints.values()) {
      if (entry.stateStartedAt === undefined || !starts.has(entry.stateStartedAt)) {
        continue
      }
      const workspace = matchWorkspaceHint(workspaces, entry.hint)
      if (workspace !== null) {
        matched.set(workspace.id ?? workspace.path ?? '', workspace)
      }
    }
    if (matched.size === 1) return [...matched.values()][0] ?? null
    if (matched.size > 1) return null
  }
  // Durum başlangıcı eşleşmese de tüm ipuçları tek workspace'e çıkıyorsa güvenli.
  const resolved = new Map<string, Workspace>()
  for (const entry of activeAgentHints.values()) {
    const workspace = matchWorkspaceHint(workspaces, entry.hint)
    if (workspace !== null) {
      resolved.set(workspace.id ?? workspace.path ?? '', workspace)
    }
  }
  return resolved.size === 1 ? [...resolved.values()][0] ?? null : null
}

export function resetAgentHints(): void {
  activeAgentHints.clear()
}

/** Görülen terminallerin zamanını tazeler; haritada olmayan terminal eklenmez. */
export function touchTerminals(
  terminals: readonly string[],
  now = Date.now()
): boolean {
  let changed = false
  for (const terminalId of terminals) {
    const entry = terminalWorkspaces.get(terminalId)
    if (entry === undefined) continue
    entry.lastSeenAt = now
    changed = true
  }
  if (changed) terminalMapDirty = true
  return changed
}

/** Terminal listesinden tek bir workspace çıkarır; iki farklı sonuç çelişkidir. */
export function terminalFocus(
  workspaces: readonly Workspace[],
  terminals: readonly string[],
  maps: ReadonlyMap<string, TerminalEntry> = terminalWorkspaces
): TerminalFocus {
  const found = new Map<string, Workspace>()
  for (const terminalId of terminals) {
    const entry = maps.get(terminalId)
    if (entry === undefined) continue
    const workspace = matchWorkspaceHint(workspaces, entry.hint)
    if (workspace === null) continue
    const key = workspace.id ?? workspace.path ?? ''
    if (key !== '') found.set(key, workspace)
  }
  if (found.size > 1) return { workspace: null, conflict: true }
  return {
    workspace: found.size === 1 ? [...found.values()][0] ?? null : null,
    conflict: false
  }
}

/** Testler için haritayı sıfırlar; üretimde yalnız worker yeniden yüklenirken. */
export function resetTerminalMap(): void {
  terminalWorkspaces.clear()
  terminalMapLoaded = false
  terminalMapDirty = false
  if (terminalSaveTimer !== null) {
    clearTimeout(terminalSaveTimer)
    terminalSaveTimer = null
  }
}

export function terminalMapSize(): number {
  return terminalWorkspaces.size
}

/** Kayıtlı belgeyi doğrular; bozuk ya da sürümü eski belge boş harita olur. */
export function parseTerminalMap(raw: unknown): Map<string, TerminalEntry> {
  const map = new Map<string, TerminalEntry>()
  if (typeof raw !== 'object' || raw === null) return map
  const doc = raw as { version?: unknown; entries?: unknown }
  if (doc.version !== TERMINAL_STORE_VERSION || !Array.isArray(doc.entries)) {
    return map
  }
  for (const item of doc.entries) {
    if (!Array.isArray(item) || item.length < 2) continue
    const terminalId = textOf(item[0])
    const entry = item[1]
    if (terminalId === null || typeof entry !== 'object' || entry === null) {
      continue
    }
    const stored = entry as { hint?: unknown; lastSeenAt?: unknown }
    const hint = parseHint(stored.hint)
    if (hint === null) continue
    const lastSeenAt =
      typeof stored.lastSeenAt === 'number' && Number.isFinite(stored.lastSeenAt)
        ? stored.lastSeenAt
        : 0
    map.set(terminalId, { hint, lastSeenAt })
  }
  return map
}

function parseHint(raw: unknown): WorkspaceHint | null {
  if (typeof raw !== 'object' || raw === null) return null
  const hint = raw as { id?: unknown; path?: unknown }
  const id = textOf(hint.id)
  const path = textOf(hint.path)
  if (id === null && path === null) return null
  return {
    ...(id === null ? {} : { id }),
    ...(path === null ? {} : { path })
  }
}

export function serializeTerminalMap(
  map: ReadonlyMap<string, TerminalEntry> = terminalWorkspaces
): { version: number; entries: Array<[string, TerminalEntry]> } {
  return { version: TERMINAL_STORE_VERSION, entries: [...map.entries()] }
}

async function loadTerminalMap(orca: OrcaWorkerApi): Promise<void> {
  if (terminalMapLoaded) return
  terminalMapLoaded = true
  try {
    const raw = await orca.storage.get(TERMINAL_STORE_KEY)
    const loaded = parseTerminalMap(raw)
    terminalWorkspaces.clear()
    for (const [terminalId, entry] of loaded) {
      terminalWorkspaces.set(terminalId, entry)
    }
    terminalMapDirty = false
  } catch (error) {
    orca.log(`demir-kit: terminal haritası okunamadı: ${messageOf(error)}`)
  }
}

async function saveTerminalMap(orca: OrcaWorkerApi): Promise<void> {
  if (!terminalMapDirty) return
  terminalMapDirty = false
  try {
    if (terminalWorkspaces.size === 0) {
      await orca.storage.delete(TERMINAL_STORE_KEY)
    } else {
      await orca.storage.set(
        TERMINAL_STORE_KEY,
        serializeTerminalMap(terminalWorkspaces)
      )
    }
  } catch (error) {
    terminalMapDirty = true
    orca.log(`demir-kit: terminal haritası yazılamadı: ${messageOf(error)}`)
  }
}

function scheduleTerminalSave(orca: OrcaWorkerApi): void {
  if (terminalSaveTimer !== null) clearTimeout(terminalSaveTimer)
  terminalSaveTimer = setTimeout(() => {
    terminalSaveTimer = null
    void saveTerminalMap(orca)
  }, TERMINAL_SAVE_MS)
}

/**
 * TTL, silinmiş workspace ve 200 kayıt sınırını uygular. `truncated` liste
 * eksikse workspace kontrolü atlanır: geçerli kayıt yanlışlıkla silinmez.
 */
export function pruneTerminalMap(
  workspaces: readonly Workspace[],
  truncated: boolean,
  now = Date.now()
): boolean {
  let changed = false
  const canCheckWorkspaces = !truncated && workspaces.length > 0
  for (const [terminalId, entry] of terminalWorkspaces) {
    const expired = now - entry.lastSeenAt > TERMINAL_TTL_MS
    const missing =
      canCheckWorkspaces && matchWorkspaceHint(workspaces, entry.hint) === null
    if (expired || missing) {
      terminalWorkspaces.delete(terminalId)
      changed = true
    }
  }
  if (terminalWorkspaces.size > TERMINAL_MAP_LIMIT) {
    const oldestFirst = [...terminalWorkspaces.entries()].sort(
      (left, right) => left[1].lastSeenAt - right[1].lastSeenAt
    )
    const drop = terminalWorkspaces.size - TERMINAL_MAP_LIMIT
    for (let index = 0; index < drop; index += 1) {
      const terminalId = oldestFirst[index]?.[0]
      if (terminalId !== undefined) {
        terminalWorkspaces.delete(terminalId)
        changed = true
      }
    }
  }
  if (changed) terminalMapDirty = true
  return changed
}

/**
 * `workspace.changed` gövdesi. Yeni hostlar `{ workspaceId, path }`, 1.4.x
 * yalnız `{ context: { displayName } }` taşır; ikisi de okunur, olay yoksa null.
 */
function focusSignalOf(event: unknown): FocusSignal | null {
  if (typeof event !== 'object' || event === null) return null
  const payload = event as {
    workspaceId?: unknown
    id?: unknown
    path?: unknown
    name?: unknown
    context?: unknown
  }
  const context =
    typeof payload.context === 'object' && payload.context !== null
      ? (payload.context as {
          workspaceId?: unknown
          id?: unknown
          path?: unknown
          displayName?: unknown
          name?: unknown
        })
      : null
  const id =
    textOf(payload.workspaceId) ??
    textOf(payload.id) ??
    textOf(context?.workspaceId) ??
    textOf(context?.id)
  const path = textOf(payload.path) ?? textOf(context?.path)
  const name =
    textOf(payload.name) ??
    textOf(context?.displayName) ??
    textOf(context?.name)
  if (id === null && path === null && name === null) return null
  return {
    ...(id === null ? {} : { id }),
    ...(path === null ? {} : { path }),
    ...(name === null ? {} : { name })
  }
}

/**
 * Odaklı workspace: önce olayın `id`'si, sonra `path`, sonra odaktaki
 * terminallerin öğrettiği tek workspace, sonra odaklı ajanların terminalleri,
 * en son ad — ad yalnız tek bir workspace'e aitse. Sinyaller çelişirse ya da
 * yoksa null: tahmin yok.
 */
export function resolveFocus(
  workspaces: readonly Workspace[],
  focus: FocusSignal | null,
  displayName: string | null = null,
  terminals: readonly string[] = [],
  maps: ReadonlyMap<string, TerminalEntry> = terminalWorkspaces,
  agentTerminals: readonly string[] = []
): FocusMatch {
  const id = textOf(focus?.id)
  if (id !== null) {
    // `workspaceId` bazen `<repo>::/yol` gelir: ipucu çözümleyicisi yolu bulur.
    const byId = matchWorkspaceHint(workspaces, hintsFromWorkspaceId(id))
    if (byId !== null) return { workspace: byId, source: 'event' }
  }
  const path = textOf(focus?.path)
  if (path !== null) {
    const byPath = matchWorkspaceHint(workspaces, { path })
    if (byPath !== null) return { workspace: byPath, source: 'path' }
  }
  const fromContext = terminalFocus(workspaces, terminals, maps)
  if (fromContext.conflict) return { workspace: null, source: 'none' }
  if (fromContext.workspace !== null) {
    return { workspace: fromContext.workspace, source: 'terminal' }
  }
  const fromAgents = terminalFocus(workspaces, agentTerminals, maps)
  if (fromAgents.conflict) return { workspace: null, source: 'none' }
  if (fromAgents.workspace !== null) {
    return { workspace: fromAgents.workspace, source: 'agent' }
  }
  const name = textOf(focus?.name) ?? textOf(displayName)
  if (name !== null) {
    const sameName = workspaces.filter((workspace) => workspace.name === name)
    if (sameName.length === 1) {
      return { workspace: sameName[0] ?? null, source: 'name' }
    }
  }
  return { workspace: null, source: 'none' }
}

/** `resolveFocus` sonucunun yalnız workspace kısmı; eski çağıranlar için. */
export function pickFocused(
  workspaces: readonly Workspace[],
  focus: FocusSignal | null,
  displayName: string | null = null,
  terminals: readonly string[] = [],
  maps: ReadonlyMap<string, TerminalEntry> = terminalWorkspaces,
  agentTerminals: readonly string[] = []
): Workspace | null {
  return resolveFocus(
    workspaces,
    focus,
    displayName,
    terminals,
    maps,
    agentTerminals
  ).workspace
}

export interface ProjectRef {
  id: string
  /** `workspace.list` alanı; host kaydetmeyen kurulumlarda null. */
  hostId: string | null
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
    hostId: textOf(workspace.hostId),
    path: workspace.path,
    name: typeof workspace.name === 'string' ? workspace.name : '',
    kitRoot
  }
}

/**
 * Host dilimi: önce `hostId`, yoksa workspace id'sinin `::` öncesi kimliği
 * (`identity:<host>`), ikisi de yoksa boş. Host kaydetmeyen iki kurulum aynı
 * yolu paylaşırsa id ön eki onları ayırır; o da yoksa kayıtlar birleşebilir.
 */
function hostSegment(hostId: string | null, id: string | null): string {
  const host = textOf(hostId)
  if (host !== null) return host
  const identity = textOf(id)
  if (identity !== null) {
    const cut = identity.indexOf('::')
    if (cut > 0) return `identity:${identity.slice(0, cut)}`
  }
  return ''
}

/**
 * Aynı dizin iki kez sayılmasın diye ref anahtarı: host dilimi + normalize yol.
 * Host kimliği anahtara girer; iki hosttaki aynı mutlak yol tek ref'e düşmez.
 */
export function refKey(
  ref: Pick<ProjectRef, 'hostId' | 'path'> & { id?: string }
): string {
  return `${hostSegment(ref.hostId, ref.id ?? null)}::${normalizePath(ref.path)}`
}

/**
 * Karşılaştırma anahtarı: yolun sembolik bağları ve `..` parçaları çözülmüş
 * hâli. Yol diskte yoksa `realpathSync` hata verir; o zaman normalize yol
 * kullanılır (davranış eskisiyle aynı).
 */
export function realPath(path: string): string {
  try {
    return normalizePath(realpathSync(path))
  } catch {
    return normalizePath(path)
  }
}

/**
 * Ayar yolunu (`projectPath`) listedeki workspace'e bağlar: normalize eşleşme,
 * yani sonda `/` ya da farklı büyük/küçük harf aynı workspace'tir. Önce gerçek
 * yollar (`realpathSync`) karşılaştırılır: sembolik bağ ya da `..` üzerinden
 * verilen yol da aynı workspace'i bulur. Eşleşme yoksa null: sentetik ref'e
 * düşmek çağıranın kararı.
 */
export function matchWorkspacePath(
  workspaces: readonly Workspace[],
  configured: string
): Workspace | null {
  const path = textOf(configured)
  if (path === null) return null
  const wanted = normalizePath(path)
  const resolved = realPath(path)
  return (
    workspaces.find((workspace) => {
      if (typeof workspace.path !== 'string') return false
      return (
        realPath(workspace.path) === resolved ||
        normalizePath(workspace.path) === wanted
      )
    }) ?? null
  )
}

interface ResolvedProjects {
  refs: ProjectRef[]
  focused: string | null
  focusSource: FocusSource
  workspaces: Workspace[]
  contextTerminals: string[]
  truncated: boolean
}

/** `git rev-parse` üst sınırı: yerel bir komut, ağ beklemez. */
const REPO_LOOKUP_TIMEOUT_MS = 2_000
/** Yol -> ortak depo kökü; hata da önbelleğe girer, her turda yeniden denenmez. */
const repoRootCache = new Map<string, string | null>()

/**
 * Bir worktree'nin ortak depo kökü: `git-common-dir` üst dizini. Ana checkout
 * da worktree de aynı kökü verir; git yoksa ya da yol bir depo değilse null.
 */
export function repoRootOf(path: string): Promise<string | null> {
  const cached = repoRootCache.get(path)
  if (cached !== undefined) return Promise.resolve(cached)
  return new Promise((resolve) => {
    execFile(
      'git',
      ['-C', path, 'rev-parse', '--path-format=absolute', '--git-common-dir'],
      { timeout: REPO_LOOKUP_TIMEOUT_MS, maxBuffer: 64 * 1024 },
      (error, stdout) => {
        let root: string | null = null
        if (error === null) {
          const common = stdout.trim()
          const cut = common.lastIndexOf('/')
          if (cut > 0) root = common.slice(0, cut)
        }
        repoRootCache.set(path, root)
        resolve(root)
      }
    )
  })
}

/**
 * Aynı deponun ana checkout'u ve epic worktree'leri tek ref'e iner: `status.py`
 * ve içindeki `gh` çağrısı her worktree için ayrı koşmaz. Kazanan sırası odaklı
 * ref, ana checkout, worktree olmayan yol; grup tek ref'ten oluşuyorsa o kalır.
 */
export function collapseProjectRefs(
  refs: readonly ProjectRef[],
  focused: string | null,
  roots: ReadonlyMap<string, string | null>
): ProjectRef[] {
  const groups = new Map<string, ProjectRef[]>()
  for (const ref of refs) {
    const root = roots.get(ref.path) ?? null
    const segment = hostSegment(ref.hostId, ref.id)
    const key =
      root === null
        ? `${segment}::path:${normalizePath(ref.path)}`
        : `${segment}::repo:${normalizePath(root)}`
    const group = groups.get(key)
    if (group === undefined) groups.set(key, [ref])
    else group.push(ref)
  }
  const collapsed: ProjectRef[] = []
  for (const group of groups.values()) {
    const winner =
      group.find((ref) => ref.id === focused) ??
      group.find((ref) => {
        const root = roots.get(ref.path) ?? null
        return root !== null && normalizePath(root) === normalizePath(ref.path)
      }) ??
      group.find((ref) => !isWorktreePath(ref.path)) ??
      group[0]
    if (winner !== undefined) collapsed.push(winner)
  }
  return collapsed
}

/**
 * Tüm workspace'ler; kit'i olanlar. Odaklı workspace, sonra ayarlardaki yol,
 * sonra kalanlar gelir. Aynı host + dizin bir kez sayılır.
 */
async function resolveProjects(orca: OrcaWorkerApi): Promise<ResolvedProjects> {
  const listed = (await call(orca)('workspace.list')) as {
    workspaces?: Workspace[]
    truncated?: boolean
  } | null
  const workspaces = (listed?.workspaces ?? []).filter(
    (workspace): workspace is Workspace => typeof workspace.path === 'string'
  )
  const context = (await call(orca)('workspace.readContext')) as {
    displayName?: string
    terminals?: Array<{ id?: unknown }>
  } | null
  const focusedName =
    typeof context?.displayName === 'string' ? context.displayName : null
  const focusedTerminals = (context?.terminals ?? [])
    .map((terminal) => terminal?.id)
    .filter((id): id is string => typeof id === 'string' && id !== '')
  // Olay id/path taşımıyorsa terminal eşlemesi, o da yoksa benzersiz ad.
  const focus = resolveFocus(
    workspaces,
    focusSignal,
    focusedName,
    focusedTerminals
  )

  const refs: ProjectRef[] = []
  const seen = new Set<string>()
  const push = (ref: ProjectRef | null): void => {
    if (ref === null) return
    const key = refKey(ref)
    if (seen.has(key)) return
    seen.add(key)
    refs.push(ref)
  }

  const focusedRef = focus.workspace ? refFor(focus.workspace) : null
  push(focusedRef)

  const configured = await orca.settings.get('projectPath')
  if (typeof configured === 'string' && configured.trim() !== '') {
    const path = configured.trim()
    // Ayar yolu listedeki workspace'e normalize eşleşmeyle bağlanır: sonda `/`
    // ya da farklı yazım olsa da sentetik (host'suz) ref üretilmez.
    const match = matchWorkspacePath(workspaces, path)
    push(match === null ? refFor({ path }) : refFor(match))
  }

  for (const workspace of workspaces) {
    push(refFor(workspace))
  }

  // Aynı depo tek taranır: epic worktree'leri `status.py` + `gh` çağrısını
  // çoğaltmaz. Odaklı ref grubun kazananı olur, kart kimliği değişmez.
  const focusedId = focusedRef?.id ?? null
  const roots = new Map<string, string | null>()
  await Promise.all(
    [...new Set(refs.map((ref) => ref.path))].map(async (path) => {
      roots.set(path, await repoRootOf(path))
    })
  )
  const collapsed = collapseProjectRefs(refs, focusedId, roots)

  // Odak çözülemediyse ya da kit taşımıyorsa `focused` null kalır: tahmin yok.
  return {
    refs: collapsed,
    focused: focusedId,
    focusSource: focusedRef === null ? 'none' : focus.source,
    workspaces,
    contextTerminals: focusedTerminals,
    truncated: listed?.truncated === true
  }
}

/** `status.py` stdout'u: çıkış kodu 0 değilse de taşınır, yoksa kaybedilirdi. */
export interface RunStatusResult {
  code: number | null
  stdout: string
  stderr: string
}

function runStatus(ref: ProjectRef): Promise<RunStatusResult> {
  return new Promise((resolve) => {
    execFile(
      'python3',
      [join(ref.kitRoot, STATUS_SCRIPT), ...STATUS_ARGS],
      { cwd: ref.path, timeout: STATUS_TIMEOUT_MS, maxBuffer: 4 * 1024 * 1024 },
      (error, stdout, stderr) => {
        const code =
          error === null
            ? 0
            : typeof (error as { code?: unknown }).code === 'number'
              ? ((error as { code: number }).code)
              : null
        resolve({
          code,
          stdout: typeof stdout === 'string' ? stdout : String(stdout ?? ''),
          stderr: typeof stderr === 'string' ? stderr : String(stderr ?? '')
        })
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
 * `tracker.repo`, yoksa epic worktree son eki atılmış yol. Anahtar host ile
 * başlar: iki hosttaki aynı yol/repo iki ayrı kart kalır.
 */
export function projectKey(project: StatusProject): string {
  const host = hostSegment(project.host ?? null, project.id)
  const prefix = host === '' ? '' : `host:${host}::`
  const root = (project.repo_root ?? '').trim()
  if (root !== '') return `${prefix}root:${normalizePath(root)}`
  const repo = (project.repo ?? '').trim().toLowerCase()
  if (repo !== '') return `${prefix}repo:${repo}`
  return `${prefix}path:${normalizePath(project.path.replace(/\/epic-\d+$/, ''))}`
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
export function dedupeProjects(
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

/**
 * Odaklı workspace'in ajanları hangi karta yazılır: kart doğrudan duruyorsa
 * kendisi, dedupe ana checkout kartında birleştirdiyse o kart (repo anahtarı).
 * Odak kit projesi değilse null: hiçbir karta ajan yazılmaz.
 */
export function agentTarget(
  deduped: StatusProject[],
  snapshots: StatusProject[],
  focusedId: string | null
): string | null {
  if (focusedId === null) return null
  const direct = deduped.find((project) => project.id === focusedId)
  if (direct !== undefined) return direct.id
  const focused = snapshots.find((project) => project.id === focusedId)
  if (focused === undefined) return null
  const key = projectKey(focused)
  const survivor = deduped.find((project) => projectKey(project) === key)
  return survivor?.id ?? null
}

/** Bir projenin hatası yalnız o projede kalır: diğerleri ok:true döner. */
function failedProject(ref: ProjectRef, message: string): StatusProject {
  return {
    id: ref.id,
    host: ref.hostId,
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
    stale: true,
    pulse: null
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
        stateStartedAt?: number
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
        state: item.state,
        ...(typeof item.stateStartedAt === 'number' &&
        Number.isFinite(item.stateStartedAt)
          ? { stateStartedAt: item.stateStartedAt }
          : {})
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

/**
 * Önbellek girdisi bu ref'e ait mi: aynı yol ve aynı host dilimi. Saf yardımcı:
 * aynı yolu paylaşan başka hostun kaydı bu karta servis edilmez.
 */
export function cacheMatches(
  entry: Pick<CacheEntry, 'project'> | null,
  ref: Pick<ProjectRef, 'hostId' | 'path'> & { id?: string }
): boolean {
  if (entry === null) return false
  if (entry.project.path !== ref.path) return false
  return (
    hostSegment(entry.project.host ?? null, entry.project.id) ===
    hostSegment(ref.hostId, ref.id ?? null)
  )
}

/** Depo önbelleği yaş uyarısının eki; panel bu metni çözüp "önbellek yaşı" gösterir. */
const CACHE_AGE_PREFIX = 'önbellekten okundu: '

/** Eski yaş uyarılarını atar, aktüelini ekler: depodan servis edilen yük hep taze yaş der. */
export function withCacheAge(warnings: string[], ageSeconds: number): string[] {
  const rest = warnings.filter((warning) => !warning.startsWith(CACHE_AGE_PREFIX))
  return [...rest, `${CACHE_AGE_PREFIX}${ageSeconds}s`]
}

/** `status.py` stdout'unu sözleşme biçiminde çözer; bozuk ya da eksikse null. */
export function parseStatusJson(stdout: string): StatusJson | null {
  const text = stdout.trim()
  if (text === '') return null
  try {
    const value: unknown = JSON.parse(text)
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      return null
    }
    const data = value as StatusJson
    if (data.epics !== undefined && !Array.isArray(data.epics)) return null
    if (data.counts !== undefined && typeof data.counts !== 'object') return null
    if (data.warnings !== undefined && !Array.isArray(data.warnings)) return null
    return data
  } catch {
    return null
  }
}

/** 0-dışı çıkışta panele taşınacak kısa neden: önce stderr'in ilk satırı, sonra sözleşme uyarısı. */
function reasonFrom(result: RunStatusResult, data: StatusJson | null): string {
  const stderrLine =
    result.stderr
      .split('\n')
      .map((line) => line.trim())
      .find((line) => line !== '') ?? ''
  const contractLine = Array.isArray(data?.warnings)
    ? (data.warnings.find(
        (warning) => typeof warning === 'string' && warning.trim() !== ''
      ) ?? '')
    : ''
  const detail = stderrLine !== '' ? stderrLine : contractLine
  const base = `status.py çıkış ${result.code ?? '?'}`
  return (detail === '' ? base : `${base}: ${detail}`).slice(0, 200)
}

/** Sözleşme alanlarını olduğu gibi koruyan proje yükü; 0-dışı çıkışta da epics/counts/pulse taşınır. */
function statusProject(
  ref: ProjectRef,
  data: StatusJson,
  overrides: {
    ok: boolean
    stale?: boolean
    error?: string
    warnings?: string[]
  }
): StatusProject {
  const baseWarnings = Array.isArray(data.warnings)
    ? data.warnings.filter((warning): warning is string => typeof warning === 'string')
    : []
  const warnings = [...baseWarnings, ...(overrides.warnings ?? [])]
  const project: StatusProject = {
    id: ref.id,
    host: ref.hostId,
    path: ref.path,
    name: projectName(ref, data),
    repo: projectRepo(data),
    repo_root: projectRepoRoot(data),
    ok: overrides.ok,
    epics: Array.isArray(data.epics) ? data.epics : [],
    counts: data.counts ?? { ...ZERO_COUNTS },
    warnings,
    stale: overrides.stale ?? data.stale === true,
    pulse: data.pulse ?? null
  }
  if (overrides.error !== undefined) project.error = overrides.error
  return project
}

async function cachedProject(
  orca: OrcaWorkerApi,
  ref: ProjectRef
): Promise<StatusProject | null> {
  const raw = await orca.storage.get(`${CACHE_PREFIX}${refKey(ref)}`)
  if (!isCacheEntry(raw)) return null
  const ageMs = Date.now() - raw.saved_at
  if (ageMs >= CACHE_MS) return null
  // Aynı yol iki hostta: giriş host dilimine ve yola bağlıdır.
  if (!cacheMatches(raw, ref)) return null
  // Önbellek yaşı uyarıyı günceller: panel depodaki kaydın aktüel yaşını görür.
  return {
    ...raw.project,
    warnings: withCacheAge(raw.project.warnings, Math.floor(ageMs / 1000))
  }
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
  // Beklenmedik hata yalnız bu projede kalır: Promise.all diğerlerini düşürmez.
  try {
    const result = await runStatus(ref)
    const data = parseStatusJson(result.stdout)
    if (result.code === 0) {
      if (data === null) {
        return failedProject(ref, 'status.py JSON okunamadı')
      }
      const project = statusProject(ref, data, { ok: true })
      try {
        await orca.storage.set(`${CACHE_PREFIX}${refKey(ref)}`, {
          saved_at: Date.now(),
          project
        })
      } catch (storageError) {
        // Önbelleğe yazılamazsa yük yine döner; yalnız sonraki tur python'a gider.
        orca.log(`demir-kit: önbellek yazılamadı (${ref.path}): ${String(storageError)}`)
      }
      return project
    }
    // 0-dışı çıkış: status.py sözleşmeyi yine de stdout'a yazdıysa veriyi koru,
    // nedeni ve `stale: true` bilgisini panele taşı (epics/counts/pulse dokunulmaz).
    const reason = reasonFrom(result, data)
    if (data !== null) {
      // Bozulmuş ya da limitten düşmüş yük depoya yazılmaz; sonraki tur yine dener.
      return statusProject(ref, data, {
        ok: false,
        stale: true,
        error: reason,
        warnings: [reason]
      })
    }
    return failedProject(ref, reason)
  } catch (error) {
    return failedProject(ref, messageOf(error))
  }
}

/** `EP-N · CP d/t · gate g`; 64 karaktere kırpılır. */
function epicLine(epic: StatusEpic): string {
  // Eski `{done,total}` şekli dizi değildir: çökme yok, CP 0/0 görünür.
  const checkpoints = Array.isArray(epic.checkpoints) ? epic.checkpoints : []
  const done = checkpoints.filter((checkpoint) => checkpoint.done === true).length
  const total = checkpoints.length
  const gate = epic.gate ?? 'yok'
  return `EP-${epic.number} · CP ${done}/${total} · gate ${gate}`.slice(0, 64)
}

/** Odak epic'i yoksa durum çubuğu için ilk yürüyen/epic satırı. */
function firstActiveEpic(
  projects: readonly StatusProject[]
): StatusEpic | undefined {
  const open = projects
    .filter((project) => project.ok)
    .flatMap((project) => project.epics ?? [])
  const executing = open.find((epic) =>
    (epic.leaves ?? []).some((leaf) => leaf.state === 'executing')
  )
  return executing ?? open[0]
}

/** Durum çubuğu odaklı projeyi anlatır; odak yoksa aktif/canlı özet verir. */
export function statusText(snapshot: StatusSnapshot): string {
  const focused = snapshot.projects.find((item) => item.id === snapshot.focused)
  const epic = focused?.ok === true ? focused.epics?.[0] : undefined
  if (epic !== undefined && typeof epic.number === 'number') {
    return epicLine(epic)
  }
  const activeEpic = firstActiveEpic(snapshot.projects)
  if (activeEpic !== undefined) return epicLine(activeEpic)
  const healthy = snapshot.projects.filter((item) => item.ok).length
  const live = snapshot.live
  if (live !== undefined && live.working > 0) {
    return `${live.working} çalışıyor · ${healthy} proje`.slice(0, 64)
  }
  if (live !== undefined && live.blocked > 0) {
    return `${live.blocked} engelli · ${healthy} proje`.slice(0, 64)
  }
  const active = snapshot.active
  if (active !== undefined && active.epics > 0) {
    return `${active.projects} aktif · ${healthy} proje`.slice(0, 64)
  }
  return healthy > 0 ? `${healthy} proje` : NO_KIT
}

/** Açık epic/leaf sayısı; odaktan bağımsız, panelin aktif iş özeti. */
export function activeOf(projects: readonly StatusProject[]): StatusActive {
  let activeProjects = 0
  let epics = 0
  let leaves = 0
  for (const project of projects) {
    if (!Array.isArray(project.epics) || project.epics.length === 0) continue
    activeProjects += 1
    epics += project.epics.length
    for (const epic of project.epics) {
      leaves += Array.isArray(epic.leaves) ? epic.leaves.length : 0
    }
  }
  return { projects: activeProjects, epics, leaves }
}

function failedSnapshot(message: string, warnings: string[]): StatusSnapshot {
  return {
    ok: false,
    code: 'no-kit',
    generated_at: new Date().toISOString(),
    focused: null,
    focusSource: 'none',
    active: { projects: 0, epics: 0, leaves: 0 },
    pulse: null,
    projects: [],
    warnings: [...warnings, message],
    error: message
  }
}

/** Beklenmeyen okuma hatası: `no-kit` deme, panel "durum okunamadı" çizsin. */
function errorSnapshot(message: string, warnings: string[]): StatusSnapshot {
  return {
    ok: false,
    generated_at: new Date().toISOString(),
    focused: null,
    focusSource: 'none',
    active: { projects: 0, epics: 0, leaves: 0 },
    pulse: null,
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
    // Maliyet henüz ölçülmüyor: sessiz '-' yerine açık "yok".
    await host('statusBar.update', { id: 'cost', text: 'yok' })
  } catch (error) {
    // No status bar (headless host): the panel still gets the snapshot.
    orca.log(`demir-kit: status bar güncellenemedi: ${String(error)}`)
  }
}

/** Son yayımlanan anlık görüntü: ajan olayı yalnız tek kartı tazeler. */
let lastSnapshot: StatusSnapshot | null = null
/** Ajanların gerçekten okunduğu odaklı workspace; kit taşımıyorsa null. */
let lastAgentWorkspace: string | null = null

async function refreshOnce(
  orca: OrcaWorkerApi,
  force: boolean
): Promise<StatusSnapshot> {
  const warnings: string[] = []
  try {
    const resolved = await resolveProjects(orca)
    if (resolved.refs.length === 0) {
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
      resolved.refs.map((ref) => projectSnapshot(orca, ref, force))
    )

    // Ajanlar her zaman Orca'nın odaklı workspace'inden gelir. Odak adı
    // çözülemediyse ajan terminalleri son bir odak sinyali olur.
    const listing = await readAgents(orca)
    if (listing.warning !== null) warnings.push(listing.warning)
    const agentTerminals = listing.agents
      .map((agent) => agent.terminalId)
      .filter((id): id is string => typeof id === 'string' && id !== '')

    let focused = resolved.focused
    let focusSource = resolved.focusSource
    if (focused === null && agentTerminals.length > 0) {
      const byAgent = resolveFocus(
        resolved.workspaces,
        null,
        null,
        [],
        terminalWorkspaces,
        agentTerminals
      )
      if (byAgent.workspace !== null) {
        focused = byAgent.workspace.id ?? byAgent.workspace.path ?? null
        focusSource = 'agent'
      }
    }
    if (focused === null) {
      // Terminal id'si gelmese de aktif ajanın worktree ipucu tek ise odak olur.
      const byActive = activeAgentFocus(resolved.workspaces, listing.agents)
      if (byActive !== null) {
        focused = byActive.id ?? byActive.path ?? null
        focusSource = 'agent'
      }
    }

    // Aynı repo (ana checkout + epic worktree) tek kartta; odaklı önce gelir.
    const deduped = dedupeProjects(snapshots, focused)
    // Odak dedupe sonrası hangi karta düştüyse ajanlar oraya yazılır; kit değilse null.
    const target = agentTarget(deduped, snapshots, focused)

    // Görülen terminalleri tazele ve haritayı sınırda tut.
    touchTerminals([...resolved.contextTerminals, ...agentTerminals])
    pruneTerminalMap(resolved.workspaces, resolved.truncated)
    if (terminalMapDirty) scheduleTerminalSave(orca)

    // Canlı ajanlar yalnız odaklı karta yazılır; diğer kartlar sıfır taşır.
    const projects = deduped.map((project) =>
      project.id === target
        ? { ...project, agents: listing.agents, live: listing.live }
        : { ...project, agents: [], live: zeroLive() }
    )
    const active = activeOf(projects)
    if (
      target === null &&
      resolved.focused === null &&
      (listing.agents.length > 0 || active.epics > 0)
    ) {
      warnings.push('odak çözülemedi')
    }
    const snapshot: StatusSnapshot = {
      ok: projects.some((project) => project.ok),
      generated_at: new Date().toISOString(),
      focused: target,
      focusSource: target === null ? 'none' : focusSource,
      live: listing.live,
      active,
      pulse: fleetPulse(projects),
      projects,
      warnings
    }
    lastSnapshot = snapshot
    lastAgentWorkspace = target
    await publish(orca, snapshot)
    return snapshot
  } catch (error) {
    // Beklenmeyen hata paneli düşürmez: son iyi görüntü ya da okunamadı kartı.
    const snapshot = errorSnapshot(messageOf(error), warnings)
    lastSnapshot = snapshot
    lastAgentWorkspace = null
    await publish(orca, snapshot)
    return snapshot
  }
}

/** Aynı anda tek tazeleme: paralel python ve sırasız yayın olmasın. */
interface InFlightRefresh {
  promise: Promise<StatusSnapshot>
  force: boolean
}

let refreshInFlight: InFlightRefresh | null = null

/**
 * Tüm çağıranlar buraya gelir. Uçuştaki çalışma yeterliyse ona katılır;
 * zorunlu tazeleme, önbellekli çalışmanın arkasında bekleyip yeniden koşar.
 */
function refresh(orca: OrcaWorkerApi, force: boolean): Promise<StatusSnapshot> {
  const current = refreshInFlight
  if (current !== null) {
    if (!force || current.force) return current.promise
    // Önbellekli çalışma bitsin, sonra taze zorunlu tur başlasın.
    return current.promise.then(() => refresh(orca, true))
  }
  const run = refreshOnce(orca, force)
  const entry: InFlightRefresh = { promise: run, force }
  refreshInFlight = entry
  void run
    .catch(() => undefined)
    .finally(() => {
      if (refreshInFlight === entry) refreshInFlight = null
    })
  return run
}

/** Öğrenme kaynaklı odak tazelemesinin taban aralığı (ms). */
const FOCUS_RETRY_MS = 1000
/** Son öğrenme kaynaklı odak tazelemesi; 0 hiç denenmedi demektir. */
let lastFocusRetry = 0

/** Öğrenme sonrası tazeleme: son denemeden bu yana 1000 ms geçtiyse evet. */
export function shouldRetryFocus(now: number, last: number): boolean {
  return now - last >= FOCUS_RETRY_MS
}

/** Olayın workspace kimliği: `workspaceId`, `worktreeId` ya da bağlam id'si. */
function workspaceIdOf(event: unknown): string | null {
  if (typeof event !== 'object' || event === null) return null
  const payload = event as {
    workspaceId?: unknown
    worktreeId?: unknown
    context?: { workspaceId?: unknown; id?: unknown }
  }
  return (
    textOf(payload.workspaceId) ??
    textOf(payload.worktreeId) ??
    textOf(payload.context?.workspaceId) ??
    textOf(payload.context?.id)
  )
}

/**
 * `agent.status.changed` olayının hedefi. Workspace yoksa tam tazeleme:
 * eski odak (`lastAgentWorkspace`) yeniden kullanılmaz, yanlış karta yazılmaz.
 * Olay başka workspace'tense hiçbir kart değişmez; aynıysa yalnız o kart.
 */
export function agentEventTarget(
  workspaceId: string | null,
  lastAgentWorkspace: string | null
): 'refresh' | 'ignore' | string {
  if (workspaceId === null || workspaceId === '') return 'refresh'
  if (workspaceId !== lastAgentWorkspace) return 'ignore'
  return workspaceId
}

/**
 * `agent.status.changed`: olayın workspace'i odaklıysa yalnız o kartın ajanları
 * tazelenir. Odaklı olmayan ya da kit'i olmayan workspace hiçbir karta yazmaz.
 */
async function refreshAgents(
  orca: OrcaWorkerApi,
  workspaceId: string
): Promise<void> {
  const target = workspaceId
  // Yalnız ajanları okunabilen (odaklı) workspace'in kartı güncellenir.
  if (target !== lastAgentWorkspace) return
  const current = lastSnapshot
  if (current === null) return
  if (!current.projects.some((project) => project.id === target)) return
  const listing = await readAgents(orca)
  if (listing.warning !== null) orca.log(`demir-kit: ${listing.warning}`)
  const snapshot: StatusSnapshot = {
    ...current,
    live: listing.live,
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
  // Kalıcı terminal haritası: worker yeniden başlasa da odak eşlemesi korunur.
  await loadTerminalMap(orca)

  orca.panels.handle('status.snapshot', async () => {
    try {
      return await refresh(orca, false)
    } catch (error) {
      // Beklenmeyen hata panele istisna olarak gitmez: son iyi görüntü döner.
      orca.log(`demir-kit: snapshot okunamadı: ${messageOf(error)}`)
      return lastSnapshot ?? errorSnapshot(messageOf(error), [])
    }
  })

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

  /** Odak tazelemesi: 1 sn taban aralık, olay fırtınasında art arda koşmaz. */
  const retryFocus = (): void => {
    const now = Date.now()
    if (!shouldRetryFocus(now, lastFocusRetry)) return
    lastFocusRetry = now
    // Ajan olayı yaymadığı için döngü yoktur.
    void refresh(orca, false)
  }

  orca.events.on('workspace.changed', (event) => {
    try {
      // Olay odak için tek otorite: id/path varsa onlar, yoksa bağlamın adı.
      const context =
        typeof event === 'object' && event !== null
          ? (event as { context?: unknown }).context
          : undefined
      if (context === null) {
        focusSignal = null
        resetAgentHints()
      } else {
        const signal = focusSignalOf(event)
        if (signal !== null) focusSignal = signal
      }
      // Bağlamdaki terminaller odaklı workspace'e aittir: sıcaklıklarını tazele.
      const terminals =
        typeof context === 'object' && context !== null
          ? (context as { terminals?: Array<{ id?: unknown }> }).terminals ?? []
          : []
      const ids = terminals
        .map((terminal) => terminal?.id)
        .filter((id): id is string => typeof id === 'string' && id !== '')
      if (touchTerminals(ids)) scheduleTerminalSave(orca)
      void refresh(orca, true)
    } catch (error) {
      orca.log(`demir-kit: workspace olayı işlenemedi: ${messageOf(error)}`)
    }
  })

  // Ajan olayı: terminal haritasını öğren; odak çözümü için tam tazeleme.
  orca.events.on('agent.status.changed', (event) => {
    try {
      const hint = agentWorkspaceHint(event)
      const state = agentStateOf(event)
      const started =
        typeof event === 'object' && event !== null
          ? (event as { stateStartedAt?: unknown }).stateStartedAt
          : undefined
      if (hint !== null && state !== null) {
        rememberAgentHint(
          hint,
          state,
          Date.now(),
          typeof started === 'number' && Number.isFinite(started)
            ? started
            : undefined
        )
      }
      if (learnAgentTerminal(event)) scheduleTerminalSave(orca)
      const target = agentEventTarget(workspaceIdOf(event), lastAgentWorkspace)
      if (target === 'refresh' || target === 'ignore') {
        // Yeni terminal eşlemesi odağı çözebilir; 1 sn taban aralıkla tazele.
        retryFocus()
        return
      }
      if (
        lastSnapshot?.projects.some((project) => project.id === target) === true
      ) {
        void refreshAgents(orca, target)
        return
      }
      // İç worktree id'si kart id'siyle eşleşmedi: tam tazeleme odağı çözer.
      retryFocus()
    } catch (error) {
      orca.log(`demir-kit: ajan olayı işlenemedi: ${messageOf(error)}`)
    }
  })

  orca.settings.onDidChange(() => {
    try {
      void refresh(orca, true)
    } catch (error) {
      orca.log(`demir-kit: ayar tazelemesi başarısız: ${messageOf(error)}`)
    }
  })

  // Hazır olma bu turu beklemez: çok sayıda projede `status.py` 10 sn'yi aşar
  // ve Orca işçiyi "hazır olmadı" diye yeniden başlatır. Panel isteği uçuştaki
  // tura katılır; ilk veri hazır olma sinyalinden sonra gelir.
  void refresh(orca, true).catch((error) => {
    orca.log(`demir-kit: ilk tazeleme başarısız: ${messageOf(error)}`)
  })
}
