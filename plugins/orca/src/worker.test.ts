// Odak çözümü ve ajan kartı saf yardımcılarla sınanır: python ya da gerçek kit yok.
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, rmSync, symlinkSync } from 'node:fs'
import * as os from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import type { StatusProject } from './protocol'
import {
  agentEventTarget,
  agentTarget,
  cacheMatches,
  dedupeProjects,
  learnAgentTerminal,
  matchWorkspacePath,
  pickFocused,
  projectKey,
  refKey,
  rememberTerminal,
  shouldRetryFocus,
  terminalWorkspaceIds
} from './worker'

const duplicateNames = [
  { id: 'ws-1', name: 'main', path: '/repo/one' },
  { id: 'ws-2', name: 'main', path: '/repo/two' }
]

function project(
  id: string,
  path: string,
  repoRoot: string | null,
  host: string | null = null
): StatusProject {
  return {
    id,
    host,
    path,
    name: 'main',
    repo: '',
    repo_root: repoRoot,
    ok: true,
    epics: [],
    counts: { epics: 0, leaves: 0, blocked: 0 },
    agents: [],
    live: { working: 0, blocked: 0, waiting: 0, idle: 0, done: 0 },
    warnings: [],
    stale: false
  }
}

const checkout = project('ws-1', '/repo', '/repo')
const worktree = project('ws-2', '/repo/epic-7', '/repo')

test('focus: event id beats duplicate names', () => {
  const focused = pickFocused(duplicateNames, { id: 'ws-2' })
  assert.equal(focused?.id, 'ws-2')
})

test('focus: ambiguous name without event stays null', () => {
  const focused = pickFocused(duplicateNames, null, 'main')
  assert.equal(focused, null)
})

test('focus: terminal map resolves duplicate names', () => {
  const terminalMap = new Map([['t1', 'ws-2']])
  const focused = pickFocused(duplicateNames, null, 'main', ['t1'], terminalMap)
  assert.equal(focused?.id, 'ws-2')
})

test('agents: worktree focus maps to repo card', () => {
  const snapshots = [checkout, worktree]
  const deduped = dedupeProjects(snapshots, null)
  assert.deepEqual(
    deduped.map((item) => item.id),
    ['ws-1']
  )
  assert.equal(agentTarget(deduped, snapshots, 'ws-2'), 'ws-1')
})

test('agents: non-kit focus attaches nowhere', () => {
  const snapshots = [checkout, worktree]
  const deduped = dedupeProjects(snapshots, null)
  assert.equal(agentTarget(deduped, snapshots, 'ws-9'), null)
})

test('map: conflicting terminals stay ambiguous', () => {
  learnAgentTerminal({ workspaceId: 'ws-1', terminalId: 'conflict-t1' })
  learnAgentTerminal({ workspaceId: 'ws-2', terminalId: 'conflict-t2' })
  const focused = pickFocused(duplicateNames, null, 'main', [
    'conflict-t1',
    'conflict-t2'
  ])
  assert.equal(focused, null)
})

test('map: learned terminal resolves focus', () => {
  // Gerçek öğrenme yolu: agent.status.changed gövdesi -> harita -> odak.
  learnAgentTerminal({
    workspaceId: 'ws-2',
    terminalId: 'learned-t1',
    paneKey: 'pane-1',
    state: 'working',
    receivedAt: 1
  })
  const focused = pickFocused(duplicateNames, null, 'main', ['learned-t1'])
  assert.equal(focused?.id, 'ws-2')
})

test('map: relearned terminal survives eviction', () => {
  rememberTerminal('lru-t1', 'ws-1')
  for (let index = 0; index < 199; index += 1) {
    rememberTerminal(`lru-fill-${index}`, 'ws-1')
  }
  // Aynı terminal yeniden öğrenilince en yeni olmalı; dolgu ondan sonra düşer.
  rememberTerminal('lru-t1', 'ws-2')
  rememberTerminal('lru-last', 'ws-2')
  assert.deepEqual(terminalWorkspaceIds(['lru-t1']), ['ws-2'])
})

test('refresh: focus retry waits a second', () => {
  assert.equal(shouldRetryFocus(1_000, 0), true)
  assert.equal(shouldRetryFocus(1_001, 0), true)
  assert.equal(shouldRetryFocus(999, 0), false)
})

test('agents: other workspace event is ignored', () => {
  // Odak `ws-1`; olay `ws-2`'den: hiçbir kart tazelenmez.
  assert.equal(agentEventTarget('ws-2', 'ws-1'), 'ignore')
})

