import { useEffect, useMemo, useRef, useState } from "react";
import { useLanguage } from "./i18n";
import "./BulletinEnhancements.css";

type Row = Record<string, any>;
type Request = (path: string, method?: string, body?: Row, signal?: AbortSignal) => Promise<any>;
type Cursor = { version_id: number; content_hash: string; visited_at: string };
export type UpdateSelection = { after: number; type: "new" | "changed"; catalog: boolean };

function readVisit(key: string): Cursor | null {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    return value && Number.isSafeInteger(value.version_id) && value.version_id >= 0 &&
      typeof value.content_hash === "string" && value.content_hash.length <= 64 &&
      typeof value.visited_at === "string" && Number.isFinite(Date.parse(value.visited_at)) ? value : null;
  } catch { return null; }
}
function saveVisit(key: string, cursor: Cursor) {
  try { localStorage.setItem(key, JSON.stringify(cursor)); return true; } catch { return false; }
}

type SummaryProps = {
  scope: string; demo: boolean; visible: boolean; paused: boolean; request: Request;
  onSelect: (selection: UpdateSelection) => void; onSources: () => void;
};
export function VisitSummary(props: SummaryProps) {
  return <SummarySession key={`${props.scope}:${props.demo}`} {...props} />;
}
function SummarySession({ scope, demo, visible, paused, request, onSelect, onSources }: SummaryProps) {
  const { t, format } = useLanguage();
  const storageKey = `nom-visit-v1:${scope}:${demo}`;
  const startingVisit = useMemo(() => readVisit(storageKey), [storageKey]);
  const baseline = useRef<Cursor | null>(startingVisit);
  const saved = useRef(false);
  const [data, setData] = useState<Row | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [reviewed, setReviewed] = useState(false);
  const [persistent, setPersistent] = useState(true);
  useEffect(() => {
    if (!visible || paused) return;
    let controller: AbortController | null = null;
    let running = false;
    const load = async () => {
      if (running || document.visibilityState === "hidden") return;
      running = true;
      controller = new AbortController();
      const active = controller;
      const params = new URLSearchParams({ is_demo: String(demo) });
      if (baseline.current) {
        params.set("after_version_id", String(baseline.current.version_id));
        params.set("anchor_hash", baseline.current.content_hash);
      }
      try {
        const result = await request(`/bulletin/updates?${params}`, "GET", undefined, active.signal);
        if (active.signal.aborted || !result.cursor) return;
        setData({ ...result, since: baseline.current });
        setError(false);
        if (!saved.current || result.reset) {
          setPersistent(saveVisit(storageKey, result.cursor));
          saved.current = true;
        }
        if (!baseline.current || result.reset) baseline.current = result.cursor;
      } catch {
        if (!active.signal.aborted) setError(true);
      } finally { running = false; }
    };
    void load();
    const timer = window.setInterval(() => void load(), 60000);
    return () => { controller?.abort(); clearInterval(timer); };
  }, [request, visible, paused, demo, storageKey, attempt]);
  if (!visible) return null;
  const firstVisit = Boolean(data && !startingVisit && !reviewed);
  const markReviewed = () => {
    if (!data?.cursor) return;
    baseline.current = data.cursor;
    setPersistent(saveVisit(storageKey, data.cursor));
    setReviewed(true);
    setAttempt((value) => value + 1);
    setData({ ...data, since: data.cursor, first_visit: false, new_publications: 0, changed_publications: 0,
      new_catalog: 0, changed_catalog: 0 });
  };
  const cards = [
    { label: "Publicaciones incorporadas", count: data?.new_publications || 0, type: "new" as const, catalog: false, source: "SIDOF" },
    { label: "Publicaciones con versiones nuevas", count: data?.changed_publications || 0, type: "changed" as const, catalog: false, source: "SIDOF" },
    { label: "Fichas incorporadas al catálogo", count: data?.new_catalog || 0, type: "new" as const, catalog: true, source: "PLATIICA" },
  ];
  return <section className="visit-summary" aria-label={t("Resumen de tu visita")}>
    <div className="visit-summary-heading">
      <div><span className="eyebrow">{t("TU BOLETÍN")}</span>
        <h2>{t(firstVisit ? "Tu primer resumen" : "Desde tu última visita")}</h2>
        <p>{firstVisit ? t("El seguimiento comienza hoy. El histórico no se cuenta como novedad.")
          : data?.since ? t("En este navegador, desde {date}.", { date: format(data.since.visited_at, true) })
            : t("Preparando tu resumen…")}</p></div>
      {data && <button type="button" className="text-button" onClick={markReviewed}>{t("Marcar resumen como revisado")}</button>}
    </div>
    {error && <p role="status">{t("El resumen no pudo actualizarse. Las publicaciones siguen disponibles.")} {" "}
      <button type="button" className="text-button" onClick={() => setAttempt((value) => value + 1)}>{t("Reintentar resumen")}</button></p>}
    {data && <>
      <div className="visit-summary-cards">{cards.map((card) => <button type="button" key={card.label}
        disabled={card.count === 0} onClick={() => onSelect({ after: data.since?.version_id ?? data.cursor.version_id, type: card.type, catalog: card.catalog })}>
        <span className="visit-count">{card.count}</span><span>{t(card.label)}<small>{card.source}</small></span>
      </button>)}</div>
      {data.changed_catalog > 0 && <button type="button" className="text-button" onClick={() => onSelect({
        after: data.since?.version_id ?? data.cursor.version_id, type: "changed", catalog: true,
      })}>{t("{count} fichas con versiones nuevas", { count: data.changed_catalog })}</button>}
      <div className="visit-summary-footer"><span>{t("Incorporado al portal no significa publicado hoy.")}</span>
        <span>{t("Última consulta completada de SIDOF")}: {data.last_complete_check?.finished_at ? format(data.last_complete_check.finished_at, true) : t("Pendiente")}</span>
        {data.last_complete_check?.period_start && <span>{t("Periodo de esa consulta: {start} a {end}", {
          start: format(data.last_complete_check.period_start), end: format(data.last_complete_check.period_end),
        })}</span>}
        {data.latest_check && data.latest_check.status !== "succeeded" && <button type="button" className="text-button" onClick={onSources}>{t(
          ["running", "queued"].includes(data.latest_check.status) ? "SIDOF tiene una consulta en curso. Ver estado de fuentes."
            : "La revisión más reciente está incompleta. Ver estado de fuentes.")}</button>}
        {data.reset && <span role="status">{t("El historial cambió; se inició un nuevo seguimiento de visitas.")}</span>}
        {!persistent && <span>{t("El navegador no permite guardar el seguimiento. El resumen se conserva durante esta visita.")}</span>}
        {reviewed && <span role="status">{t(persistent ? "Resumen marcado como revisado en este navegador." : "Resumen marcado como revisado para esta visita.")}</span>}
      </div>
    </>}
  </section>;
}

