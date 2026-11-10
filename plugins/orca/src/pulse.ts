// Süreç nabzı yardımcıları: saf fonksiyonlar, `node:test` ile sınanır.
// Panel ve işçi aynı biçimi paylaşsın diye metin/özet burada üretilir.
import type {
  FleetPulse,
  StatusEpic,
  StatusLeaf,
  StatusMachinery,
  StatusProject,
  StatusPulse,
  StatusPulseLead
} from './protocol'

/** Dar kenar çubuğu için unicode sparkline; SVG gerekmez. */
const SPARK = '▁▂▃▄▅▆▇█'
/** Filo özetinde taşınan en fazla örnek; sözleşme de 200'de kırpar. */
export const SAMPLE_CAP = 200

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** Negatif olmayan değerlerden tek satır sparkline; veri yoksa boş metin. */
export function sparkline(values: readonly number[]): string {
  const clean = values.filter((value) => finite(value) && value >= 0)
  if (clean.length === 0) return ''
  const max = Math.max(...clean)
  if (max === 0) return SPARK[0].repeat(clean.length)
  return clean
    .map((value) => {
      const index = Math.round((value / max) * (SPARK.length - 1))
      return SPARK[Math.max(0, Math.min(SPARK.length - 1, index))]
    })
    .join('')
}

/** Toplam; hiç ölçüm yoksa `null` (sıfır uydurulmaz). */
export function sumKnown(values: readonly (number | null | undefined)[]): number | null {
  const known = values.filter(finite)
  if (known.length === 0) return null
  return known.reduce((total, value) => total + value, 0)
}

/** Nearest-rank yüzdelik; örnek yoksa `null`. */
export function percentile(samples: readonly number[], share: number): number | null {
  const clean = samples.filter(finite).slice().sort((left, right) => left - right)
  if (clean.length === 0) return null
  const index = Math.max(0, Math.min(clean.length - 1, Math.ceil(share * clean.length) - 1))
  return Math.round(clean[index] * 10) / 10
}

/** Günlük serileri sondan hizalar; pencere farklıysa en yenisi ortak kalır. */
function sumDaily(pulses: readonly StatusPulse[]): number[] {
  const width = Math.max(0, ...pulses.map((pulse) => pulse.daily?.length ?? 0))
  const total = new Array<number>(width).fill(0)
  for (const pulse of pulses) {
    const daily = pulse.daily ?? []
    daily.forEach((value, index) => {
      if (!finite(value)) return
      const target = width - daily.length + index
      if (target >= 0) total[target] += value
    })
  }
  return total
}

function leadOf(samples: readonly number[]): StatusPulseLead {
  const clean = samples.filter(finite).slice().sort((left, right) => left - right)
  return {
    n: clean.length,
    p50: percentile(clean, 0.5),
    p90: percentile(clean, 0.9),
    samples: clean.slice(-SAMPLE_CAP)
  }
}

/**
 * Filo nabzı: proje nabızlarının toplamı. Toplama yalnız ölçüm taşıyan
 * projelerden yapılır; kaç projenin ölçüldüğü `projects` alanında durur ve
 * eksik varsa `partial: true` olur. Aynı repo dedupe'si işçide; burada yok.
 */
export function fleetPulse(projects: readonly StatusProject[]): FleetPulse | null {
  const measured = projects
    .map((project) => project.pulse ?? null)
    .filter((pulse): pulse is StatusPulse => pulse !== null && pulse.status === 'ok')
  if (measured.length === 0) return null
  const samples = measured.flatMap((pulse) => pulse.lead?.samples ?? [])
  return {
    projects: measured.length,
    partial: measured.length < projects.length,
    window_days: Math.max(...measured.map((pulse) => pulse.window_days)),
    leaves_done: sumKnown(measured.map((pulse) => pulse.leaves_done)),
    prev_delta: sumKnown(measured.map((pulse) => pulse.prev_delta)),
    gates: sumKnown(measured.map((pulse) => pulse.gates)),
    gate_failures: sumKnown(measured.map((pulse) => pulse.gate_failures)),
    review_rounds: sumKnown(measured.map((pulse) => pulse.review_rounds)),
    blocked: sumKnown(measured.map((pulse) => pulse.blocked)),
    deferred: sumKnown(measured.map((pulse) => pulse.deferred)),
    daily: sumDaily(measured),
    lead: leadOf(samples)
  }
}

