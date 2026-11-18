import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useLanguage } from "./i18n";
import "./PublicationHistory.css";

type Row = Record<string, any>;
type Request = (path: string, method?: string, body?: Row, signal?: AbortSignal) => Promise<any>;
export type ArchiveDates = { from: string; to: string; direction: "asc" | "desc" };
export const emptyArchiveDates: ArchiveDates = { from: "", to: "", direction: "desc" };

export function calendarRange(year: string, month = "") {
  if (!year) return { from: "", to: "" };
  if (!month) return { from: `${year}-01-01`, to: `${year}-12-31` };
  const last = new Date(Date.UTC(Number(year), Number(month), 0)).getUTCDate();
  return { from: `${year}-${month}-01`, to: `${year}-${month}-${last}` };
}

export function ArchiveTools({ dates, change, request, demo, admin, sourceId, progress, queued, sourcesView }: {
  dates: ArchiveDates; change: (dates: ArchiveDates) => void; request: Request; demo: boolean;
  admin: boolean; sourceId?: number; progress: string; queued: () => void; sourcesView: () => void;
}) {
  const { t, format, language } = useLanguage();
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Mexico_City", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const currentYear = Number(today.slice(0, 4));
  const [coverage, setCoverage] = useState<Row | null>(null);
  const [coverageError, setCoverageError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const [imported, setImported] = useState(false);
  const [importFrom, setImportFrom] = useState(`${currentYear}-01-01`);
  const [importTo, setImportTo] = useState(today);
  const year = dates.from && dates.to && dates.from.slice(0, 4) === dates.to.slice(0, 4) ? dates.from.slice(0, 4) : "";
  const month = year && dates.from.slice(0, 7) === dates.to.slice(0, 7) ? dates.from.slice(5, 7) : "";
  const coverageYear = year || String(currentYear);
  const years = useMemo(() => [...new Set([
    ...Array.from({ length: 11 }, (_, index) => currentYear - index),
    ...(coverage?.years || []).map((item: Row) => Number(item.year)),
    ...(year ? [Number(year)] : []),
  ])].sort((a, b) => b - a), [currentYear, coverage, year]);

  useEffect(() => {
    const controller = new AbortController();
    setCoverageError(false);
    setCoverage(null);
    void request(`/history/coverage?year=${coverageYear}&is_demo=${demo}`, "GET", undefined, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setCoverage(data); })
      .catch(() => { if (!controller.signal.aborted) setCoverageError(true); });
    return () => controller.abort();
  }, [request, coverageYear, demo, progress, retry]);

  const importHistory = async (event: FormEvent) => {
    event.preventDefault();
    setImporting(true); setImportError(""); setImported(false);
    try {
      await request("/jobs", "POST", { source_id: sourceId, period_start: importFrom, period_end: importTo });
      setImported(true); queued();
    } catch (error) { setImportError((error as Error).message); }
    finally { setImporting(false); }
  };

  return <section className="archive-tools" aria-label={t("Fechas del archivo")}>
    <div className="archive-date-grid">
      <label>{t("Año")}<select value={year} onChange={(event) => change({ ...dates, ...calendarRange(event.target.value) })}>
        <option value="">{t("Todos los años")}</option>
        {years.map((value) => <option key={value} value={value}>{value}</option>)}
      </select></label>
      <label>{t("Mes")}<select value={month} disabled={!year} onChange={(event) => change({ ...dates, ...calendarRange(year, event.target.value) })}>
        <option value="">{t("Todos los meses")}</option>
        {Array.from({ length: 12 }, (_, index) => <option key={index} value={String(index + 1).padStart(2, "0")}>
          {new Intl.DateTimeFormat(language === "en" ? "en-US" : "es-MX", { month: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2024, index, 1)))}
        </option>)}
      </select></label>
      <label>{t("Desde")}<input type="date" value={dates.from} onChange={(event) => change({ ...dates, from: event.target.value })} /></label>
      <label>{t("Hasta")}<input type="date" value={dates.to} onChange={(event) => change({ ...dates, to: event.target.value })} /></label>
      <label>{t("Orden cronológico")}<select value={dates.direction} onChange={(event) => change({ ...dates, direction: event.target.value as ArchiveDates["direction"] })}>
        <option value="desc">{t("Más recientes primero")}</option><option value="asc">{t("Más antiguas primero")}</option>
      </select></label>
    </div>
    {dates.from && dates.to && dates.from > dates.to && <p role="alert">{t("La fecha inicial debe ser anterior o igual a la fecha final.")}</p>}
    <div className="archive-coverage" aria-label={t("Cobertura del archivo guardado")}>
      <strong>{t("Cobertura del archivo guardado")}</strong>
      {coverageError ? <p role="status">{t("No se pudo consultar la cobertura del archivo.")} <button className="text-button" onClick={() => setRetry(retry + 1)}>{t("Reintentar")}</button></p>
        : coverage ? <>
          <p>{t(coverage.total === 1 ? "{count} publicación guardada" : "{count} publicaciones guardadas", { count: coverage.total || 0 })}
            {coverage.first_publication && <> · {t("Fechas con documentos: {from} a {to}.", { from: format(coverage.first_publication), to: format(coverage.last_publication) })}</>}
          </p>
          {!coverage.total && <p>{t("Todavía no hay publicaciones SIDOF guardadas.")}</p>}
          <p>{t(coverage.verified_days === 1 ? "Índice verificado en {year}: 1 día." : "Índices verificados en {year}: {count} días.", { year: coverageYear, count: coverage.verified_days || 0 })}
            {!!coverage.incomplete_days && <> {t(coverage.incomplete_days === 1 ? "1 día consultado conserva referencias incompletas." : "{count} días consultados conservan referencias incompletas.", { count: coverage.incomplete_days })}</>}</p>
          <p>{t("Los documentos guardados no acreditan que todos los días del intervalo estén cubiertos.")}</p>
        </> : <p role="status">{t("Cargando…")}</p>}
    </div>
    {admin && sourceId && !demo && <details className="archive-import">
      <summary>{t("Cargar un periodo anterior")}</summary>
      <p>{t("Solicita hasta un año por carga. El servidor recupera los documentos en segundo plano; puedes seguir navegando.")}</p>
      <form onSubmit={(event) => void importHistory(event)}>
        <label>{t("Desde")}<input aria-label={t("Cargar un periodo anterior") + " · " + t("Desde")} type="date" required max={today} value={importFrom} onChange={(event) => setImportFrom(event.target.value)} /></label>
        <label>{t("Hasta")}<input aria-label={t("Cargar un periodo anterior") + " · " + t("Hasta")} type="date" required min={importFrom} max={today} value={importTo} onChange={(event) => setImportTo(event.target.value)} /></label>
        <button className="button paper" disabled={importing}>{t(importing ? "Solicitando carga…" : "Cargar periodo histórico")}</button>
      </form>
      {importError && <p role="alert">{t(importError)}</p>}
      {imported && <p role="status">{t("La carga quedó en cola. Consulta su avance en Estado de fuentes.")} <button className="text-button" onClick={sourcesView}>{t("Estado de fuentes")}</button></p>}
    </details>}
  </section>;
}

