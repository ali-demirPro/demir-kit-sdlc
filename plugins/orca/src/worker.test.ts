// Odak çözümü ve ajan kartı saf yardımcılarla sınanır: python ya da gerçek kit yok.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { StatusProject } from './protocol'
import {
  agentTarget,
  dedupeProjects,
  learnAgentTerminal,
  pickFocused,
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
  repoRoot: string | null
): StatusProject {
  return {
    id,
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