export function PublicationFacts({ publication, capturedAt }: { publication: Row; capturedAt?: string }) {
  const { t, format } = useLanguage();
  const code = publication.title?.match(/\b(?:PROY-)?NOM(?:-EM)?-\d{2,3}-[A-Z0-9/-]+?-\d{4}\b/i)?.[0] || publication.official_id;
  const verifiedDate = publication.effective_verified && publication.effective_on && publication.effective_evidence;
  const facts = [
    ["Clave o identificador", code || t("Por confirmar")],
    ["Estado informado por la fuente", publication.norm_status || t("No informado por la fuente")],
    ["Publicación oficial", publication.published_on ? format(publication.published_on) : t("Fecha por confirmar")],
    ["Entrada en vigor verificada", verifiedDate ? format(publication.effective_on) : t("Por confirmar")],
    ["Fuente", publication.source_name || t("No informado por la fuente")],
    ["Copia consultada", capturedAt ? format(capturedAt, true) : t("Pendiente")],
  ];
  return <section className="publication-facts" aria-label={t("Ficha de la publicación")}>
    <h2>{t("Ficha de la publicación")}</h2>
    <dl>{facts.map(([label, value]) => <div key={label}><dt>{t(label)}</dt><dd>{value}</dd></div>)}</dl>
    {publication.product_scope && <p><strong>{t("Producto/servicio en PLATIICA")}: </strong>{publication.product_scope}</p>}
    <p>{t("La ficha muestra el registro actual; la copia corresponde a la versión seleccionada.")}</p>
    {verifiedDate && <details className="facts-evidence"><summary>{t("Evidencia de la fecha verificada")}</summary>
      <p lang="es">{publication.effective_evidence}</p>
    </details>}
  </section>;
}