test('agents: null workspace triggers refresh', () => {
  // Olay workspace taşımıyor: eski odak yeniden kullanılmaz, tam tazeleme.
  assert.equal(agentEventTarget(null, 'ws-1'), 'refresh')
})

test('hosts: same path different host stays separate', () => {
  assert.notEqual(
    refKey({ hostId: 'a', path: '/repo' }),
    refKey({ hostId: 'b', path: '/repo' })
  )
  // Host kaydetmeyen kurulumlar: workspace id'sinin `::` ön eki ayırır.
  assert.notEqual(
    refKey({ hostId: null, id: 'abc::ws-1', path: '/repo' }),
    refKey({ hostId: null, id: 'def::ws-1', path: '/repo' })
  )
  // Aynı repo_root ve yol, farklı host: iki ayrı kart.
  const first = project('ws-1', '/repo', '/repo', 'host-a')
  const second = project('ws-2', '/repo', '/repo', 'host-b')
  assert.notEqual(projectKey(first), projectKey(second))
  assert.equal(dedupeProjects([first, second], null).length, 2)
  // Host alanı yok: id ön eki kartları ayırır, dedupe ikisini de tutar.
  const compositeFirst = project('abc::ws-1', '/repo', '/repo')
  const compositeSecond = project('def::ws-1', '/repo', '/repo')
  assert.notEqual(projectKey(compositeFirst), projectKey(compositeSecond))
  assert.equal(dedupeProjects([compositeFirst, compositeSecond], null).length, 2)
})

test('cache: other host entry is not served', () => {
  const entry = { project: project('ws-1', '/repo', '/repo', 'host-a') }
  assert.equal(cacheMatches(entry, { hostId: 'host-a', path: '/repo' }), true)
  assert.equal(cacheMatches(entry, { hostId: 'host-b', path: '/repo' }), false)
  // Host alanı yoksa id ön eki de eşleşmeli.
  assert.equal(cacheMatches(entry, { hostId: null, id: 'ws-1', path: '/repo' }), false)
  assert.equal(cacheMatches(null, { hostId: 'host-a', path: '/repo' }), false)
  const composite = { project: project('abc::ws-1', '/repo', '/repo') }
  assert.equal(
    cacheMatches(composite, { hostId: null, id: 'abc::ws-2', path: '/repo' }),
    true
  )
  assert.equal(
    cacheMatches(composite, { hostId: null, id: 'def::ws-2', path: '/repo' }),
    false
  )
})

test('config: normalized project path reuses the workspace', () => {
  const listed = [{ id: 'local::ws-1', name: 'main', path: '/repo' }]
  // Sondaki `/` yeni ref üretmez: aynı workspace, aynı anahtar.
  const match = matchWorkspacePath(listed, '/repo/')
  assert.equal(match?.id, 'local::ws-1')
  assert.equal(
    refKey({
      hostId: match?.hostId ?? null,
      id: match?.id ?? listed[0]?.id,
      path: '/repo/'
    }),
    refKey({ hostId: null, id: 'local::ws-1', path: '/repo' })
  )
  // Liste dışı bir yol sentetik ref'e düşer: tahmin yok.
  assert.equal(matchWorkspacePath(listed, '/other'), null)
})

test('config: symlinked project path reuses the workspace', () => {
  const root = mkdtempSync(join(os.tmpdir(), 'demir-kit-path-'))
  try {
    const real = join(root, 'real')
    const link = join(root, 'link')
    const otherReal = join(root, 'other')
    mkdirSync(real)
    mkdirSync(otherReal)
    symlinkSync(real, link, 'dir')
    const listed = [{ id: 'ws-1', name: 'main', path: real }]
    // Bağ üzerinden verilen ayar yolu da aynı workspace'i bulur.
    assert.equal(matchWorkspacePath(listed, link)?.id, 'ws-1')
    // `..` parçası da çözülür: bağ + `..` gerçek dizine döner.
    assert.equal(matchWorkspacePath(listed, join(link, '..', 'real'))?.id, 'ws-1')
    // Gerçekten var olan başka bir dizin eşleşmez (gerçek yollar farklı).
    assert.equal(matchWorkspacePath(listed, otherReal), null)
    // Diskte olmayan dizin de eşleşmez.
    assert.equal(matchWorkspacePath(listed, join(root, 'missing')), null)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})