export function PublicationHistory({ publication, request, open }: { publication: Row; request: Request; open: (id: number) => void }) {
  const { t, format } = useLanguage();
  const [code, setCode] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<Row | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setResult(null); setError(false);
    void request(`/history/publications/${publication.id}?page=${page}${code ? `&norm_code=${encodeURIComponent(code)}` : ""}`, "GET", undefined, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setResult(data); })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [publication.id, request, page, code, retry]);
  const kinds: Record<string, string> = { proyecto: "Proyecto de norma", norma_definitiva: "Norma definitiva", norma_emergencia: "Norma de emergencia", modificacion: "Modificación", cancelacion: "Cancelación", acuerdo: "Acuerdo", aviso: "Aviso" };
  const codes: string[] = result?.norm_codes || publication.norm_codes || [];
  return <div className="publication-history reader-body">
    <span className="eyebrow">{t("Historial relacionado")}</span>
    <h1>{t("Publicaciones que mencionan esta NOM")}</h1>
    <p className="history-selected-title" lang="es">{publication.title}</p>
    <p>{t("Se vinculan por la clave completa, incluido el año. Una mención no acredita una modificación, sustitución o cancelación.")}</p>
    {codes.length > 1 ? <label className="history-code-select">{t("Clave NOM")}<select value={code || result?.selected_norm_code || codes[0]} onChange={(event) => { setCode(event.target.value); setPage(1); }}>
      {codes.map((value) => <option key={value}>{value}</option>)}
    </select></label> : codes.length === 1 && <strong className="history-code">{codes[0]}</strong>}
    {error ? <div role="alert"><p>{t("No se pudo cargar el historial.")}</p><button className="button paper" onClick={() => setRetry(retry + 1)}>{t("Reintentar")}</button></div>
      : !result ? <p role="status">{t("Cargando historial…")}</p> : <>
        {!!result.unindexed_publications && <p className="history-progress" role="status">{t("Se están preparando las referencias de {count} publicaciones guardadas. El historial puede crecer al terminar.", { count: result.unindexed_publications })} <button className="text-button" onClick={() => setRetry(retry + 1)}>{t("Actualizar")}</button></p>}
        {!result.items?.length ? <p className="history-empty">{t(!codes.length ? "No se identificó una clave NOM completa en el título o identificador de esta ficha." : "No hay publicaciones relacionadas en el archivo guardado.")}</p> : <ol className="history-timeline">
          {result.items.map((item: Row) => <li key={item.id}>
            <div className="history-event-meta"><time dateTime={item.published_on || undefined}>{item.published_on ? format(item.published_on) : t("Sin fecha oficial confirmada")}</time><span>{t(kinds[item.kind] || "Publicación")}</span></div>
            <button className="headline-link" lang="es" onClick={() => open(item.id)}>{item.title}</button>
            <p className="history-evidence-label">{t(item.reference_location === "title" ? "Referencia en el título" : item.reference_location === "identifier" ? "Referencia en el identificador" : "Referencia en el texto")}</p>
            <blockquote lang="es">{item.reference_snippet}</blockquote>
            <button className="text-button" onClick={() => open(item.id)}>{t("Abrir documento")}</button>
          </li>)}
        </ol>}
        {result.total > 25 && <nav className="history-pagination" aria-label={t("Historial relacionado")}>
          <button className="button paper" disabled={page === 1} onClick={() => setPage(page - 1)}>{t("Anterior")}</button>
          <span>{t("Página {page} de {total}", { page, total: Math.ceil(result.total / 25) })}</span>
          <button className="button paper" disabled={page * 25 >= result.total} onClick={() => setPage(page + 1)}>{t("Siguiente")}</button>
        </nav>}
        <p>{t("El histórico puede ampliarse al cargar otros periodos de SIDOF.")}</p>
      </>}
  </div>;
}
