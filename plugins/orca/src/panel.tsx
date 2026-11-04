// No build step: Orca strips the types and compiles the JSX when the panel loads.
// CP-1 sürümü: yalnız başlık ve sayımlar; epic listesi sonraki checkpoint'te.
import { atom, Badge, Button, Heading, plugin, read, Row, set, Stack, Text, type PanelContext } from 'orca'
import type { StatusSnapshot } from './protocol'

const snapshot = atom<StatusSnapshot | null>(null)
const errorText = atom<string | null>(null)

async function load(): Promise<void> {
  try {
    const answer = await plugin.request('status.snapshot')
    set(snapshot, answer)
    set(errorText, null)
  } catch (error) {
    set(errorText, error instanceof Error ? error.message : String(error))
  }
}

/** Runs once before the first render; the request starts the worker if needed. */
export function setup(_ctx: PanelContext): void {
  void load()
}

export default function Panel() {
  const data = read(snapshot)
  const failure = read(errorText)

  return (
    <Stack gap="md">
      <Row justify="between">
        <Heading>demir-kit</Heading>
        <Button variant="ghost" onPress={() => void load()}>
          Yenile
        </Button>
      </Row>

      {failure !== null && <Text tone="danger">Hata: {failure}</Text>}

      {failure === null && data === null && <Text muted>Yükleniyor…</Text>}

      {failure === null && data !== null && !data.ok && (
        <Text tone="warning">veri yok: {data.error ?? data.warnings[0] ?? 'bilinmeyen hata'}</Text>
      )}

      {failure === null && data !== null && data.ok && (
        <Stack gap="sm">
          <Row gap="xs">
            <Badge tone="accent">epic {data.counts?.epics ?? 0}</Badge>
            <Badge tone="neutral">leaf {data.counts?.leaves ?? 0}</Badge>
            <Badge tone={data.counts?.blocked ? 'warning' : 'neutral'}>{data.counts?.blocked ?? 0} engel</Badge>
          </Row>
          <Text muted size="xs">
            {data.project ?? 'proje yolu yok'}
            {data.stale ? ' · eski veri' : ` · ${data.generated_at ?? ''}`}
          </Text>
        </Stack>
      )}

      {failure === null && data !== null && data.ok && data.epics.length === 0 && (
        <Text muted>Epic yok.</Text>
      )}
    </Stack>
  )
}
