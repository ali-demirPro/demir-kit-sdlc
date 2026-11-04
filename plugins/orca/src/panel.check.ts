// `orca plugin check` renders the panel once per scenario, each on a fresh host.
// `requests` stubs the panel's ask, so check draws the state without running python.
import { defineCheck } from 'orca/testing'

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
      epics: [
        {
          number: 185,
          title: 'Epic: çok projeli panel',
          state: 'executing',
          risk: 'low',
          checkpoints: { done: 1, total: 2 },
          leaves: [
            { number: 184, title: 'Leaf: status + plugin', state: 'executing' },
            { number: 182, title: 'Leaf: biten checkpoint', state: 'leaf-done' }
          ],
          gate: null
        }
      ],
      counts: { epics: 1, leaves: 2, blocked: 0 },
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
          checkpoints: { done: 0, total: 4 },
          leaves: [{ number: 25, title: 'Leaf: iskele', state: 'intake' }],
          gate: null
        }
      ],
      counts: { epics: 1, leaves: 1, blocked: 0 },
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
      warnings: [],
      stale: false
    }
  ],
  warnings: []
}

/** No result for `workspace.list` would leave the worker's own error in the log. */
const quietWorker = { results: { 'workspace.list': { workspaces: [] } } }

export default defineCheck({
  fresh: {
    ...quietWorker,
    requests: { 'status.snapshot': snapshot }
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
