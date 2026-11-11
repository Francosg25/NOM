Warning: truncated output (original token count: 21518)
Total output lines: 2124

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  accessToken,
  authConfig,
  restoreSession,
  signIn,
  signOut,
} from "./apiAccess";
import type { AuthConfig } from "./apiAccess";
import { LanguageProvider, useLanguage } from "./i18n";
import { version as portalVersion } from "../package.json";
import DocumentReading, { createReadingLoader } from "./DocumentReading";

type Row = Record<string, any>;
type View = "actualidad" | "archivo" | "historico" | "producto" | "fuentes" | "guia";
const views: { id: View; name: string }[] = [
  { id: "actualidad", name: "Novedades" },
  { id: "archivo", name: "Buscar publicaciones" },
  { id: "historico", name: "Catálogo NOM" },
  { id: "producto", name: "Consultar producto" },
  { id: "fuentes", name: "Estado de fuentes" },
  { id: "guia", name: "Cómo funciona" },
];
const types: Record<string, string> = {
  proyecto: "Proyecto de norma",
  norma_vigente: "Norma vigente",
  norma_no_vigente: "NOM no vigente",
  norma_definitiva: "Norma definitiva",
  norma_emergencia: "Norma de emergencia",
  modificacion: "Modificación",
  cancelacion: "Cancelación",
  acuerdo: "Acuerdo",
  aviso: "Aviso",
  clasificacion_pendiente: "Publicación",
};
const jobNames: Record<string, string> = {
  queued: "En espera",
  running: "Consultando",
  succeeded: "Completada",
  failed: "Con error",
  partial: "Consulta parcial",
  interrupted: "Interrumpida",
};
function dayStamp(days = 0) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Mexico_City",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(Date.now() - days * 86400000));
}
function link(value: string) {
  try {
    const u = new URL(value);
    return u.protocol === "https:" ? u.href : "";
  } catch {
    return "";
  }
}
function displayUrl(value: string) {
  try {
    const u = new URL(value);
    return u.hostname.replace(/^www\./, "") + u.pathname;
  } catch {
    return value;
  }
}
function dailySource(item?: Row) {
  return (
    item?.kind === "sidof" &&
    item.urls?.some(
      (url: string) =>
        url.replace(/\/$/, "") === "https://sidof.segob.gob.mx/dof/sidof",
    )
  );
}
function missingIndexError(error?: string) {
  return Boolean(error?.includes("SIDOF: fecha sin índice, pero sin declaración oficial de ausencia de publicación"));
}
function sourceIssue(error: string) {
  if (missingIndexError(error))
    return "SIDOF no entregó un índice para algunas fechas y su calendario no confirmó que fueran días sin publicación. Esas fechas siguen pendientes; las demás consultas pueden continuar.";
  const causes: Record<string, string> = {
    TLS_CERTIFICATE:
      "La conexión HTTPS falló al validar el certificado: puede no ser reconocido, estar vencido o tener una cadena incompleta. Esta fuente no pudo revisarse.",
    TLS_HANDSHAKE:
      "No se pudo negociar la conexión segura con el sitio o el proxy. La revisión sigue pendiente.",
    TLS_CONFIGURATION:
      "El servidor del portal no pudo cargar su configuración de certificados HTTPS. Revisa la configuración de certificados antes de volver a consultar.",
    PROXY_AUTH:
      "El proxy de la red solicita una autenticación que el proceso del portal no tiene disponible. La revisión no pudo realizarse.",
    PROXY_CONFIGURATION:
      "La configuración del proxy no es válida o está incompleta para este proceso. La revisión sigue pendiente.",
    PROXY_CONNECT:
      "No se pudo conectar con la fuente a través del proxy configurado. La revisión sigue pendiente.",
    DNS_ERROR:
      "No se pudo resolver el nombre del sitio oficial. Revisa la resolución DNS y la configuración del proxy en el equipo o servidor donde corre el portal.",
    CONNECT_TIMEOUT:
      "Se agotó el tiempo para conectar con el sitio o el proxy. No se confirmó el acceso a la fuente.",
    READ_TIMEOUT:
      "La conexión se abrió, pero la fuente no respondió a tiempo. La revisión quedó incompleta.",
  };
  const code = error.match(/\[([A-Z_]+)\]/)?.[1];
  if (code && causes[code]) return causes[code];
  if (/espera|conexi[oó]n|timeout|connect|network|DNS/i.test(error))
    return "No se pudo conectar con el sitio oficial. Comprueba que esta computadora o servidor tenga acceso a esa dirección; después vuelve a consultar.";
  if (/robots/i.test(error))
    return "El sitio no permitió verificar sus reglas de consulta automática. Esta revisión quedó pendiente.";
  if (/HTTP\s*(403|429)/i.test(error))
    return "El sitio rechazó o limitó la consulta. Intenta de nuevo más tarde.";
  return "La revisión no pudo completarse. Abre la fuente oficial para comprobarla y consulta el detalle del error.";
}

