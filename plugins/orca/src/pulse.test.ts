// Süreç nabzı saf yardımcıları: python, ağ ya da gerçek kit yok.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  fleetLine,
  fleetPulse,
  groupCountText,
  groupLeaves,
  leafGroup,
  machineryLine,
  percentile,
  pulseLine,
  sparkline,
  sumKnown
} from './pulse'
import type { StatusProject, StatusPulse } from './protocol'

function pulse(overrides: Partial<StatusPulse> = {}): StatusPulse {
  return {
    status: 'ok',
    window_days: 7,
    leaves_done: 11,
    prev_delta: 3,
    gates: 47,
    gate_failures: 4,
    review_rounds: 9,
    blocked: 2,
    deferred: 0,
    daily: [1, 0, 2, 3, 1, 2, 2],
    lead: { n: 3, p50: 20, p90: 40, samples: [10, 20, 40] },
    ...overrides
  }
}

function project(id: string, value: StatusPulse | null): StatusProject {
  return {
    id,
    path: `/tmp/${id}`,
    name: id,
    ok: true,
    epics: [],
    counts: { epics: 0, leaves: 0, blocked: 0 },
    warnings: [],
    stale: false,
    pulse: value
  }
}

test('sparkline: boş ve sıfır seri güvenli', () => {
  assert.equal(sparkline([]), '')
  assert.equal(sparkline([-1, Number.NaN]), '')
  assert.equal(sparkline([0, 0]), '▁▁')
  assert.equal(sparkline([1, 2, 3]).length, 3)
})

test('sumKnown: ölçüm yoksa null, karışıkta yalnız bilineni toplar', () => {
  assert.equal(sumKnown([null, undefined]), null)
  assert.equal(sumKnown([1, null, 2]), 3)
})

test('percentile: nearest-rank ve tek örnek', () => {
  assert.equal(percentile([], 0.5), null)
  assert.equal(percentile([10], 0.9), 10)
  assert.equal(percentile([10, 20, 30], 0.5), 20)
  assert.equal(percentile([10, 20, 30], 0.9), 30)
})

test('fleetPulse: nabız yoksa null', () => {
  assert.equal(fleetPulse([project('a', null)]), null)
  assert.equal(fleetPulse([]), null)
})

test('fleetPulse: iki proje birebir toplanır, eksik proje partial işaretler', () => {
  const fleet = fleetPulse([
    project('a', pulse()),
    project('b', pulse({ leaves_done: 4, gates: 3, blocked: 1, daily: [0, 0, 1, 0, 0, 0, 3] }))
  ])
  assert.equal(fleet?.projects, 2)
  assert.equal(fleet?.partial, false)
  assert.equal(fleet?.leaves_done, 15)
  assert.equal(fleet?.gates, 50)
  assert.equal(fleet?.blocked, 3)
  assert.deepEqual(fleet?.daily, [1, 0, 3, 3, 1, 2, 5])
  assert.equal(fleet?.lead.n, 6)

  const partial = fleetPulse([project('a', pulse()), project('b', null)])
  assert.equal(partial?.projects, 1)
  assert.equal(partial?.partial, true)
  assert.match(fleetLine(partial) ?? '', /1 proje ölçüldü/)
})

test('fleetPulse: kısa seri sondan hizalanır', () => {
  const fleet = fleetPulse([
    project('a', pulse({ daily: [5, 5] })),
    project('b', pulse({ daily: [1, 1, 1, 1] }))
  ])
  assert.deepEqual(fleet?.daily, [1, 1, 6, 6])
})

test('pulseLine: yok ise null, dolu ise tek satır', () => {
  assert.equal(pulseLine(null), null)
  assert.equal(pulseLine(undefined), null)
  assert.equal(pulseLine(pulse({ status: 'missing' })), null)
  assert.equal(pulseLine(pulse()), '7g · 11 leaf · ↑3 · 47 gate · 4 düşen · 2 engel')
  assert.equal(pulseLine(pulse({ prev_delta: -2 })), '7g · 11 leaf · ↓2 · 47 gate · 4 düşen · 2 engel')
  assert.equal(pulseLine(pulse({ gate_failures: 0, blocked: 0 })), '7g · 11 leaf · ↑3 · 47 gate')
})

test('fleetLine: proje sayısı, pencere ve lead', () => {
  const fleet = fleetPulse([project('a', pulse())])
  assert.equal(fleetLine(fleet), '1 proje · 7g · 11 leaf · ↑3 · 47 gate · 4 düşen · lead 20 dk')
  assert.equal(fleetLine(null), null)
})

test('machineryLine: gate/review/lead/engel', () => {
  assert.equal(machineryLine(null), null)
  assert.equal(
    machineryLine({
      gate_runs: 44,
      gate_failures: 7,
      review_rounds: 3,
      leaves_done: 2,
      blocked: 1,
      deferred: 1,
      lead_minutes: 89.9,
      prevented: 2
    }),
    'gate 44 (7 düşen) · review 3 · lead 89.9 dk · engel 2'
  )
  assert.match(
    machineryLine({
      gate_runs: 1,
      gate_failures: 0,
      review_rounds: 0,
      leaves_done: 0,
      blocked: 0,
      deferred: 0,
      lead_minutes: null,
      prevented: 0
    }) ?? '',
    /lead - dk · engel 0/
  )
})

test('leafGroup: bitti/devam/sırada eşlemesi', () => {
  assert.equal(leafGroup('leaf-done'), 'bitti')
  assert.equal(leafGroup('closed'), 'bitti')
  assert.equal(leafGroup('executing'), 'devam')
  assert.equal(leafGroup('blocked'), 'devam')
  assert.equal(leafGroup('agent-approved'), 'sırada')
  assert.equal(leafGroup('intake'), 'sırada')
  assert.equal(leafGroup(undefined), 'sırada')
})

test('groupLeaves: sabit grup sırası, boş grup atlanır', () => {
  const buckets = groupLeaves([
    { number: 1, title: 'a', state: 'intake' },
    { number: 2, title: 'b', state: 'leaf-done' },
    { number: 3, title: 'c', state: 'executing' },
    { number: 4, title: 'd', state: 'closed' }
  ])
  assert.deepEqual(
    buckets.map((bucket) => [bucket.group, bucket.leaves.map((leaf) => leaf.number)]),
    [
      ['bitti', [2, 4]],
      ['devam', [3]],
      ['sırada', [1]]
    ]
  )
  assert.equal(groupCountText([{ number: 1, state: 'intake' }]), '1 sırada')
  assert.equal(groupCountText([]), null)
  assert.equal(groupCountText(undefined), null)
})
