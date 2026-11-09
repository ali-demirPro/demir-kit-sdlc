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
  next_action: 'CP-2 panel detayı',
  // Dolu eval: satır `eval 12/14 · discovery %80 · 3 friction` olur; sıfır
  // bulgular (objection/opportunity) satıra girmez.
  evaluations: {
    batch: '2026-11-08',
    cases_pass: 12,
    cases_total: 14,
    discovery_rate: 0.8,
    findings: { friction: 3, objection: 0, opportunity: 0 },
    updated_at: '2026-11-08T10:00:00Z'
  }
}

/** Eval kaydı yok: her alan `null`; detayda satır çizilmez, panel çökmez. */
const emptyEvaluationsEpic = {
  number: 189,
  title: 'Epic: eval kaydı yok',
  state: 'executing',
  risk: 'low',
  checkpoints: [],
  updated_at: null,
  url: null,
  leaves: [],
  gate: null,
  approvals: { agent_approved: false, human_qa: false },
  next_action: null,
  evaluations: {
    batch: null,
    cases_pass: null,
    cases_total: null,
    discovery_rate: null,
    findings: { friction: null, objection: null, opportunity: null },
    updated_at: null
  }
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
      epics: [epicDetail, emptyEvaluationsEpic],
      counts: { epics: 2, leaves: 3, blocked: 0 },
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

/** Aynı adlı iki kit workspace: odak ikincisi; "odak" rozeti ikinci kartta kalmalı. */
const sameNameSnapshot = {
  ok: true,
  generated_at: '2026-11-04T10:00:00Z',
  focused: 'ws-ikinci',
  projects: [
    {
      id: 'ws-birinci',
      path: '/Users/ali/projeler/birinci',
      name: 'main',
      repo: 'ali-demirPro/birinci',
      repo_root: '/Users/ali/projeler/birinci',
      ok: true,
      epics: [],
      counts: { epics: 0, leaves: 0, blocked: 0 },
      agents: [],
      live: { working: 0, blocked: 0, waiting: 0, idle: 0, done: 0 },
      warnings: [],
      stale: false
    },
    {
      id: 'ws-ikinci',
      path: '/Users/ali/projeler/ikinci',
      name: 'main',
      repo: 'ali-demirPro/ikinci',
      repo_root: '/Users/ali/projeler/ikinci',
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

/** Odak çözülemezse yanlış karta rozet basılmaz; nötr bilgi satırı çizilir. */
const focusMissingSnapshot = {
  ok: true,
  generated_at: '2026-11-05T10:00:00Z',
  focused: null,
  focusSource: 'none',
  live: { working: 1, blocked: 0, waiting: 0, idle: 0, done: 0 },
  active: { projects: 1, epics: 1, leaves: 1 },
  projects: [
    {
      id: 'ws-nombo',
      path: '/Users/ali/projeler/nombo',
      name: 'main',
      repo: 'ali-demirPro/nombo',
      repo_root: '/Users/ali/projeler/nombo',
      ok: true,
      epics: [
        {
          number: 4,
          title: 'Epic: UI gate',
          state: 'executing',
          risk: 'medium',
          checkpoints: [],
          updated_at: null,
          url: null,
          leaves: [{ number: 1, title: 'Leaf: harness', state: 'executing' }],
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
    }
  ],
  warnings: ['odak çözülemedi']
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
    // `evaluations` alanı yok: eval satırı çizilmez, panel çökmez.
    persisted: {
      plugin: {
        view: { kind: 'detail', projectId: 'ws-demir-kit', epicNumber: 188 }
      }
    },
    requests: { 'status.snapshot': legacySnapshot }
  },
  evalEmpty: {
    ...quietWorker,
    // Tüm eval alanları null: detay satır çizmez.
    persisted: {
      plugin: {
        view: { kind: 'detail', projectId: 'ws-demir-kit', epicNumber: 189 }
      }
    },
    requests: { 'status.snapshot': snapshot }
  },
  sameName: {
    ...quietWorker,
    // Aynı `name`, farklı `id`: rozet yalnız odaklı ikinci kartta görünür.
    requests: { 'status.snapshot': sameNameSnapshot }
  },
  focusMissing: {
    ...quietWorker,
    // Odak yok: canlı/aktif özet nötr satırda, hiçbir kartta "odak" rozeti yok.
    requests: { 'status.snapshot': focusMissingSnapshot }
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
