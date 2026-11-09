// Saf eval yardımcıları: panel yalnız buradan okur, `node:test` aynı biçimi çalıştırır.
import type { StatusEvaluations } from './protocol'

/**
 * Sayı mı ve sözleşme tabanında mı? `null`, eksik, negatif ve ondalık değer
 * satıra girmez; producer'ın normalizasyonu panelde de uygulanır.
 */
export function isCount(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

/** Oran `0..1` aralığında sonlu sayı mı? Aralık dışı parça atlanır. */
export function isRate(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
}

/**
 * Eval özeti: `eval 12/14 · discovery %80 · 3 friction`.
 * Parça yalnız dolu alanlardan oluşur; hiç parça yoksa satır çizilmez (`null`).
 * Eski `status.py` alanı taşımaz, üretici `null` da gönderebilir: satır yok.
 */
export function evalText(evaluations?: StatusEvaluations | null): string | null {
  if (evaluations === undefined || evaluations === null) return null

  const parts: string[] = []
  const pass = evaluations.cases_pass
  const total = evaluations.cases_total
  if (isCount(pass) && isCount(total)) parts.push(`eval ${pass}/${total}`)

  const rate = evaluations.discovery_rate
  if (isRate(rate)) parts.push(`discovery %${Math.round(rate * 100)}`)

  // Sabit sıra; yalnız sıfırdan büyük sayılar yazılır.
  const findings: Array<[number | null | undefined, string]> = [
    [evaluations.findings?.friction, 'friction'],
    [evaluations.findings?.objection, 'objection'],
    [evaluations.findings?.opportunity, 'opportunity']
  ]
  for (const [count, label] of findings) {
    if (isCount(count) && count > 0) parts.push(`${count} ${label}`)
  }

  return parts.length === 0 ? null : parts.join(' · ')
}
