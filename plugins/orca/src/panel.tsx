// No build step: Orca strips the types and compiles the JSX when the panel loads.
// CP-2: portföy tablosu, 30 sn otomatik yenileme, boş ve hata durumları.
import {
  atom,
  Badge,
  Button,
  Callout,
  EmptyState,
  Heading,
  plugin,
  read,
  Row,
  set,
  Spinner,
  Stack,
  Table,
  Text,
  type PanelContext
} from 'orca'
import type { StatusEpic, StatusSnapshot } from './protocol'

/** Dashboard ile aynı pencere: 30 saniyede bir tazele. */
const REFRESH_MS = 30_000

const snapshot = atom<StatusSnapshot | null>(null)
const errorText = atom<string | null>(null)
const loading = atom<boolean>(false)

async function load(): Promise<void> {
  set(loading, true)
  try {
    const answer = await plugin.request('status.snapshot')
    set(snapshot, answer)
    set(errorText, null)
  } catch (error) {
    set(errorText, error instanceof Error ? error.message : String(error))
  } finally {
    set(loading, false)
  }
}

/** Runs once before the first render; the request starts the worker if needed. */
export function setup(ctx: PanelContext): void {
  void load()
  const timer = setInterval(() => void load(), REFRESH_MS)
  ctx.signal.addEventListener('abort', () => clearInterval(timer), { once: true })
}

function sourceTone(source: string): 'success' | 'warning' | 'neutral' {
  if (source === 'live') return 'success'
  if (source === 'cache') return 'warning'
  return 'neutral'
}

function cpText(epic: StatusEpic): string {
  const done = epic.checkpoints?.done
  const total = epic.checkpoints?.total
  if (typeof done !== 'number' || typeof total !== 'number') return '-'
  return `${done}/${total}`
}

function rowsOf(epics: readonly StatusEpic[]) {
  return epics
    .filter((epic) => typeof epic.number === 'number')
    .map((epic) => ({
      key: String(epic.number),
      cells: {
        epic: `#${epic.number}`,
        state: epic.state ?? '-',
        checkpoints: cpText(epic),
        gate: epic.gate ?? '-',
        risk: epic.risk ?? '-'
      }
    }))
}

const COLUMNS = [
  { key: 'epic', label: '#', width: 'xs' as const },
  { key: 'state', label: 'durum' },
  { key: 'checkpoints', label: 'CP', width: 'xs' as const },
  { key: 'gate', label: 'gate', width: 'xs' as const },
  { key: 'risk', label: 'risk', width: 'xs' as const }
]

export default function Panel() {
  const data = read(snapshot)
  const failure = read(errorText)
  const busy = read(loading)

  return (
    <Stack gap="md">
      <Row justify="between" align="start">
        <Stack gap="xs">
          <Heading>{data?.project_name ?? 'demir-kit'}</Heading>
          <Row gap="xs" wrap>
            {data !== null && <Badge tone={sourceTone(data.source)}>{data.source}</Badge>}
            {data?.stale === true && <Badge tone="warning">eski veri</Badge>}
          </Row>
          {data?.project != null && (
            <Text muted size="xs" truncate>
              {data.project}
            </Text>
          )}
        </Stack>
        <Button variant="ghost" icon="refresh" disabled={busy} onPress={() => void load()}>
          Yenile
        </Button>
      </Row>

      {failure !== null && (
        <Callout tone="danger" title="Durum okunamadı" icon="error">
          <Stack gap="xs">
            <Text tone="danger">{failure}</Text>
          </Stack>
        </Callout>
      )}

      {failure === null && data === null && (
        <Stack gap="sm">
          <Spinner label="Durum okunuyor" labelHidden />
          <Text muted>Yükleniyor…</Text>
        </Stack>
      )}

      {failure === null && data !== null && !data.ok && (
        <Callout tone="danger" title="Durum okunamadı" icon="error">
          <Stack gap="xs">
            <Text tone="danger">{data.error ?? 'bilinmeyen hata'}</Text>
            {data.warnings.slice(0, 3).map((warning) => (
              <Text key={warning} muted size="xs">
                {warning}
              </Text>
            ))}
          </Stack>
        </Callout>
      )}

      {failure === null && data !== null && data.ok && data.epics.length === 0 && (
        <EmptyState
          title="demir-kit bulunamadı"
          description="Ayarlar › demir-kit › Proje yolu (projectPath) alanına kit kökünü yaz."
          icon="puzzle"
        />
      )}

      {failure === null && data !== null && data.ok && data.epics.length > 0 && (
        <Stack gap="sm">
          <Row gap="xs" wrap>
            <Badge tone="accent">epic {data.counts?.epics ?? data.epics.length}</Badge>
            <Badge tone="neutral">leaf {data.counts?.leaves ?? 0}</Badge>
            <Badge tone={data.counts?.blocked ? 'warning' : 'neutral'}>{data.counts?.blocked ?? 0} engel</Badge>
          </Row>
          <Table label="Epic listesi" columns={COLUMNS} rows={rowsOf(data.epics)} selectionMode="none" />
          <Text muted size="xs">
            {data.generated_at ?? ''}
          </Text>
        </Stack>
      )}
    </Stack>
  )
}