/** Pencere metni: `7g · 11 leaf ↑3 · 47 gate · 4 düşen · 2 engel`. */
export function pulseLine(pulse?: StatusPulse | null): string | null {
  if (pulse === null || pulse === undefined || pulse.status !== 'ok') return null
  const parts = [`${pulse.window_days}g`, `${pulse.leaves_done ?? '-'} leaf`]
  const delta = pulse.prev_delta
  if (finite(delta) && delta !== 0) {
    parts.push(delta > 0 ? `↑${delta}` : `↓${Math.abs(delta)}`)
  }
  parts.push(`${pulse.gates ?? '-'} gate`)
  if (finite(pulse.gate_failures) && pulse.gate_failures > 0) {
    parts.push(`${pulse.gate_failures} düşen`)
  }
  const prevented = (pulse.blocked ?? 0) + (pulse.deferred ?? 0)
  if (prevented > 0) parts.push(`${prevented} engel`)
  return parts.join(' · ')
}

/** Filo şeridi: `3 proje · 7g · 11 leaf ↑3 · 47 gate · 4 düşen`. */
export function fleetLine(pulse?: FleetPulse | null): string | null {
  if (pulse === null || pulse === undefined) return null
  const parts = [
    pulse.partial ? `${pulse.projects} proje ölçüldü` : `${pulse.projects} proje`,
    `${pulse.window_days}g`,
    `${pulse.leaves_done ?? '-'} leaf`
  ]
  const delta = pulse.prev_delta
  if (finite(delta) && delta !== 0) {
    parts.push(delta > 0 ? `↑${delta}` : `↓${Math.abs(delta)}`)
  }
  parts.push(`${pulse.gates ?? '-'} gate`)
  if (finite(pulse.gate_failures) && pulse.gate_failures > 0) {
    parts.push(`${pulse.gate_failures} düşen`)
  }
  if (pulse.lead?.p50 !== null && pulse.lead?.p50 !== undefined) {
    parts.push(`lead ${pulse.lead.p50} dk`)
  }
  return parts.join(' · ')
}

/** Epic süreç karnesi: `gate 44 (7 düşen) · review 3 · lead 89.9 dk · engel 0`. */
export function machineryLine(machinery?: StatusMachinery | null): string | null {
  if (machinery === null || machinery === undefined) return null
  const failures =
    machinery.gate_failures > 0 ? ` (${machinery.gate_failures} düşen)` : ''
  const lead = machinery.lead_minutes === null ? '-' : machinery.lead_minutes
  return [
    `gate ${machinery.gate_runs}${failures}`,
    `review ${machinery.review_rounds}`,
    `lead ${lead} dk`,
    `engel ${machinery.prevented}`
  ].join(' · ')
}

export type LeafGroup = 'bitti' | 'devam' | 'sırada'

/** Leaf durumunu üç gruba indirger: biten, yürüyen, sırada. */
export function leafGroup(state?: string): LeafGroup {
  if (state === 'leaf-done' || state === 'epic-done' || state === 'closed') return 'bitti'
  if (state === 'executing' || state === 'blocked' || state === 'epic-reconcile') {
    return 'devam'
  }
  return 'sırada'
}

export interface LeafBucket {
  group: LeafGroup
  leaves: StatusLeaf[]
}

/** Üç grup, sabit sırada; boş grup atlanır. Girişteki sıra gruplar içinde korunur. */
export function groupLeaves(leaves: readonly StatusLeaf[] | undefined): LeafBucket[] {
  const buckets: LeafBucket[] = [
    { group: 'bitti', leaves: [] },
    { group: 'devam', leaves: [] },
    { group: 'sırada', leaves: [] }
  ]
  for (const leaf of leaves ?? []) {
    const bucket = buckets.find((item) => item.group === leafGroup(leaf.state))
    if (bucket !== undefined) bucket.leaves.push(leaf)
  }
  return buckets.filter((bucket) => bucket.leaves.length > 0)
}

/** Epic satırındaki canlı pano: `3 bitti · 1 devam · 2 sırada`; hepsi boşsa null. */
export function groupCountText(leaves: readonly StatusLeaf[] | undefined): string | null {
  const buckets = groupLeaves(leaves)
  if (buckets.length === 0) return null
  return buckets.map((bucket) => `${bucket.leaves.length} ${bucket.group}`).join(' · ')
}

/** Epic başına biten leaf sayısı; `counts.leaves` aktif toplamı verir. */
export function doneLeaves(epic: StatusEpic): number {
  return (epic.leaves ?? []).filter((leaf) => leafGroup(leaf.state) === 'bitti').length
}
