// No build step: Orca strips the types and compiles the JSX when the panel loads.
// CP-1: liste ve düz epic detayı; epic satırına tıklama aynı panelde detayı açar.
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
  ActionReply,
  StatusEpic,
  StatusLeaf,
  StatusProject,
  StatusSnapshot
} from './protocol'

/** Dashboard ile aynı pencere: 30 saniyede bir tazele. */
const REFRESH_MS = 30_000

type PanelView =
  | { kind: 'list' }
  | { kind: 'detail'; projectId: string; epicNumber: number }

const snapshot = atom<StatusSnapshot | null>(null)
const errorText = atom<string | null>(null)
const loading = atom<boolean>(false)
/** Liste ya da tek epic detayı; panel yeniden açılınca korunur. */
const view = atom<PanelView>('view', { kind: 'list' }, { persist: 'plugin' })
/** İki adımlı onay: ilk tık burada bekler, ikinci tık işlemi çağırır. */
const confirm = atom<{ id: string } | null>(null)
const actionNote = atom<ActionReply | null>(null)
const acting = atom<boolean>(false)

async function refresh(): Promise<void> {
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
  void refresh()
  const timer = setInterval(() => void refresh(), REFRESH_MS)
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

/** Sayı mı? Null güvenliği tek yerde: `null`/eksik/başka tip satıra girmez. */
function isCount(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/**
 * Eval özeti: `eval 12/14 · discovery %80 · 3 friction`.
 * Parça yalnız dolu alanlardan oluşur; hiç parça yoksa satır çizilmez (`null`).
 * Eski `status.py` `evaluations` taşımaz: aynı şekilde satır yok, panel çökmez.
 */
function evalText(epic: StatusEpic): string | null {
  const evaluations = epic.evaluations
  if (evaluations === undefined || evaluations === null) return null

  const parts: string[] = []
  const pass = evaluations.cases_pass
  const total = evaluations.cases_total
  if (isCount(pass) && isCount(total)) parts.push(`eval ${pass}/${total}`)

  const rate = evaluations.discovery_rate
  if (isCount(rate)) parts.push(`discovery %${Math.round(rate * 100)}`)

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

/** `updated_at` kısa biçim: `04.11 10:00`; çözülemeyen değer olduğu gibi kalır. */
function shortTime(value?: string | null): string {
  const text = (value ?? '').trim()
  if (text === '') return '-'
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  if (match !== null) return `${match[3]}.${match[2]} ${match[4]}:${match[5]}`
  return text.length > 16 ? `${text.slice(0, 16)}…` : text
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

/**
 * Odak çözülemezse hiçbir karta "odak" basılmaz; bunun yerine kısa ve nötr
 * bir satır gösterilir. Hata değildir: Orca 1.4.248 bağlamda id/yol taşımaz.
 */
function focusNotice(data: StatusSnapshot): string | null {
  if (data.focused !== null) return null
  const live = data.live
  const working = live?.working ?? 0
  const blocked = live?.blocked ?? 0
  if (working > 0) return `● ${working} çalışıyor · odak çözülemedi`
  if (blocked > 0) return `● ${blocked} engelli · odak çözülemedi`
  const active = data.active
  if ((active?.epics ?? 0) > 0) {
    return `${active?.projects ?? 0} aktif iş · odak çözülemedi`
  }
  return null
}

/** İlk üç ajanın başlığı; terminal kimliği yoksa tire. */
function agentTitles(project: StatusProject): string {
  return (project.agents ?? [])
    .slice(0, 3)
    .map((agent) => agent.title ?? agent.terminalId ?? '-')
    .join(' · ')
}

/** Epic satırı detayı açar; liste görünümü tamamen detaya bırakılır. */
function openEpic(project: StatusProject, epic: StatusEpic): void {
  set(confirm, null)
  set(view, { kind: 'detail', projectId: project.id, epicNumber: epic.number })
}

function backToList(): void {
  set(confirm, null)
  set(view, { kind: 'list' })
}

function epicTitle(epic: StatusEpic): string {
  return `#${epic.number} — ${epic.title ?? ''}`
}

function leafTitle(leaf: StatusLeaf): string {
  return `#${leaf.number} — ${leaf.title ?? ''} · ${leaf.state ?? '-'}`
}

/** Proje kartındaki claim hedefi: ilk `agent-approved` leaf; yoksa null. */
function claimableLeaf(project: StatusProject): number | null {
  for (const epic of project.epics) {
    for (const leaf of epic.leaves ?? []) {
      if (leaf.state === 'agent-approved') return leaf.number
    }
  }
  return null
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

/** Aksiyon sonucunu bırakır; başarısızsa komut çıktısı ve issue linki görünür.
 * Başarılı aksiyon detayı kapatır: liste görünümüne dönülür ve snapshot tazelenir.
 * Başarısız aksiyon detayda kalır; seçim korunur.
 */
async function runAction(request: () => Promise<ActionReply>): Promise<void> {
  set(confirm, null)
  set(acting, true)
  set(actionNote, null)
  try {
    const answer = await request()
    const reply = answer ?? {
      ok: false,
      message: 'yanıt yok',
      exitCode: 1,
      tail: '',
      url: ''
    }
    set(actionNote, reply)
    if (reply.ok) {
      // Seçim temizlenir: detay kapanır, liste tazelenmiş haliyle görünür.
      set(view, { kind: 'list' })
    }
  } catch (error) {
    set(actionNote, {
      ok: false,
      message: error instanceof Error ? error.message : String(error),
      exitCode: 1,
      tail: '',
      url: ''
    })
  } finally {
    set(acting, false)
    await refresh()
  }
}

/** Başarılı aksiyonda kısa not, kapatma gibi kısmi hatada uyarı kutusu. */
function ActionNote({ note }: { note: ActionReply | null }) {
  if (note === null) return null
  if (note.ok) {
    const warning = (note.warning ?? '').trim()
    return (
      <Stack gap="xs">
        <Text muted size="xs">
          {note.message}
        </Text>
        {warning !== '' && (
          <Callout tone="warning" title="Uyarı" icon="warning">
            <Text size="xs">{warning}</Text>
          </Callout>
        )}
      </Stack>
    )
  }
  return (
    <Callout tone="danger" title="İşlem başarısız" icon="error">
      <Stack gap="xs">
        <Text tone="danger">{note.message}</Text>
        {note.tail !== '' &&
          note.tail.split('\n').map((line, index) => (
            <Text key={`tail-${index}`} muted size="xs">
              {line}
            </Text>
          ))}
        {note.url !== '' && (
          <Button
            variant="outline"
            size="sm"
            icon="open-external"
            onPress={() => openIssue(note.url)}
          >
            Issue'yu aç
          </Button>
        )}
      </Stack>
    </Callout>
  )
}

/** İki adımlı onay: ilk tık `Emin misin?`, ikinci tık `run` çağırır. */
function ConfirmButton({
  id,
  label,
  run
}: {
  id: string
  label: string
  run: () => Promise<void>
}) {
  const pending = read(confirm)?.id === id
  const busy = read(acting)
  if (!pending) {
    return (
      <Button
        variant="outline"
        size="sm"
        disabled={busy}
        onPress={() => {
          set(actionNote, null)
          set(confirm, { id })
        }}
      >
        {label}
      </Button>
    )
  }
  return (
    <Row gap="xs" wrap>
      <Text muted size="xs">
        Emin misin?
      </Text>
      <Button size="sm" disabled={busy} onPress={() => void run()}>
        Evet
      </Button>
      <Button variant="ghost" size="sm" onPress={() => set(confirm, null)}>
        Vazgeç
      </Button>
    </Row>
  )
}

/** Düz epic detayı: CP özeti ve aksiyonlar; iç içe leaf listesi yok. */
function EpicDetail({
  epic,
  projectPath
}: {
  epic: StatusEpic
  projectPath: string
}) {
  // Eski `{done,total}` şekli dizi değildir: CP listesi boş kalır, panel çökmez.
  const checkpoints = Array.isArray(epic.checkpoints) ? epic.checkpoints : []
  const approvals = epic.approvals
  const url = epic.url ?? ''
  // Evaluations yoksa ya da tüm parçalar boşsa `null`: satır çizilmez.
  const evalLine = evalText(epic)

  return (
    <Stack gap="xs">
      <Text weight="semibold">{epicTitle(epic)}</Text>
      <Row gap="xs" wrap>
        <Badge tone={stateTone(epic.state)}>{epic.state ?? '-'}</Badge>
        <Badge tone="neutral">{`CP ${cpText(epic)}`}</Badge>
        <Badge tone={approvals?.agent_approved ? 'success' : 'neutral'}>
          {`ajan onayı ${approvals?.agent_approved ? 'var' : 'yok'}`}
        </Badge>
        <Badge tone={approvals?.human_qa ? 'success' : 'neutral'}>
          {`insan QA ${approvals?.human_qa ? 'var' : 'yok'}`}
        </Badge>
        <Text muted size="xs">{`güncelleme ${shortTime(epic.updated_at)}`}</Text>
      </Row>

      <Text muted size="xs">{`sıradaki iş: ${epic.next_action ?? '-'}`}</Text>

      {/* Salt-okur eval özeti; parça yoksa hiç çizilmez. */}
      {evalLine !== null && (
        <Text muted size="xs">
          {evalLine}
        </Text>
      )}

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

      <Row gap="xs" wrap>
        {url !== '' && (
          <Button variant="outline" size="sm" icon="open-external" onPress={() => openIssue(url)}>
            Issue'yu aç
          </Button>
        )}
        {approvals?.human_qa === true && (
          <>
            <ConfirmButton
              id={`epic:${epic.number}:accepted`}
              label="Kabul et"
              run={() =>
                runAction(() =>
                  plugin.request('epic.decision', {
                    projectPath,
                    issue: epic.number,
                    decision: 'accepted'
                  })
                )
              }
            />
            <ConfirmButton
              id={`epic:${epic.number}:rejected`}
              label="Reddet"
              run={() =>
                runAction(() =>
                  plugin.request('epic.decision', {
                    projectPath,
                    issue: epic.number,
                    decision: 'rejected'
                  })
                )
              }
            />
          </>
        )}
      </Row>
    </Stack>
  )
}

/** Yürüyen leaf'i olan proje: odak olmasa da "aktif" rozeti alır. */
function isActive(project: StatusProject): boolean {
  return project.epics.some((epic) =>
    (epic.leaves ?? []).some((leaf) => leaf.state === 'executing')
  )
}

function ProjectGroup({
  project,
  focused
}: {
  project: StatusProject
  focused: boolean
}) {
  const claimable = claimableLeaf(project)
  const active = isActive(project)

  return (
    <Card title={projectTitle(project)} description={shortPath(project.path)}>
      <Stack gap="sm">
        <Row gap="xs" wrap>
          {focused && <Badge tone="accent">odak</Badge>}
          {!focused && active && <Badge tone="accent">aktif</Badge>}
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
          <List label={`${project.name} epicleri`}>
            {project.epics.flatMap((epic) => [
              <ListItem
                key={`epic-${project.id}-${epic.number}`}
                title={epicTitle(epic)}
                onPress={() => openEpic(project, epic)}
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
        )}

        {project.ok && claimable !== null && (
          <ConfirmButton
            id={`project:${project.id}:claim`}
            label="Sıradaki leaf'i claim et"
            run={() =>
              runAction(() =>
                plugin.request('leaf.claim', { projectPath: project.path })
              )
            }
          />
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
  const note = read(actionNote)
  const current = read(view)
  const noteLine = <ActionNote note={note} />
  const focusLine = data === null ? null : focusNotice(data)

  if (current.kind === 'detail') {
    const project = data?.projects.find((item) => item.id === current.projectId)
    const epic = project?.epics.find((item) => item.number === current.epicNumber)
    return (
      <Stack gap="md">
        <Row justify="between" align="start">
          <Heading>demir-kit</Heading>
          <Row gap="xs">
            <Button
              variant="ghost"
              icon="refresh"
              disabled={busy}
              onPress={() => void refresh()}
            >
              Yenile
            </Button>
            <Button variant="outline" size="sm" onPress={backToList}>
              ‹ Geri
            </Button>
          </Row>
        </Row>

        {noteLine}

        {project !== undefined && epic !== undefined ? (
          <Box border={true} radius="md" padding="md">
            <Stack gap="xs">
              <Text muted size="xs">
                {`${projectTitle(project)} · ${shortPath(project.path)}`}
              </Text>
              <EpicDetail epic={epic} projectPath={project.path} />
            </Stack>
          </Box>
        ) : (
          <Text muted size="xs">
            Epic listede yok; geri dönüp listeyi yenile.
          </Text>
        )}
      </Stack>
    )
  }

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
            {data !== null && (data.active?.epics ?? 0) > 0 && (
              <Badge tone="accent">{`${data.active?.projects ?? 0} aktif`}</Badge>
            )}
          </Row>
        </Stack>
        <Button
          variant="ghost"
          icon="refresh"
          disabled={busy}
          onPress={() => void refresh()}
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

      {noteLine}

      {failure === null && focusLine !== null && (
        <Text muted size="xs">
          {focusLine}
        </Text>
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
