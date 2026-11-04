// No build step: Orca strips the types and compiles the JSX when the panel loads.
// CP-2: çok projeli portföy, epic/leaf başlıkları, tıklayınca workspace açma.
import {
  atom,
  Badge,
  Button,
  Callout,
  Card,
  EmptyState,
  Heading,
  List,
  ListItem,
  plugin,
  read,
  Row,
  set,
  Spinner,
  Stack,
  Text,
  type PanelContext
} from 'orca'
import type {
  StatusEpic,
  StatusLeaf,
  StatusProject,
  StatusSnapshot
} from './protocol'

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

/** Yolun son iki parçası; uzunsa başı `…` ile kısalır. */
function shortPath(path: string): string {
  const parts = path.split('/').filter(Boolean)
  if (parts.length <= 3) return path
  return `…/${parts.slice(-2).join('/')}`
}

/** Kart başlığı: `owner/repo`, yoksa proje adı. */
function projectTitle(project: StatusProject): string {
  const repo = (project.repo ?? '').trim()
  return repo !== '' ? repo : project.name
}

/** Panelde yalnız aktif iş sayılır: status.py kapanmış epic'leri zaten atlar. */
function countsText(project: StatusProject): string {
  const epics = project.counts?.epics ?? 0
  const leaves = project.counts?.leaves ?? 0
  return `epic ${epics} · leaf ${leaves}`
}

function cpText(epic: StatusEpic): string {
  const done = epic.checkpoints?.done
  const total = epic.checkpoints?.total
  if (typeof done !== 'number' || typeof total !== 'number') return '-'
  return `${done}/${total}`
}

function gateTone(gate: StatusEpic['gate']): 'success' | 'danger' | 'neutral' {
  if (gate === 'pass') return 'success'
  if (gate === 'fail') return 'danger'
  return 'neutral'
}

function epicTitle(epic: StatusEpic): string {
  return `#${epic.number} — ${epic.title ?? ''}`
}

function leafTitle(leaf: StatusLeaf): string {
  return `#${leaf.number} — ${leaf.title ?? ''} · ${leaf.state ?? '-'}`
}

/** Epic veya leaf satırı: o projenin workspace'ini göster.
 * Panel host'a doğrudan gitmez: istek işçiye gider, `workspace.open`'ı işçi çağırır.
 */
function openWorkspace(project: StatusProject): void {
  void plugin
    .request('workspace.open', { id: project.id })
    .catch((error: unknown) => {
      console.error(`demir-kit: workspace.open başarısız: ${String(error)}`)
    })
}

function ProjectGroup({
  project,
  focused
}: {
  project: StatusProject
  focused: boolean
}) {
  return (
    <Card title={projectTitle(project)} description={shortPath(project.path)}>
      <Stack gap="sm">
        <Row gap="xs" wrap>
          {focused && <Badge tone="accent">odak</Badge>}
          <Badge tone={project.ok ? 'neutral' : 'danger'}>
            {project.ok ? 'ok' : 'hata'}
          </Badge>
          {project.stale === true && <Badge tone="warning">eski veri</Badge>}
          <Badge tone="neutral">{countsText(project)}</Badge>
          {project.counts?.blocked ? (
            <Badge tone="warning">{project.counts.blocked} engel</Badge>
          ) : null}
        </Row>

        {project.ok === false && (
          <Callout tone="danger" title="Durum okunamadı" icon="error">
            <Text tone="danger">{project.error ?? 'bilinmeyen hata'}</Text>
          </Callout>
        )}

        {project.ok && project.epics.length === 0 && (
          <Text muted size="xs">
            açık iş yok
          </Text>
        )}

        {project.epics.length > 0 && (
          <List label={`${project.name} epicleri`}>
            {project.epics.flatMap((epic) => [
              <ListItem
                key={`epic-${project.id}-${epic.number}`}
                title={epicTitle(epic)}
                onPress={() => openWorkspace(project)}
              >
                <Row gap="xs" wrap>
                  <Badge tone="neutral">{`CP ${cpText(epic)}`}</Badge>
                  <Badge tone={gateTone(epic.gate)}>{`gate ${epic.gate ?? '-'}`}</Badge>
                  <Badge tone="neutral">{`risk ${epic.risk ?? '-'}`}</Badge>
                </Row>
              </ListItem>,
              ...(epic.leaves ?? []).map((leaf) => (
                <ListItem
                  key={`leaf-${project.id}-${leaf.number}`}
                  title={leafTitle(leaf)}
                  onPress={() => openWorkspace(project)}
                />
              ))
            ])}
          </List>
        )}

        {project.warnings.slice(0, 3).map((warning) => (
          <Text key={warning} muted size="xs">
            [uyarı] {warning}
          </Text>
        ))}
      </Stack>
    </Card>
  )
}

export default function Panel() {
  const data = read(snapshot)
  const failure = read(errorText)
  const busy = read(loading)

  return (
    <Stack gap="md">
      <Row justify="between" align="start">
        <Stack gap="xs">
          <Heading>demir-kit</Heading>
          <Row gap="xs" wrap>
            {data !== null && (
              <Badge tone={data.ok ? 'success' : 'warning'}>
                {data.projects.length} proje
              </Badge>
            )}
          </Row>
        </Stack>
        <Button
          variant="ghost"
          icon="refresh"
          disabled={busy}
          onPress={() => void load()}
        >
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

      {failure === null && data !== null && data.code === 'no-kit' && (
        <EmptyState
          title="demir-kit bulunamadı"
          description="Kit kökü (delivery/scripts/status.py) olan bir workspace aç ya da Ayarlar > demir-kit > Proje yolu ver."
        />
      )}

      {failure === null &&
        data !== null &&
        data.code !== 'no-kit' &&
        !data.ok &&
        data.projects.length === 0 && (
          <Callout tone="danger" title="Durum okunamadı" icon="error">
            <Text tone="danger">{data.error ?? 'bilinmeyen hata'}</Text>
          </Callout>
        )}

      {failure === null &&
        data !== null &&
        data.projects.map((project) => (
          <ProjectGroup
            key={project.id}
            project={project}
            focused={project.id === data.focused}
          />
        ))}

      {failure === null && data !== null && data.projects.length > 0 && (
        <Text muted size="xs">
          {data.generated_at ?? ''}
        </Text>
      )}
    </Stack>
  )
}
