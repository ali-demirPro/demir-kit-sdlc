// `orca plugin check` renders the panel once per scenario, each on a fresh host.
// `requests` stubs the panel's ask, so check draws the state without running python.
import { defineCheck } from 'orca/testing'

const snapshot = {
  ok: true,
  source: 'live',
  project: '/Users/ali/projeler/demir-kit',
  project_name: 'demir-kit',
  epics: [
    {
      number: 181,
      title: 'Epic: MCP yüzeyi + ince Orca plugin',
      state: 'executing',
      risk: 'low',
      checkpoints: { done: 2, total: 11 },
      gate: null
    },
    {
      number: 179,
      title: 'Epic: MCP kayıt ve güvenlik sınırı',
      state: 'epic-done',
      risk: null,
      checkpoints: { done: 3, total: 3 },
      gate: 'pass'
    }
  ],
  counts: { epics: 2, leaves: 5, blocked: 0 },
  stale: false,
  generated_at: '2026-11-04T10:00:00Z',
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
        ...snapshot,
        source: 'cache',
        epics: [],
        counts: { epics: 0, leaves: 0, blocked: 0 }
      }
    }
  }
})