function Guide({ go }: { go: (view: View) => void }) {
  const { t } = useLanguage();
  return (
    <section className="guide-page">
      <div className="section-intro">
        <h1>{t("Cómo funciona")}</h1>
        <p>
          {t(
            "PLATIICA aporta el catálogo base de NOM vigentes y SIDOF vigila publicaciones del DOF. Ninguna coincidencia determina aplicabilidad legal.",
          )}
        </p>
      </div>
      <ol className="guide-steps">
        {[
          "PLATIICA aporta el catálogo de NOM y SIDOF revisa publicaciones del DOF.",
          "Busca una NOM por producto o revisa publicaciones y evidencia oficial.",
          "Una carga parcial no representa todo el catálogo. Consulta el estado para ver qué falta revisar.",
        ].map((text) => (
          <li key={text}>
            <p>{t(text)}</p>
          </li>
        ))}
      </ol>
      <button className="button paper" onClick={() => go("fuentes")}>
        {t("Estado de fuentes")}
      </button>
    </section>
  );
}
function Icon({ name, size = 18 }: { name: string; size?: number }) {
  if (["arrow", "external", "refresh"].includes(name)) return null;
  const paths: Record<string, ReactNode> = {
    arrow: <path d="M4 12h15m-6-6 6 6-6 6" />,
    external: <path d="M14 4h6v6m0-6L9 15M10 4H4v16h16v-6" />,
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 5 5" />
      </>
    ),
    refresh: <path d="M20 7a9 9 0 1 0 1 8M20 2v6h-6" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    download: <path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4" />,
    plus: <path d="M12 5v14M5 12h14" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.arrow}
    </svg>
  );
}
function DateMark({ value }: { value?: string }) {
  const { language } = useLanguage();
  return (
    <div className="date-mark" aria-hidden="true">
      <strong>{value ? value.slice(8, 10) : "—"}</strong>
      <span>
        {value
          ? new Intl.DateTimeFormat(language === "en" ? "en-US" : "es-MX", {
              month: "short",
              timeZone: "UTC",
            })
              .format(new Date(`${value}T12:00:00Z`))
              .replace(".", "")
          : language === "en"
            ? "n/d"
            : "s/f"}
      </span>
      {value && <small>{value.slice(0, 4)}</small>}
    </div>
  );
}
export function Reader({
  title,
  children,
  close,
  variant = "panel",
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  variant?: "panel" | "document";
}) {
  const { t } = useLanguage();
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key !== "Tab") return;
      const nodes = panel.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), a[href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])',
      );
      if (!nodes?.length) return;
      const first = nodes[0],
        last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, [close]);
  return (
    <div
      className={`reader-backdrop${variant === "document" ? " reader-modal-backdrop" : ""}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <section
        className={`reader${variant === "document" ? " reader-document" : ""}`}
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="reader-header">
          <span>{t(variant === "document" ? "LECTURA DE NORMA" : "ARCHIVO / LECTURA")}</span>
          <button
            className="icon-button"
            aria-label={t("Cerrar lectura")}
            onClick={close}
          >
            <Icon name="close" />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
function PublicationRow({
  item,
  open,
}: {
  item: Row;
  open: (id: number) => void;
}) {
  const { t, format } = useLanguage();
  return (
    <article className="publication-row">
      <DateMark value={item.published_on} />
      <div className="publication-copy">
        <div className="article-kicker">
          <span>{t(item.source_name)}</span>
          <span>{t(types[item.kind] || "Publicación")}</span>
          {item.has_changes && (
            <b className="change-flag">{t("Cambio detectado")}</b>
          )}
          {item.is_demo && (
            <b className="demo-flag">{t("Muestra sintética")}</b>
          )}
        </div>
        <button
          className="headline-link"
          lang="es"
          onClick={() => open(item.id)}
        >
          {item.title}
        </button>
        {item.excerpt && (
          <p className="article-excerpt" lang="es">
            {item.excerpt}
          </p>
        )}
        <div className="article-meta">
          <span>
            {item.published_on
              ? format(item.published_on)
              : t("Sin fecha oficial confirmada")}
          </span>
          <span>
            {t("Detectado {date}", { date: format(item.detected_at) })}
          </span>
          {item.norm_status && (
            <span>
              {t("Estado oficial")}: {item.norm_status}
            </span>
          )}
          {item.official_id && <span>{item.official_id}</span>}
        </div>
        {item.product_scope && (
          <p className="article-excerpt">
            {t("Producto/servicio en PLATIICA")}: {item.product_scope}
          </p>
        )}
      </div>
      <button
        className="read-arrow"
        onClick={() => open(item.id)}
        aria-label={t("Leer {title}", { title: item.title })}
      >
        <Icon name="arrow" size={23} />
      </button>
    </article>
  );
}

export default function Portal() {
  return (
    <LanguageProvider>
      <Bulletin />
    </LanguageProvider>
  );
}

function Bulletin() {
  const { language, setLanguage, t, format } = useLanguage();
  const [view, setView] = useState<View>(() =>
    views.some((v) => v.id === location.hash.slice(1))
      ? (location.hash.slice(1) as View)
      : "actualidad",
  );
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [token, setToken] = useState("");
  const [ready, setReady] = useState(false);
  const [me, setMe] = useState<Row | null>(null);
  const [dashboard, setDashboard] = useState<Row>({});
  const [publications, setPublications] = useState<Row[]>([]);
  const [jobs, setJobs] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [productMode, setProductMode] = useState<"fraccion" | "descripcion">("fraccion");
  const [productValue, setProductValue] = useState("");
  const [productSearch, setProductSearch] = useState<Row | null>(null);
  const [productBusy, setProductBusy] = useState(false);
  const [trackedProduct, setTrackedProduct] = useState<Row | null>(null);
  const [trackedProducts, setTrackedProducts] = useState<Row[]>([]);
  const [productAlerts, setProductAlerts] = useState<Row[]>([]);
  const [source, setSource] = useState("");
  const [period, setPeriod] = useState("all");
  const [kind, setKind] = useState("");
  const [changes, setChanges] = useState(false);
  const [demo, setDemo] = useState(false);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [detail, setDetail] = useState<Row | null>(null);
  const [readerBusy, setReaderBusy] = useState(false);
  const [readerError, setReaderError] = useState(false);
  const readerGeneration = useRef(0);
  const readerRequest = useRef<AbortController | null>(null);
  const portalRequest = useRef<AbortController | null>(null);
  const portalLoading = useRef(false);
  const [inspection, setInspection] = useState<Row | null>(null);
  const [versionId, setVersionId] = useState<number | null>(null);
  const generation = useRef(0);
  const sources: Row[] = (dashboard.sources || []).filter(
    (s: Row) => ["sidof", "platiica_catalog"].includes(s.kind) && s.active,
  );
  const activeJobs = jobs.some((j) => ["queued", "running"].includes(j.status));
  const admin = me?.role === "administrador";
  const request = useCallback(
    async (path: string, method = "GET", body?: Row, signal?: AbortSignal) => {
      const current = await accessToken(token);
      const response = await fetch(`/api${path}`, {
        method,
        signal,
        headers: {
          ...(current ? { Authorization: `Bearer ${current}` } : {}),
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : "No se pudo completar la solicitud. Intenta de nuevo.",
        );
      }
      return response.json();
    },
    [token],
  );
  const loadReading = useMemo(() => createReadingLoader(
    (path, signal) => request(path, "GET", undefined, signal)), [request]);
  useEffect(() => () => {
    readerRequest.current?.abort();
    portalRequest.current?.abort();
  }, []);
  useEffect(() => {
    let live = true;
    void authConfig()
      .then(async (value) => {
        if (!live) return;
        setConfig(value);
        const restored = await restoreSession();
        if (live) {
          setToken(restored);
          setReady(true);
        }
      })
      .catch((e) => {
        if (live) {
          setError(e.message);
          setBusy(false);
        }
      });
    return () => {
      live = false;
    };
  }, []);
  const load = useCallback(
    async (quiet = false) => {
      if (!ready || quiet && portalLoading.current) return;
      portalRequest.current?.abort();
      const controller = new AbortController();
      portalRequest.current = controller;
      portalLoading.current = true;
      const id = ++generation.current;
      if (!quiet) setBusy(true);
      const params = new URLSearchParams({
        page: String(page),
        page_size: "15",
        sort: "published",
        source_kind: view === "historico" ? "platiica_catalog" : "sidof",
        is_demo: String(demo),
      });
      if (query.trim()) params.set("q", query.trim());
      if (source) params.set("source_id", source);
      if (kind) params.set("kind", kind);
      if (period !== "all")
        params.set("published_since", dayStamp(Number(period) - 1));
      if (changes) params.set("changes_only", "true");
      try {
        const [person, overview, list, runs] = await Promise.all([
          request("/me", "GET", undefined, controller.signal),
          request("/dashboard", "GET", undefined, controller.signal),
          request(`/publications?${params}`, "GET", undefined, controller.signal),
          request("/jobs?page_size=12&summary=true", "GET", undefined, controller.signal),
        ]);
        if (id !== generation.current) return;
        setMe(person);
        setDashboard(overview);
        setPublications(list.items);
        setTotal(list.total);
        setJobs(
          runs.items.filter((job: Row) =>
            overview.sources.some(
              (s: Row) =>
                s.id === job.source_id &&
                ["sidof", "platiica_catalog"].includes(s.kind),
            ),
          ),
        );
        setError("");
      } catch (e) {
        if (id === generation.current && !controller.signal.aborted) setError((e as Error).message);
      } finally {
        if (id === generation.current) {
          setBusy(false);
          portalLoading.current = false;
        }
      }
    },
    [ready, request, page, query, source, kind, period, changes, demo, view],
  );
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query ? 250 : 0);
    return () => clearTimeout(timer);
  }, [load, query]);
  useEffect(() => {
    // The server monitor continues running; the hidden bulletin need not poll
    // while the user is reading a document or inspecting an earlier check.
    if (detail || inspection) return;
    const timer = window.setInterval(
      () => {
        if (document.visibilityState === "visible") void load(true);
      },
      activeJobs ? 5000 : 60000,
    );
    return () => clearInterval(timer);
  }, [load, activeJobs, !!detail, !!inspection]);
  useEffect(() => {
    const changed = () => {
      const next = location.hash.slice(1);
      if (views.some((v) => v.id === next)) {
        setView(next as View);
        setSource("");
        setKind("");
        setPeriod("all");
        setChanges(false);
        setPage(1);
      }
    };
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 8000);
    return () => clearTimeout(timer);
  }, [notice]);
  const navigate = (next: View) => {
    setView(next);
    location.hash = next;
    setSource("");
    setKind("");
    setPeriod("all");
    setChanges(false);
    setPage(1);
  };
  const reset = () => {
    setQuery("");
    setSource("");
    setKind("");
    setPeriod("all");
    setChanges(false);
    setPage(1);
  };
  const retry = async () => {
    try {
      if (!ready) {
        setConfig(await authConfig());
        setToken(await restoreSession());
        setReady(true);
      } else await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const refresh = async () => {
    setUpdating(true);
    try {
      const result = await request("/refresh", "POST");
      setNotice(
        result.jobs.length
          ? "Consultando las fuentes. Los resultados aparecerán aquí al terminar."
          : result.recent_sources
            ? "Hay consultas recientes. Espera un minuto tras una revisión fallida o 15 minutos tras una revisión correcta antes de repetir."
            : "Configura una fuente para comenzar.",
      );
      if (!result.monitor_enabled && result.jobs.length)
        setNotice(
          "Consulta en cola. Inicia el portal con MONITOR_ENABLED=true para procesarla.",
        );
      await load(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUpdating(false);
    }
  };
  const searchProduct = async (event: FormEvent) => {
    event.preventDefault();
    setProductBusy(true);
    setProductSearch(null);
    setTrackedProduct(null);
    setProductAlerts([]);
    setError("");
    try {
      setProductSearch(
        await request("/product-search", "POST", {
          mode: productMode,
          value: productValue,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setProductBusy(false);
    }
  };
  const loadProductAlerts = useCallback(
    async (catalogId: number) => {
      const result = await request(`/alerts?catalog_id=${catalogId}&page_size=50`);
      setProductAlerts(result.items);
    },
    [request],
  );
  const saveProductForMonitoring = async () => {
    const digits = productValue.replace(/\D/g, "");
    const stopWords = new Set([
      "and", "con", "del", "desde", "for", "las", "los", "para", "por",
      "the", "una", "uno", "unos", "unas", "uso", "de", "el", "en", "la", "o", "y",
    ]);
    if (
      productMode === "fraccion" &&
      (!/^[0-9.\s-]+$/.test(productValue.trim()) || ![8, 10].includes(digits.length))
    ) {
      setError("Ingresa una fracción mexicana de 8 dígitos, o 10 con NICO.");
      return;
    }
    const words =
      productMode === "descripcion"
        ? Array.from(
            new Set(
              (productValue.toLocaleLowerCase().match(/[\p{L}\p{N}]{3,}/gu) || [])
                .filter((word) => !stopWords.has(word)),
            ),
          ).slice(0, 100)
        : [];
    if (productMode === "descripcion" && words.length === 0) {
      setError("Agrega palabras descriptivas del producto, como tipo, material o uso.");
      return;
    }
    setProductBusy(true);
    setError("");
    try {
      const item = await request("/catalog", "POST", {
        kind: "producto",
        name:
          productMode === "fraccion"
            ? `Fracción MX ${digits}`
            : productValue.trim().slice(0, 300),
        description:
          productMode === "fraccion"
            ? `Seguimiento por fracción arancelaria mexicana ${digits}`
            : productValue.trim(),
        tariff_code: productMode === "fraccion" ? digits.slice(0, 8) : null,
        nico: productMode === "fraccion" && digits.length === 10 ? digits.slice(8) : null,
        keywords: words,
        synonyms: [],
        watched_norms: [],
        technical: {},
        owner: me?.id || "JE",
        active: true,
        is_demo: false,
      });
      setTrackedProduct(item);
      setTrackedProducts((items) => [item, ...items.filter((existing) => existing.id !== item.id)]);
      await loadProductAlerts(item.id);
      setNotice("Producto guardado para seguimiento automático de publicaciones y posibles coincidencias.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setProductBusy(false);
    }
  };
  useEffect(() => {
    if (view !== "producto" || !trackedProduct?.id) return;
    const timer = window.setInterval(() => {
      void loadProductAlerts(trackedProduct.id).catch((e) => setError((e as Error).message));
    }, 30000);
    return () => clearInterval(timer);
  }, [view, trackedProduct?.id, loadProductAlerts]);
  useEffect(() => {
    if (!ready || !admin || view !== "producto") return;
    let live = true;
    void request("/catalog?kind=producto&active=true&is_demo=false&page_size=100")
      .then((result) => {
        if (live) setTrackedProducts(result.items);
      })
      .catch((e) => {
        if (live) setError((e as Error).message);
      });
    return () => {
      live = false;
    };
  }, [ready, admin, view, request]);
  const open = async (id: number) => {
    const current = ++readerGeneration.current;
    readerRequest.current?.abort();
    const controller = ne…9518 tokens truncated…                          ? "Última revisión completa"
                              : "Pendiente de consultar",
                        )}
                      </span>
                    </div>
                    <h2>{sourceName(item)}</h2>
                    <p>
                      {t(
                        item.kind === "platiica_catalog"
                          ? "Inventario oficial de fichas NOM. La carga inicial y las actualizaciones se procesan por lotes."
                          : "Publicaciones oficiales SIDOF por fecha. Se guardan el texto disponible y una copia del original.",
                      )}
                    </p>
                    {item.kind === "platiica_catalog" &&
                      item.latest_check_status === "running" && (
                        <div className="pending-dates">
                          <strong>{t("Progreso de la carga")}</strong>
                          <p>
                            {item.catalog_discovered_count == null
                              ? t("Descubriendo fichas en los sitemaps oficiales.")
                              : t(
                                  "{reviewed} revisadas de {discovered} fichas detectadas; {pending} pendientes y {unchanged} sin cambios.",
                                  {
                                    reviewed: item.latest_check_reviewed_count || 0,
                                    discovered: item.catalog_discovered_count,
                                    pending: item.pending_items,
                                    unchanged: item.catalog_unchanged_count || 0,
                                  },
                                )}
                          </p>
                        </div>
                      )}
                    {item.latest_check_status === "running" &&
                      item.latest_check_heartbeat_at &&
                      Date.now() - Date.parse(item.latest_check_heartbeat_at) > 120_000 && (
                        <div className="source-failure">
                          <p>
                            {t(
                              "El proceso no ha enviado una señal reciente. Reinicia el portal para recuperar la consulta interrumpida; el trabajo pendiente se conserva.",
                            )}
                          </p>
                        </div>
                      )}
                    {
                      <details className="source-notes">
                        <summary>{t("Notas originales de la fuente")}</summary>
                        <p lang="es">{item.coverage}</p>
                      </details>
                    }
                    {item.urls.map((url: string) => (
                      <a
                        key={url}
                        className="source-url"
                        href={link(
                          dailySource(item)
                            ? "https://sidof.segob.gob.mx/"
                            : url,
                        )}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {dailySource(item)
                          ? t("Abrir el portal oficial de SIDOF")
                          : displayUrl(url)}
                        <Icon name="external" size={14} />
                      </a>
                    ))}
                    {item.pending_dates?.length > 0 && (
                      <div className="pending-dates">
                        <strong>{t(
                          dailySource(item) && item.last_error?.split("\n").every((line: string) => missingIndexError(line))
                            ? "Fechas sin índice verificable"
                            : "Fechas pendientes de verificar",
                        )}</strong>
                        <p>
                          {item.pending_dates
                            .map((day: string) => format(day))
                            .join(" · ")}
                        </p>
                      </div>
                    )}
                    {dailySource(item) && item.recent_checked_dates?.length > 0 && (
                      <div className="pending-dates">
                        <strong>{t("Fechas con índice revisado")}</strong>
                        <p>{item.recent_checked_dates.map((day: string) => format(day)).join(" · ")}</p>
                      </div>
                    )}
                    {dailySource(item) && item.confirmed_absence_dates?.length > 0 && (
                      <div className="pending-dates">
                        <strong>{t("Fechas sin publicación según el calendario oficial")}</strong>
                        <p>{item.confirmed_absence_dates.map((day: string) => format(day)).join(" · ")}</p>
                      </div>
                    )}
                    {item.kind === "platiica_catalog" && item.pending_items > 0 && (
                      <div className="pending-dates">
                        <strong>{t("Fichas pendientes de revisar")}</strong>
                        <p>{item.pending_items}</p>
                      </div>
                    )}
                    <p className="schedule-note">
                      {t(
                        "El servidor consulta esta fuente automáticamente según la frecuencia indicada. Puedes cerrar el navegador; el servidor debe seguir encendido.",
                      )}
                    </p>
                    {item.last_error && (
                      <div className="source-failure">
                        <p>
                          {t(
                            dailySource(item) && missingIndexError(item.last_error)
                              ? sourceIssue(item.last_error)
                              : total > 0
                              ? "Hay publicaciones guardadas. La última revisión quedó incompleta."
                              : sourceIssue(item.last_error),
                          )}
                        </p>
                        <details className="source-problem">
                          <summary>{t(dailySource(item) && missingIndexError(item.last_error)
                            ? "Detalle de fechas pendientes" : "Detalle original del error")}</summary>
                          <p lang="es">{item.last_error}</p>
                        </details>
                      </div>
                    )}
                    {admin && (
                      <details className="source-editor">
                        <summary>{t("Editar seguimiento")}</summary>
                        <form onSubmit={(e) => void saveSource(e, item)}>
                          <label>
                            {t("Páginas a consultar, una por línea")}
                            <textarea
                              name="urls"
                              defaultValue={item.urls.join("\n")}
                              rows={3}
                              readOnly={item.kind === "platiica_catalog"}
                              required
                            />
                          </label>
                          <div className="editor-grid">
                            <label>
                              {t("Frecuencia en horas")}
                              <input
                                name="frequency"
                                type="number"
                                min="1"
                                max="8760"
                                defaultValue={item.frequency_hours}
                                required
                              />
                            </label>
                            <label>
                              {t("Consultar desde")}
                              <input
                                name="start"
                                type="date"
                                max={dayStamp()}
                                defaultValue={item.schedule_start || dayStamp()}
                              />
                            </label>
                          </div>
                          <label>
                            {t("Referencia esperada, opcional")}
                            <input
                              name="expected"
                              defaultValue={(item.expected_terms || []).join(
                                ", ",
                              )}
                              readOnly={item.kind === "platiica_catalog"}
                            />
                          </label>
                          <label className="check-filter">
                            <input
                              type="checkbox"
                              name="enabled"
                              defaultChecked={item.schedule_enabled}
                            />
                            {t("Revisión automática de esta fuente")}
                          </label>
                          <button className="button ink" disabled={updating}>
                            {t("Guardar seguimiento")}
                          </button>
                        </form>
                      </details>
                    )}
                  </div>
                  <dl className="directory-meta">
                    <div>
                      <dt>{t("Último intento")}</dt>
                      <dd>{format(item.last_attempt_at, true)}</dd>
                    </div>
                    <div>
                      <dt>{t("Publicaciones guardadas")}</dt>
                      <dd>{item.publication_count || 0}</dd>
                    </div>
                    <div>
                      <dt>{t("Última descarga")}</dt>
                      <dd>{format(item.last_download_at, true)}</dd>
                    </div>
                    <div>
                      <dt>{t("Última revisión completa")}</dt>
                      <dd>{format(item.last_full_review_at, true)}</dd>
                    </div>
                    <div>
                      <dt>{t("Frecuencia")}</dt>
                      <dd>
                        {item.schedule_enabled
                          ? t("Cada {hours} h", { hours: item.frequency_hours })
                          : t("Manual")}
                      </dd>
                    </div>
                    <div>
                      <dt>{t("Próxima consulta automática")}</dt>
                      <dd>
                        {item.schedule_enabled &&
                        dashboard.scheduler_enabled &&
                        dashboard.monitor_enabled
                          ? format(item.next_due_at, true)
                          : t("Manual")}
                      </dd>
                    </div>
                  </dl>
                </article>
              ))}
            </section>
            <section className="run-log">
              <div className="section-rule">
                <h2>{t("Registro de consultas")}</h2>
                <span>{t("Últimas ejecuciones")}</span>
              </div>
              {jobs.length === 0 ? (
                <p className="log-empty">
                  {t("Todavía no se ha solicitado una consulta.")}
                </p>
              ) : (
                jobs.map((job) => (
                  <div key={job.id} className="run-line">
                    <span className={`run-state ${job.status}`}>
                      {t(jobNames[job.status] || job.status)}
                    </span>
                    <strong>
                      {sourceName(sources.find((s) => s.id === job.source_id))}
                    </strong>
                    <span>{format(job.requested_at, true)}</span>
                    <small>
                      {t(
                        job.status === "failed"
                          ? "Revisión fallida; novedades sin confirmar"
                          : "{new} nuevos · {changes} cambios",
                        {
                          new: job.new_count,
                          changes: job.modified_count,
                        },
                      )}
                      {job.error_count > 0
                        ? t(dailySource(sources.find((s) => s.id === job.source_id)) &&
                            job.error?.split("\n").every((line: string) => missingIndexError(line))
                            ? " · {count} fechas sin índice verificable" : " · {count} errores",
                          { count: job.error_count })
                        : ""}
                    </small>
                    <div className="run-actions">
                      {dailySource(
                        sources.find((s) => s.id === job.source_id),
                      ) && (
                        <button
                          className="text-button"
                          onClick={() =>
                            void request(`/jobs/${job.id}`)
                              .then(setInspection)
                              .catch((e) => setError(e.message))
                          }
                        >
                          {t("Ver revisión diaria")}
                        </button>
                      )}
                      {admin &&
                        ["failed", "partial", "interrupted"].includes(
                          job.status,
                        ) && (
                          <button
                            className="text-button"
                            disabled={updating}
                            onClick={() => {
                              setUpdating(true);
                              void request("/jobs", "POST", {
                                source_id: job.source_id,
                                resume_job_id: job.id,
                              })
                                .then(() => load(true))
                                .catch((e) => setError(e.message))
                                .finally(() => setUpdating(false));
                            }}
                          >
                            {t("Retomar")}
                            <Icon name="arrow" size={14} />
                          </button>
                        )}
                    </div>
                  </div>
                ))
              )}
            </section>
          </>
        )}
      </main>
      <footer className="colophon">
        <a href="#actualidad" onClick={() => navigate("actualidad")}>
          norma<span>.</span>
        </a>
        <p>
          NOM Monitor · Johnson Electric
          <br />
          <span>{t("Un punto de consulta para la normativa mexicana.")}</span>
        </p>
        <div>
          <span>SIDOF</span>
          {config?.demo_enabled && (
            <label>
              <input
                type="checkbox"
                checked={demo}
                onChange={(e) => {
                  setDemo(e.target.checked);
                  setPage(1);
                }}
              />
              {t("Ver muestras sintéticas")}
            </label>
          )}
          {config?.mode === "entra" && me?.auth_mode === "entra" && (
            <button className="text-button" onClick={() => void signOut()}>
              {t("Cerrar sesión")}
            </button>
          )}
        </div>
      </footer>
      {detail && (
        <Reader title={detail.title} close={closeReader} variant="document">
          <div className="reader-body document-reader-body">
            <div className="document-heading">
              <div className="article-kicker">
                <span>{detail.source_name ? t(detail.source_name) : "SIDOF"}</span>
                <span>{t(types[detail.kind] || "Publicación")}</span>
                {detail.is_demo && <b className="demo-flag">{t("Muestra sintética")}</b>}
              </div>
              <h1 lang="es">{detail.title}</h1>
              <div className="document-meta">
                {detail.published_on && <time dateTime={detail.published_on}>{format(detail.published_on)}</time>}
                <span>{t("Texto oficial en español")}</span>
                {link(detail.url) && (
                  <a href={link(detail.url)} target="_blank" rel="noreferrer">
                    {t("Abrir en la fuente oficial")} <Icon name="external" size={14} />
                  </a>
                )}
              </div>
            </div>
            {readerBusy ? (
              <div className="reader-skeleton" role="status">
                <p>{t("Preparando lectura…")}</p>
                <span aria-hidden="true" /><span aria-hidden="true" /><span aria-hidden="true" />
              </div>
            ) : readerError ? (
              <div className="reader-load-error" role="alert">
                <p>{t("El documento no pudo cargarse. Vuelve a intentarlo.")}</p>
                <button className="button paper" onClick={() => void open(detail.id)}>{t("Reintentar")}</button>
              </div>
            ) : selected ? (
              <>
                {detail.versions.length > 1 && (
                  <label className="document-version-select">
                    {t("Versión del documento")}
                    <select value={selected.id} onChange={(event) => setVersionId(Number(event.target.value))}>
                      {detail.versions.map((version: Row) => (
                        <option key={version.id} value={version.id}>
                          {t("Versión {number}", { number: version.sequence })} · {format(version.captured_at)}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <DocumentReading key={selected.id} version={selected as { id: number; content?: string }} load={loadReading} />
                <div className="document-utility">
                  {selected.evidence_key && (
                    <button className="button paper" onClick={() => void download(selected)}>
                      <Icon name="download" />{t("Descargar copia consultada")}
                    </button>
                  )}
                  <details className="document-context">
                    <summary>{t("Información de la copia")}</summary>
                    <p>{t("Copia consultada el {date}.", { date: format(selected.captured_at, true) })}</p>
                    <p>{t("DETECTADO EN EL BOLETÍN")}: {format(detail.detected_at, true)}</p>
                    {detail.processing_note && <p lang="es">{detail.processing_note}</p>}
                  </details>
                </div>
              </>
            ) : (
              <p className="capture-caption">{t("Todavía no hay una copia del documento disponible.")}</p>
            )}
          </div>
        </Reader>
      )}
      {inspection && (
        <Reader title={t("Revisión diaria SIDOF")} close={closeInspection}>
          <div className="reader-body">
            <span className="eyebrow">SIDOF / API</span>
            <h1>{t("Qué se revisó")}</h1>
            <p className="capture-caption">
              {t(
                "Las notas son todas las publicaciones del diario, no todas son NOM. Las referencias sin texto o título requieren revisión adicional.",
              )}
            </p>
            {inspection.index_checks?.some((check: Row) => !check.declared_no_publication) && (
              <p>{t("{count} fechas con índice revisado en esta ejecución", {
                count: inspection.index_checks.filter((check: Row) => !check.declared_no_publication).length,
              })}</p>
            )}
            {inspection.continuation?.queue?.length > 0 && (
              <div className="pending-dates">
                <strong>{t("Fechas pendientes de verificar")}</strong>
                <p>{inspection.continuation.queue
                  .map((item: Row) => format(item.day))
                  .join(" · ")}</p>
              </div>
            )}
            {(inspection.index_checks || []).length === 0 && (
              <p>
                {t("Todavía no hay un día completo registrado en este lote.")}
              </p>
            )}
            {(inspection.index_checks || []).map(
              (check: Row, index: number) => (
                <section className="daily-check" key={`${check.day}-${index}`}>
                  <h2>{format(check.day)}</h2>
                  {!check.declared_no_publication && <p>
                    {t(
                      "{notes} notas revisadas · {selected} publicaciones seleccionadas",
                      {
                        notes: check.notes_checked,
                        selected: check.selected_ids.length,
                      },
                    )}
                  </p>}
                  {check.declared_no_publication && (
                    <p>
                      {t(
                        "El calendario oficial de SIDOF identifica esta fecha sin publicación.",
                      )}
                    </p>
                  )}
                  {check.declared_no_publication && check.calendar_url && (
                    <a className="source-url" href={link(check.calendar_page_url || check.calendar_url)}
                      target="_blank" rel="noreferrer">{t("Consultar calendario oficial")}</a>
                  )}
                  {check.recovered_references?.length > 0 && (
                    <details className="source-notes">
                      <summary>{t("{count} referencias recuperadas del PDF oficial", {
                        count: check.recovered_references.length,
                      })}</summary>
                      {check.recovered_references.map((item: Row) => (
                        <p key={item.id}>
                          <a href={link(`${item.url}#page=${item.page}`)} target="_blank" rel="noreferrer">
                            {item.id} · {t("Página {page}", { page: item.page })}
                          </a>{" · "}{item.title}
                        </p>
                      ))}
                    </details>
                  )}
                  {check.selected_ids.map((id: string) => (
                    <span className="daily-id" key={id}>
                      {id}
                    </span>
                  ))}
                  {check.unresolved?.length > 0 && (
                    <div className="source-failure">
                      <strong>
                        {t("{count} referencias pendientes de revisión", {
                          count: check.unresolved.length,
                        })}
                      </strong>
                      <p>
                        {t(
                          "El servicio no proporcionó título o texto suficiente para clasificarlas. No se descartaron como irrelevantes.",
                        )}
                      </p>
                      {check.unresolved.map((item: Row) => (
                        <a
                          key={item.id}
                          className="source-url"
                          href={link(item.url)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {item.id}
                          <Icon name="external" size={14} />
                        </a>
                      ))}
                    </div>
                  )}
                </section>
              ),
            )}
            {inspection.error && (
              <div className="notification error">
                <p>{t(sourceIssue(inspection.error))}</p>
                <details>
                  <summary>{t("Detalles técnicos")}</summary>
                  <p lang="es">{inspection.error}</p>
                </details>
              </div>
            )}
          </div>
        </Reader>
      )}
    </div>
  );
}
