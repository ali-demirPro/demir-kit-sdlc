// Eval özeti saf yardımcıyla sınanır: python ya da gerçek kit yok.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { evalText, isCount, isRate } from './eval'
import type { StatusEvaluations } from './protocol'

function evaluations(overrides: Partial<StatusEvaluations> = {}): StatusEvaluations {
  return {
    batch: '2026-11-08',
    cases_pass: 12,
    cases_total: 14,
    discovery_rate: 0.8,
    findings: { friction: 3, objection: 0, opportunity: 0 },
    updated_at: '2026-11-08T10:00:00Z',
    ...overrides
  }
}

test('eval: dolu alanlar birebir tek satır', () => {
  assert.equal(evalText(evaluations()), 'eval 12/14 · discovery %80 · 3 friction')
})

test('eval: sıfır bulgular satıra girmez', () => {
  assert.equal(
    evalText(
      evaluations({
        findings: { friction: 0, objection: 0, opportunity: 0 }
      })
    ),
    'eval 12/14 · discovery %80'
  )
})

test('eval: eksik alan atlanır, kalanlar çizilir', () => {
  // ADV-11: kısmi null — `cases_total` null iken `eval 12/undefined` sızmaz.
  assert.equal(
    evalText(
      evaluations({
        cases_total: null,
        discovery_rate: null,
        findings: { friction: 3, objection: null, opportunity: null }
      })
    ),
    '3 friction'
  )
  assert.equal(
    evalText(evaluations({ cases_pass: null })),
    'discovery %80 · 3 friction'
  )
  assert.equal(evalText(evaluations({ discovery_rate: null })), 'eval 12/14 · 3 friction')
})

test('eval: bulgu sırası sabit ve tam dize', () => {
  assert.equal(
    evalText(
      evaluations({
        findings: { friction: 1, objection: 2, opportunity: 3 }
      })
    ),
    'eval 12/14 · discovery %80 · 1 friction · 2 objection · 3 opportunity'
  )
})

test('eval: tümü null ise satır yok', () => {
  assert.equal(
    evalText({
      batch: null,
      cases_pass: null,
      cases_total: null,
      discovery_rate: null,
      findings: { friction: null, objection: null, opportunity: null },
      updated_at: null
    }),
    null
  )
})

test('eval: alan yok ya da null ise satır yok', () => {
  assert.equal(evalText(undefined), null)
  assert.equal(evalText(null), null)
})

test('eval: sözleşme dışı sayılar atlanır', () => {
  // ADV-13: negatif/ondalık sayı ve 0..1 dışı oran çizilmez.
  assert.equal(
    evalText(
      evaluations({
        cases_pass: -1,
        cases_total: 14,
        discovery_rate: -0.5,
        findings: { friction: 2.5, objection: -1, opportunity: 1 }
      })
    ),
    '1 opportunity'
  )
  assert.equal(
    evalText(
      evaluations({
        cases_pass: 12.5,
        cases_total: 14,
        discovery_rate: 1.5,
        findings: { friction: 3, objection: 0, opportunity: 0 }
      })
    ),
    '3 friction'
  )
  assert.equal(evalText(evaluations({ discovery_rate: 1 })), 'eval 12/14 · discovery %100 · 3 friction')
})

test('eval: taban kontrolleri', () => {
  assert.equal(isCount(0), true)
  assert.equal(isCount(-1), false)
  assert.equal(isCount(1.5), false)
  assert.equal(isCount(null), false)
  assert.equal(isRate(0), true)
  assert.equal(isRate(1), true)
  assert.equal(isRate(-0.1), false)
  assert.equal(isRate(1.1), false)
  assert.equal(isRate(Number.NaN), false)
})