type Mark = { kind: "equal" | "added" | "removed"; text: string };
function Highlight({ marks, text, side }: { marks?: Mark[]; text: string; side: "before" | "after" }) {
  if (!marks) return side === "before" ? <del>{text}</del> : <ins>{text}</ins>;
  return <>{marks.map((mark, i) => mark.kind === "removed" ? <del key={i}>{mark.text}</del>
    : mark.kind === "added" ? <ins key={i}>{mark.text}</ins> : <span key={i}>{mark.text}</span>)}</>;
}
export function VersionComparison({ publicationId, versions, selectedId, request }: {
  publicationId: number; versions: Row[]; selectedId: number; request: Request;
}) {
  const { t, format } = useLanguage();
  const [expanded, setExpanded] = useState(false);
  const [baseId, setBaseId] = useState<number | null>(null);
  const selected = versions.find((version) => version.id === selectedId);
  const older = versions.filter((version) => version.sequence < (selected?.sequence || 0));
  const from = older.find((version) => version.id === baseId) || older[0];
  const pair = `${publicationId}:${from?.id}:${selectedId}`;
  const [pagination, setPagination] = useState({ pair, page: 1 });
  const page = pagination.pair === pair ? pagination.page : 1;
  const cache = useMemo(() => new Map<string, Row>(), [request]);
  const path = `/bulletin/publications/${publicationId}/comparison?from_version_id=${from?.id}&to_version_id=${selectedId}&page=${page}`;
  const [result, setResult] = useState<{ path: string; cache: typeof cache; data: Row } | null>(null);
  const [failure, setFailure] = useState("");
  const [attempt, setAttempt] = useState(0);
  const data = result?.path === path && result.cache === cache ? result.data : cache.get(path);
  useEffect(() => {
    if (!expanded || !from) return;
    const controller = new AbortController();
    setFailure("");
    if (cache.has(path)) return;
    void request(path, "GET", undefined, controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      cache.set(path, data);
      if (cache.size > 4) cache.delete(cache.keys().next().value!);
      setResult({ path, cache, data });
    }).catch(() => { if (!controller.signal.aborted) setFailure(path); });
    return () => controller.abort();
  }, [expanded, from?.id, path, cache, request, attempt]);
  if (versions.length < 2) return null;
  const captions: Record<string, string> = {
    unchanged: "El texto guardado es idéntico en ambas copias.",
    spacing_only: "El texto coincide al unificar espacios y caracteres equivalentes.",
    text_changed: "Hay diferencias en el texto guardado.",
    unavailable: "No hay texto suficiente en ambas copias para comparar.",
    too_large: "Estas copias superan el tamaño de comparación. Consulta las versiones originales.",
  };
  const failed = failure === path;
  return <section className="version-comparison">
    <button type="button" className="button paper" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{t(expanded ? "Cerrar comparación" : "Comparar versiones")}</button>
    {expanded && <div className="comparison-content">
      <h2>{t("Comparación de versiones guardadas")}</h2>
      <p>{t("Son copias conservadas por NOM Monitor, no números de edición oficial de la NOM.")}</p>
      <p>{t("Se compara el texto extraído. Revisa las copias originales para tablas, imágenes y formato.")}</p>
      {!from ? <p>{t("Esta es la primera versión guardada.")}</p> : <>
        <label>{t("Comparar con la versión anterior")}
          <select value={from.id} onChange={(event) => setBaseId(Number(event.target.value))}>
            {older.map((version) => <option key={version.id} value={version.id}>{t("Versión {number}", { number: version.sequence })} · {format(version.captured_at, true)}</option>)}
          </select>
        </label>
        <p>{t("Versión seleccionada")}: {t("Versión {number}", { number: selected?.sequence || 0 })} · {format(selected?.captured_at, true)}</p>
        {failed ? <p role="status">{t("No se pudo cargar la comparación.")} <button type="button" className="text-button" onClick={() => setAttempt((value) => value + 1)}>{t("Reintentar")}</button></p>
          : !data ? <p role="status">{t("Comparando las copias…")}</p> : <>
            <p className="comparison-caption" role="status">
              <strong>{t(({ unchanged: "Texto sin cambios", spacing_only: "Diferencias de espacios o caracteres equivalentes",
                text_changed: "Diferencias de texto detectadas" } as Record<string, string>)[data.classification] || "Comparación de texto")}</strong>
              <br />{t(captions[data.classification] || captions.unavailable)}
            </p>
            {data.classification === "text_changed" && <>
              <p>{t("{added} bloques agregados · {removed} eliminados · {modified} modificados", { added: data.added, removed: data.removed, modified: data.modified })}</p>
              <p className="comparison-legend"><del>{t("Texto eliminado")}</del> <ins>{t("Texto agregado")}</ins></p>
              <div className="comparison-rows" lang="es">{data.items.map((row: Row, index: number) => row.kind === "context"
                ? <p className="comparison-context" key={index}>{row.before}</p>
                : <div className="comparison-row" key={index}>
                  <div><strong>{t("Antes")}</strong><p>{row.before ? <Highlight marks={row.before_marks} text={row.before} side="before" /> : "—"}</p></div>
                  <div><strong>{t("Ahora")}</strong><p>{row.after ? <Highlight marks={row.after_marks} text={row.after} side="after" /> : "—"}</p></div>
                </div>)}</div>
              {data.total > data.page_size && <nav className="comparison-pagination" aria-label={t("Páginas de comparación")}>
                <button type="button" className="button paper" disabled={page <= 1} onClick={() => setPagination({ pair, page: page - 1 })}>{t("Anterior")}</button>
                <span>{t("Página {page} de {total}", { page, total: Math.ceil(data.total / data.page_size) })}</span>
                <button type="button" className="button paper" disabled={page * data.page_size >= data.total} onClick={() => setPagination({ pair, page: page + 1 })}>{t("Siguiente")}</button>
              </nav>}
            </>}
          </>}
      </>}
    </div>}
  </section>;
}
