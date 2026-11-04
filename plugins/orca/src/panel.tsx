// No build step: Orca strips the types and compiles the JSX when the panel loads.
// CP-2: çok projeli portföy, epic/leaf başlıkları, tıklayınca workspace açma.
import {
  atom,
  Badge,
  Box,
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
  shell,
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
/** Açık epic detayları: `${project.id}:${epic.number}`; panel yeniden açılınca korunur. */
const expanded = atom<string[]>('expanded', [], { persist: 'plugin' })

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
  // Eski `status.py` `{done,total}` gönderirse çökme: dizi değilse boş say.
  const checkpoints = Array.isArray(epic.checkpoints) ? epic.checkpoints : []
  const done = checkpoints.filter((checkpoint) => checkpoint.done === true).length
  return `${done}/${checkpoints.length}`
}

function gateTone(gate: StatusEpic['gate']): 'success' | 'danger' | 'neutral' {
  if (gate === 'pass') return 'success'
  if (gate === 'fail') return 'danger'
  return 'neutral'
}

/** Epic state rozeti: yürüyen iş vurgulu, engel kırmızı, biten yeşil. */
function stateTone(state?: string): 'accent' | 'success' | 'danger' | 'warning' | 'neutral' {
  if (state === 'executing') return 'accent'
  if (state === 'leaf-done' || state === 'epic-done') return 'success'
  if (state === 'blocked') return 'danger'
  if (state === 'epic-reconcile') return 'warning'
  return 'neutral'
}

/** Canlı ajan satırı: `● 2 çalışıyor · 1 boşta · 1 engelli`. */
function liveText(project: StatusProject): string {
  const live = project.live
  const idle = live?.idle ?? 0
  const idleText = idle > 0 ? ` · ${idle} boşta` : ''
  return `● ${live?.working ?? 0} çalışıyor${idleText} · ${live?.blocked ?? 0} engelli`
}

/** İlk üç ajanın başlığı; terminal kimliği yoksa tire. */
function agentTitles(project: StatusProject): string {
  return (project.agents ?? [])
    .slice(0, 3)
    .map((agent) => agent.title ?? agent.terminalId ?? '-')
    .join(' · ')
}

function epicKey(project: StatusProject, epic: StatusEpic): string {
  return `${project.id}:${epic.number}`
}

/** Epic satırı detayı açar/kapatır; aynı panelde kalır. */
function toggleEpic(key: string): void {
  const open = read(expanded)
  set(
    expanded,
    open.includes(key) ? open.filter((item) => item !== key) : [...open, key]
  )
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

/** Issue bağlantısı tarayıcıda açılır; tıklama panelde kalır. */
function openIssue(url: string): void {
  void shell.openExternal(url).catch((error: unknown) => {
    console.error(`demir-kit: shell.openExternal başarısız: ${String(error)}`)
  })
}

/** Epic detayı: CP listesi, onaylar, sıradaki iş, güncelleme zamanı, issue linki. */
function EpicDetail({ epic }: { epic: StatusEpic }) {
  // Eski `{done,total}` şekli dizi değildir: CP listesi boş kalır, panel çökmez.
  const checkpoints = Array.isArray(epic.checkpoints) ? epic.checkpoints : []
  const approvals = epic.approvals
  const url = epic.url ?? ''

  return (
    <Box border={true} radius="md" padding="sm" background="muted">
      <Stack gap="xs">
        <Text weight="semibold" size="xs">
          {epicTitle(epic)}
        </Text>
        <Row gap="xs" wrap>
          <Badge tone={approvals?.agent_approved ? 'success' : 'neutral'}>
            {`ajan onayı ${approvals?.agent_approved ? 'var' : 'yok'}`}
          </Badge>
          <Badge tone={approvals?.human_qa ? 'success' : 'neutral'}>
            {`insan QA ${approvals?.human_qa ? 'var' : 'yok'}`}
          </Badge>
          <Text muted size="xs">{`güncelleme ${epic.updated_at ?? '-'}`}</Text>
        </Row>

        {checkpoints.length === 0 && (
          <Text muted size="xs">
            checkpoint yok
          </Text>
        )}
        {checkpoints.map((checkpoint) => (
          <Text key={`${epic.number}-${checkpoint.leaf}-${checkpoint.id}`} size="xs">
            {`#${checkpoint.leaf} · ${checkpoint.id} ${checkpoint.done ? '✓' : '○'} ${checkpoint.title}`}
          </Text>
        ))}

        <Text muted size="xs">{`sıradaki iş: ${epic.next_action ?? '-'}`}</Text>

        {url !== '' && (
          <Button variant="outline" size="sm" icon="open-external" onPress={() => openIssue(url)}>
            Issue'yu aç
          </Button>
        )}
      </Stack>
    </Box>
  )
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

        {(project.agents ?? []).length > 0 && (
          <Stack gap="xs">
            <Badge tone={(project.live?.blocked ?? 0) > 0 ? 'warning' : 'accent'}>
              {liveText(project)}
            </Badge>
            <Text muted size="xs">
              {agentTitles(project)}
            </Text>
          </Stack>
        )}

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
          <Stack gap="sm">
            <List label={`${project.name} epicleri`}>
              {project.epics.flatMap((epic) => [
                <ListItem
                  key={`epic-${project.id}-${epic.number}`}
                  title={epicTitle(epic)}
                  onPress={() => toggleEpic(epicKey(project, epic))}
                >
                  <Row gap="xs" wrap>
                    <Badge tone={stateTone(epic.state)}>
                      {epic.state ?? '-'}
                    </Badge>
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
            {project.epics
              .filter((epic) => read(expanded).includes(epicKey(project, epic)))
              .map((epic) => (
                <EpicDetail key={`detail-${project.id}-${epic.number}`} epic={epic} />
              ))}
          </Stack>
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
