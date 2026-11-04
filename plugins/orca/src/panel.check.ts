// `orca plugin check` renders the panel once per scenario, each on a fresh host.
// `requests` stubs the panel's ask, so check draws the state without running python.
import { defineCheck } from 'orca/testing'

const epicDetail = {
  number: 185,
  title: 'Epic: çok projeli panel',
  state: 'executing',
  risk: 'low',
  checkpoints: [
    { id: 'CP-1', title: 'status ve sözleşme', done: true, leaf: 183 },
    { id: 'CP-2', title: 'panel detayı', done: false, leaf: 184 }
  ],
  updated_at: '2026-11-04T10:00:00Z',
  url: 'https://github.com/ali-demirPro/demir-kit-sdlc/issues/185',
  leaves: [
    { number: 184, title: 'Leaf: status + plugin', state: 'executing' },
    { number: 183, title: 'Leaf: onay bekleyen', state: 'agent-approved' },
    { number: 182, title: 'Leaf: biten checkpoint', state: 'leaf-done' }
  ],
  gate: null,
  approvals: { agent_approved: true, human_qa: true },
  next_action: 'CP-2 panel detayı'
}

const snapshot = {
  ok: true,
  generated_at: '2026-11-04T10:00:00Z',
  focused: 'ws-demir-kit',
  projects: [
    {
      id: 'ws-demir-kit',
      path: '/Users/ali/projeler/demir-kit',
      name: 'demir-kit',
      repo: 'ali-demirPro/demir-kit-sdlc',
      repo_root: '/Users/ali/projeler/demir-kit',
      ok: true,
      epics: [epicDetail],
      counts: { epics: 1, leaves: 3, blocked: 0 },
      agents: [
        { terminalId: 't1', title: 'claude/main', state: 'working' },
        { terminalId: 't2', title: 'codex/review', state: 'working' },
        { terminalId: 't3', title: 'claude/leaf-187', state: 'blocked' }
      ],
      live: { working: 2, blocked: 1, waiting: 0, idle: 1, done: 0 },
      warnings: [],
      stale: false
    },
    {
      id: 'ws-urun',
      path: '/Users/ali/projeler/urun',
      name: 'urun',
      repo: 'ali-demirPro/urun',
      ok: true,
      epics: [
        {
          number: 24,
          title: 'Epic: ilk sürüm',
          state: 'intake',
          risk: 'medium',
          checkpoints: [
            { id: 'CP-1', title: 'iskele', done: false, leaf: 25 },
            { id: 'CP-2', title: 'ilk ekran', done: false, leaf: 25 }
          ],
          updated_at: null,
          url: 'https://github.com/ali-demirPro/urun/issues/24',
          leaves: [{ number: 25, title: 'Leaf: iskele', state: 'intake' }],
          gate: null,
          approvals: { agent_approved: false, human_qa: false },
          next_action: null
        }
      ],
      counts: { epics: 1, leaves: 1, blocked: 0 },
      agents: [],
      live: { working: 0, blocked: 0, waiting: 0, idle: 0, done: 0 },
      warnings: [],
      stale: false
    },
    {
      id: 'ws-bos',
      path: '/Users/ali/projeler/bos',
      name: 'bos',
      repo: 'ali-demirPro/bos',
      ok: true,
      epics: [],
      counts: { epics: 0, leaves: 0, blocked: 0 },
      agents: [],
      live: { working: 0, blocked: 0, waiting: 0, idle: 0, done: 0 },
      warnings: [],
      stale: false
    }
  ],
  warnings: []
}

/** No result for `workspace.list` would leave the worker's own error in the log. */
const quietWorker = { results: { 'workspace.list': { workspaces: [] } } }

/** Eski `status.py` biçimi: `checkpoints` dizi değil `{done,total}`; panel çökmemeli. */
const legacySnapshot = {
  ok: true,
  generated_at: '2026-11-04T10:00:00Z',
  focused: 'ws-demir-kit',
  projects: [
    {
      id: 'ws-demir-kit',
      path: '/Users/ali/projeler/demir-kit',
      name: 'demir-kit',
      ok: true,
      epics: [
        {
          number: 188,
          title: 'Epic: eski şekil',
          state: 'executing',
          risk: 'low',
          checkpoints: { done: 1, total: 2 },
          updated_at: 'dün',
          url: null,
          leaves: [],
          gate: null,
          approvals: { agent_approved: false, human_qa: false },
          next_action: null
        }
      ],
      counts: { epics: 1, leaves: 0, blocked: 0 },
      agents: [],
      live: { working: 0, blocked: 0, waiting: 0, idle: 0, done: 0 },
      warnings: [],
      stale: false
    }
  ],
  warnings: []
}

export default defineCheck({
  fresh: {
    ...quietWorker,
    requests: { 'status.snapshot': snapshot }
  },
  detail: {
    ...quietWorker,
    // Düz detay: kalıcı görünüm doğrudan epic detayını başlatır.
    persisted: {
      plugin: {
        view: { kind: 'detail', projectId: 'ws-demir-kit', epicNumber: 185 }
      }
    },
    requests: { 'status.snapshot': snapshot }
  },
  legacy: {
    ...quietWorker,
    // Eski şekilli checkpoint'ler detayda da açık: CP listesi boş kalır.
    persisted: {
      plugin: {
        view: { kind: 'detail', projectId: 'ws-demir-kit', epicNumber: 188 }
      }
    },
    requests: { 'status.snapshot': legacySnapshot }
  },
  empty: {
    ...quietWorker,
    requests: {
      'status.snapshot': {
        ok: false,
        code: 'no-kit',
        generated_at: '2026-11-04T10:00:00Z',
        focused: null,
        projects: [],
        warnings: ['demir-kit bulunamadı'],
        error: 'demir-kit bulunamadı'
      }
    }
  }
})
