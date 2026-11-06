import { useCallback, useEffect, useRef, useState } from "react";
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
function sourceIssue(error: string) {
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
    </div>
  );
}
export function Reader({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
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
        "button:not(:disabled), a[href], input, select, textarea, summary",
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
      className="reader-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <section
        className="reader"
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="reader-header">
          <span>{t("ARCHIVO / LECTURA")}</span>
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
  const [inspection, setInspection] = useState<Row | null>(null);
  const [versionId, setVersionId] = useState<number | null>(null);
  const generation = useRef(0);
  const sources: Row[] = (dashboard.sources || []).filter(
    (s: Row) => ["sidof", "platiica_catalog"].includes(s.kind) && s.active,
  );
  const activeJobs = jobs.some((j) => ["queued", "running"].includes(j.status));
  const admin = me?.role === "administrador";
  const request = useCallback(
    async (path: string, method = "GET", body?: Row) => {
      const current = await accessToken(token);
      const response = await fetch(`/api${path}`, {
        method,
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
      if (!ready) return;
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
          request("/me"),
          request("/dashboard"),
          request(`/publications?${params}`),
          request("/jobs?page_size=12"),
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
        if (id === generation.current) setError((e as Error).message);
      } finally {
        if (id === generation.current) setBusy(false);
      }
    },
    [ready, request, page, query, source, kind, period, changes, demo, view],
  );
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query ? 250 : 0);
    return () => clearTimeout(timer);
  }, [load, query]);
  useEffect(() => {
    const timer = window.setInterval(
      () => {
        if (document.visibilityState === "visible") void load(true);
      },
      activeJobs ? 5000 : 60000,
    );
    return () => clearInterval(timer);
  }, [load, activeJobs]);
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
    try {
      const doc = await request(`/publications/${id}`);
      setDetail(doc);
      setVersionId(doc.versions[0]?.id || null);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const closeReader = useCallback(() => setDetail(null), []);
  const closeInspection = useCallback(() => setInspection(null), []);
  const download = async (version: Row) => {
    try {
      const current = await accessToken(token);
      const response = await fetch(`/api/versions/${version.id}/evidence`, {
        headers: current ? { Authorization: `Bearer ${current}` } : {},
      });
      if (!response.ok)
        throw new Error(t("No fue posible recuperar esta copia."));
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `norma-${version.id}${version.media_type?.includes("pdf") ? ".pdf" : version.media_type?.includes("json") ? ".json" : ".html"}`;
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const saveSource = async (event: FormEvent<HTMLFormElement>, item: Row) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setUpdating(true);
    try {
      await request(`/sources/${item.id}`, "PATCH", {
        urls: String(form.get("urls"))
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
        frequency_hours: Number(form.get("frequency")),
        expected_terms: String(form.get("expected"))
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        schedule_enabled: form.get("enabled") === "on",
        schedule_start: String(form.get("start")) || dayStamp(),
      });
      setNotice("Seguimiento actualizado.");
      await load(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUpdating(false);
    }
  };
  const latest = sources
    .map((s) => s.last_download_at as string)
    .filter(Boolean)
    .sort()
    .at(-1);
  const activeSources = sources.filter((s) => s.active);
  const failedSources = activeSources.filter((s) => s.last_error);
  const allFailed =
    activeSources.length > 0 && failedSources.length === activeSources.length;
  const sourceName = (s?: Row) =>
    s?.kind === "sidof"
      ? t(
          dailySource(s)
            ? "SIDOF · publicaciones diarias"
            : "SIDOF · documento de referencia",
        )
      : s?.kind === "platiica_catalog"
        ? t("Catálogo Mexicano de Normas · PLATIICA")
        : s?.name || t("Fuente");
  const lead = publications[0];
  const selected = detail?.versions.find((v: Row) => v.id === versionId);
  const filtered = Boolean(
    query || source || kind || changes || period !== "all",
  );
  const date = new Intl.DateTimeFormat(language === "en" ? "en-US" : "es-MX", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "America/Mexico_City",
  }).format(new Date());
  return (
    <div className="newspaper">
      <a className="skip-link" href="#contenido">
        {t("Ir al contenido")}
      </a>
      <div className="edition-strip">
        <span>
          JE / NOM MONITOR <b className="release-mark">v{portalVersion}</b>
        </span>
        <div className="edition-right">
          <span>{date}</span>
          <div
            className="language-switch"
            role="group"
            aria-label={t("Idioma")}
          >
            <button
              lang="es"
              aria-label="Español"
              aria-pressed={language === "es"}
              onClick={() => setLanguage("es")}
            >
              Español
            </button>
            <button
              lang="en"
              aria-label="English"
              aria-pressed={language === "en"}
              onClick={() => setLanguage("en")}
            >
              English
            </button>
          </div>
        </div>
      </div>
      <header className="masthead">
        <a
          className="wordmark"
          href="#actualidad"
          onClick={() => navigate("actualidad")}
          aria-label={t("NOM Monitor, inicio")}
        >
          norma<span className="wordmark-point">.</span>
          <span className="wordmark-caption">
            {t("UN BOLETÍN DE JOHNSON ELECTRIC")}
          </span>
        </a>
        <button
          className={`button ink ${activeJobs ? "is-running" : ""}`}
          onClick={() => void refresh()}
          disabled={!ready || updating || activeJobs}
        >
          <Icon name="refresh" />
          {t(
            activeJobs
              ? "Consultando…"
              : updating
                ? "Solicitando…"
                : "Consultar fuentes",
          )}
        </button>
      </header>
      <nav className="section-nav" aria-label={t("Navegación principal")}>
        <div>
          {views.map((item) => (
            <button
              key={item.id}
              className={view === item.id ? "selected" : ""}
              onClick={() => navigate(item.id)}
              aria-current={view === item.id ? "page" : undefined}
            >
              {t(item.name)}
            </button>
          ))}
        </div>
        <span className="edition-label">
          {t(
            me?.auth_mode === "development"
              ? "EDICIÓN LOCAL"
              : "CONSULTA ABIERTA",
          )}
        </span>
      </nav>
      <main id="contenido">
        {error && (
          <div role="alert" className="notification error">
            <span>
              {t(
                error === "Failed to fetch"
                  ? "No se pudo conectar con el portal. Comprueba que INICIAR_LOCAL esté abierto y vuelve a cargar."
                  : error,
              )}
            </span>
            <button className="text-button" onClick={() => void retry()}>
              {t("Volver a intentar")}
            </button>
          </div>
        )}
        {notice && (
          <div role="status" className="notification notice">
            {t(notice)}
          </div>
        )}
        {!busy && failedSources.length > 0 && (
          <section className="coverage-alert" role="status">
            <span className="coverage-symbol" aria-hidden="true">
              !
            </span>
            <div>
              <strong>
                {t(
                  allFailed
                    ? "Hay fechas pendientes de verificar."
                    : "Hay fechas pendientes de verificar.",
                )}
              </strong>
              <p>
                {t(
                  "{count} publicaciones guardadas. Abre el detalle para ver qué falta revisar.",
                  {
                    count: sources.reduce(
                      (sum, item) => sum + (item.publication_count || 0),
                      0,
                    ),
                  },
                )}
              </p>
            </div>
            <button className="text-button" onClick={() => navigate("fuentes")}>
              {t("Ver qué pasó")}
              <Icon name="arrow" />
            </button>
          </section>
        )}
        {config?.mode === "entra" && !me && !busy && (
          <div className="notification">
            <span>
              {t("Esta instalación tiene acceso Microsoft habilitado.")}
            </span>
            <button
              className="button ink"
              onClick={() => void signIn().catch((e) => setError(e.message))}
            >
              {t("Iniciar sesión")}
            </button>
          </div>
        )}
        {view === "actualidad" && (
          <section className="front-intro">
            <div>
              <span className="eyebrow">{t("EL BOLETÍN")}</span>
              <h1>
                {t("Publicaciones NOM")}
                <br />
                <span className="intro-subtitle">
                  {t("Publicaciones oficiales de SIDOF.")}
                </span>
              </h1>
            </div>
            <div className="intro-note">
              <p>
                {t(
                  "Consulta las fuentes, lee lo que se publicó y comprueba qué cambió en los documentos guardados.",
                )}
              </p>
              <div className="last-check">
                <i
                  className={
                    activeJobs
                      ? "status-dot working"
                      : latest
                        ? "status-dot good"
                        : "status-dot"
                  }
                />
                <span>
                  {activeJobs
                    ? t("Revisión en curso")
                    : latest
                      ? t("Última descarga: {date}", {
                          date: format(latest, true),
                        })
                      : allFailed
                        ? t("La revisión necesita atención")
                        : t("La primera consulta está pendiente")}
                </span>
              </div>
            </div>
          </section>
        )}
        {view === "guia" && <Guide go={navigate} />}
        {view === "producto" && (
          <section className="product-search-page">
            <div className="section-intro">
              <span className="eyebrow">{t("REVISIÓN PRELIMINAR")}</span>
              <h1>
                {t("Consultar por producto")}
                <span className="accent">.</span>
              </h1>
              <p>
                {t(
                  "Ingresa una fracción arancelaria mexicana o describe el producto. Buscaremos coincidencias textuales en NOM vigentes del catálogo PLATIICA y publicaciones SIDOF guardadas.",
                )}
              </p>
            </div>
            <form className="product-search-form" onSubmit={(event) => void searchProduct(event)}>
              <label>
                {t("Buscar por")}
                <select
                  value={productMode}
                  onChange={(event) => {
                    setProductMode(event.target.value as "fraccion" | "descripcion");
                    setProductSearch(null);
                  }}
                >
                  <option value="fraccion">{t("Fracción arancelaria mexicana")}</option>
                  <option value="descripcion">{t("Descripción del producto")}</option>
                </select>
              </label>
              <label className="product-query">
                {productMode === "fraccion"
                  ? t("Fracción arancelaria / NICO")
                  : t("Descripción, materiales o uso")}
                <input
                  required
                  maxLength={500}
                  value={productValue}
                  onChange={(event) => setProductValue(event.target.value)}
                  placeholder={
                    productMode === "fraccion"
                      ? t("Ej. 8501.10.01 o 8501.10.01 00")
                      : t("Ej. motor eléctrico de corriente continua para actuador")
                  }
                />
              </label>
              <button className="button ink" type="submit" disabled={!ready || productBusy}>
                <Icon name="search" />
                {t(productBusy ? "Buscando…" : "Buscar posibles coincidencias")}
              </button>
            </form>
            <p className="product-search-hint">
              {t(
                "La fracción admite 8 dígitos o 10 con NICO. Para descripción, incluye tipo de producto, material y uso cuando los conozcas.",
              )}
            </p>
            {admin && (
              <div className="product-tracking-control">
                <p>
                  {t(
                    "Como administrador, puedes guardar esta entrada para que el monitor la compare con publicaciones actuales y futuras.",
                  )}
                </p>
                <button
                  className="button paper"
                  type="button"
                  onClick={() => void saveProductForMonitoring()}
                  disabled={!productValue.trim() || productBusy}
                >
                  {t(productBusy ? "Guardando…" : "Guardar para seguimiento")}
                </button>
              </div>
            )}
            {admin && trackedProducts.length > 0 && (
              <label className="tracked-product-select">
                {t("Productos en seguimiento")}
                <select
                  value={trackedProduct?.id || ""}
                  onChange={(event) => {
                    const selected = trackedProducts.find(
                      (item) => String(item.id) === event.target.value,
                    );
                    setTrackedProduct(selected || null);
                    setProductAlerts([]);
                    if (selected)
                      void loadProductAlerts(selected.id).catch((e) =>
                        setError((e as Error).message),
                      );
                  }}
                >
                  <option value="">{t("Selecciona un producto guardado")}</option>
                  {trackedProducts.map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
              </label>
            )}
            {trackedProduct && (
              <section className="tracked-product">
                <div className="section-rule">
                  <h2>{t("Seguimiento activo")}: {trackedProduct.name}</h2>
                  <button
                    className="text-button"
                    onClick={() => void loadProductAlerts(trackedProduct.id).catch((e) => setError((e as Error).message))}
                  >
                    {t("Actualizar coincidencias")}
                  </button>
                </div>
                <p className="product-search-hint">
                  {t(
                    "Las propuestas se generan al procesar publicaciones y requieren revisión humana; no son decisiones de aplicabilidad.",
                  )}
                </p>
                {productAlerts.length === 0 ? (
                  <p className="empty-edition">
                    {t("Aún no hay propuestas de coincidencia para este producto.")}
                  </p>
                ) : (
                  productAlerts.map((alert: Row) => (
                    <article className="product-match" key={alert.id}>
                      <button
                        className="headline-link"
                        onClick={() => void open(alert.publication_id)}
                      >
                        {alert.publication_title}
                      </button>
                      <p className="article-excerpt">{alert.reason}</p>
                      <div className="article-meta">
                        <span>{t(alert.status)}</span>
                        <span>{t(alert.decision)}</span>
                      </div>
                    </article>
                  ))
                )}
              </section>
            )}
            {productSearch && (
              <section className="product-search-results" aria-live="polite">
                <div className="section-rule">
                  <h2>{t("Coincidencias para revisar")}</h2>
                  <span>{t("{count} resultados", { count: productSearch.total })}</span>
                </div>
                <p className="product-search-hint">
                  {t("Se revisaron {count} documentos de NOM vigentes y publicaciones SIDOF.", {
                    count: productSearch.searched_publications,
                  })}
                </p>
                <p className="product-search-hint">
                  {t("Catálogo PLATIICA: {current} NOM vigentes entre {records} fichas guardadas.", {
                    current: productSearch.catalog.current_norms,
                    records: productSearch.catalog.records,
                  })}
                </p>
                <p className="product-search-hint">
                  {t("Completar la cola del sitemap no demuestra que PLATIICA publique todas las fichas en esos sitemaps.")}
                </p>
                {!productSearch.catalog.synchronized && (
                  <p className="product-search-hint">
                    {t("La última revisión del sitemap no terminó correctamente o la actualización automática está desactivada.")}
                    {productSearch.catalog.pending_pages > 0 &&
                      ` ${t("{count} fichas pendientes de revisar.", {
                        count: productSearch.catalog.pending_pages,
                      })}`}
                  </p>
                )}
                {(productSearch.catalog.unresolved_status > 0 ||
                  productSearch.catalog.missing_product_scope > 0) && (
                  <p className="product-search-hint">
                    {t("Hay fichas con estado o producto/servicio incompleto; no se incluyen como NOM vigentes.")}
                  </p>
                )}
                <p className="product-search-disclaimer">{t(productSearch.disclaimer)}</p>
                {productSearch.results.length === 0 ? (
                  <div className="empty-edition">
                    <h2>{t("No encontramos coincidencias en las publicaciones guardadas.")}</h2>
                    <p>
                      {t(
                        "Esto no confirma que no existan NOM aplicables: el archivo puede estar incompleto o la publicación puede no mencionar esos términos.",
                      )}
                    </p>
                  </div>
                ) : (
                  <div className="product-match-list">
                    {productSearch.results.map((result: Row) => {
                      const publication = result.publication;
                      const match = result.match;
                      return (
                        <article className="product-match" key={publication.id}>
                          <div className="article-kicker">
                            <span>{t(publication.source_name)}</span>
                            <span>{t(types[publication.kind] || "Publicación")}</span>
                            <b className="change-flag">
                              {t(
                                match.type === "fraccion_exacta"
                                  ? "Coincidencia de fracción"
                                  : match.type === "fraccion_base"
                                    ? "Coincidencia de fracción base"
                                    : "Coincidencia por descripción",
                              )}
                            </b>
                          </div>
                          <button
                            className="headline-link"
                            onClick={() => void open(publication.id)}
                          >
                            {publication.title}
                          </button>
                          <p className="article-excerpt" lang="es">{match.evidence}</p>
                          {match.matched_terms.length > 0 && (
                            <p className="matched-terms">
                              {t("Términos encontrados")}: {match.matched_terms.join(", ")}
                            </p>
                          )}
                          <div className="article-meta">
                            {publication.norm_status && (
                              <span>{t("Estado oficial")}: {publication.norm_status}</span>
                            )}
                            <span>
                              {publication.published_on
                                ? format(publication.published_on)
                                : t("Sin fecha oficial confirmada")}
                            </span>
                            <span>{publication.official_id}</span>
                          </div>
                          {publication.product_scope && (
                            <p className="matched-terms">
                              {t("Producto/servicio en PLATIICA")}: {publication.product_scope}
                            </p>
                          )}
                        </article>
                      );
                    })}
                  </div>
                )}
                {productSearch.truncated && (
                  <p className="product-search-hint">
                    {t("Se muestran los primeros 30 resultados más relevantes.")}
                  </p>
                )}
              </section>
            )}
          </section>
        )}
        {view === "archivo" && (
          <section className="section-intro">
            <span className="eyebrow">{t("LA HEMEROTECA")}</span>
            <h1>
              {t("Explorar publicaciones")}
              <span className="accent">.</span>
            </h1>
            <p>
              {t(
                "Busca por título, norma o palabras del documento. Cada publicación conserva su fuente y sus versiones.",
              )}
            </p>
          </section>
        )}
        {view === "historico" && (
          <section className="section-intro">
            <span className="eyebrow">{t("INVENTARIO PLATIICA")}</span>
            <h1>
              {t("Catálogo histórico de NOM")}
              <span className="accent">.</span>
            </h1>
            <p>
              {t(
                "Consulta las fichas NOM guardadas desde PLATIICA, vigentes y no vigentes. La lista incluye solo registros ya importados; revisa el estado de sincronización antes de considerarla completa.",
              )}
            </p>
          </section>
        )}
        {(view === "actualidad" || view === "archivo" || view === "historico") && (
          <>
            <form className="search-bar" onSubmit={(e) => e.preventDefault()}>
              <Icon name="search" size={21} />
              <input
                aria-label={t("Buscar publicaciones")}
                placeholder={t("Busca una NOM, un tema o una palabra…")}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(1);
                }}
              />
              {query && (
                <button
                  className="icon-button"
                  type="button"
                  aria-label={t("Limpiar búsqueda")}
                  onClick={() => {
                    setQuery("");
                    setPage(1);
                  }}
                >
                  <Icon name="close" />
                </button>
              )}
              <span>{t("ARCHIVO OFICIAL")}</span>
            </form>
            <div
              className={`source-wire ${view === "historico" ? "catalog-wire" : ""}`}
              aria-label={t("Filtrar por fuente")}
            >
              <button
                className={!source ? "active" : ""}
                onClick={() => {
                  setSource("");
                  setPage(1);
                }}
              >
                {t("Todas las fuentes")}
              </button>
              {sources
                .filter(
                  (s) =>
                    s.active &&
                    s.kind === (view === "historico" ? "platiica_catalog" : "sidof"),
                )
                .map((s) => (
                  <button
                    key={s.id}
                    className={source === String(s.id) ? "active" : ""}
                    onClick={() => {
                      setSource(String(s.id));
                      setPage(1);
                    }}
                  >
                    <i
                      className={`status-dot ${s.last_error ? "issue" : s.last_success_at ? "good" : ""}`}
                    />
                    {s.kind === "platiica_catalog" ? "PLATIICA" : s.kind.toUpperCase()}
                    {s.kind === "sidof"
                      ? ` · ${t(dailySource(s) ? "diario" : "referencia")}`
                      : ""}
                  </button>
                ))}
            </div>
            {language === "en" && (
              <p className="language-note">
                {t(
                  "La interfaz está en inglés. Los títulos y documentos oficiales se muestran en el español de la fuente.",
                )}
              </p>
            )}
            <div className="reading-layout">
              <section className="news-column" aria-busy={busy}>
                <div className="section-rule">
                  <h2>
                    {t(
                      view === "actualidad"
                        ? filtered
                          ? "Tu selección"
                          : "En portada"
                        : view === "historico"
                          ? "Fichas del catálogo"
                          : "El archivo",
                    )}
                  </h2>
                  <span>
                    {busy
                      ? t("Cargando…")
                      : t(
                          total === 1
                            ? "{count} publicación"
                            : "{count} publicaciones",
                          { count: total },
                        )}
                  </span>
                </div>
                <div className="filter-line">
                  <label>
                    {t("Fecha oficial")}
                    <select
                      aria-label={t("Periodo de publicación")}
                      value={period}
                      onChange={(e) => {
                        setPeriod(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="all">{t("Todas las fechas")}</option>
                      <option value="7">{t("Últimos 7 días")}</option>
                      <option value="30">{t("Últimos 30 días")}</option>
                    </select>
                  </label>
                  <label>
                    {t("Tipo")}
                    <select
                      aria-label={t("Tipo de publicación")}
                      value={kind}
                      onChange={(e) => {
                        setKind(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="">{t("Todos los tipos")}</option>
                      {Object.entries(types).map(([value, name]) => (
                        <option key={value} value={value}>
                          {t(name)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="check-filter">
                    <input
                      type="checkbox"
                      checked={changes}
                      onChange={(e) => {
                        setChanges(e.target.checked);
                        setPage(1);
                      }}
                    />
                    {t("Con cambios")}
                  </label>
                  {filtered && (
                    <button className="text-button" onClick={reset}>
                      {t("Quitar filtros")}
                    </button>
                  )}
                </div>
                {!busy && publications.length === 0 ? (
                  <div className="empty-edition">
                    <span className="empty-number">Nº 00</span>
                    <h2>
                      {t(
                        filtered
                          ? "Ninguna publicación coincide."
                          : view === "historico"
                            ? "Aún no hay fichas NOM guardadas."
                            : allFailed
                              ? "Aún no hay documentos recuperados."
                              : "Tu primera edición comienza aquí.",
                      )}
                    </h2>
                    <p>
                      {t(
                        filtered
                          ? "Prueba con otro tema o amplía el periodo. Las publicaciones sin fecha oficial no aparecen al filtrar por últimos días."
                          : view === "historico"
                            ? "La carga inicial se procesa por lotes. Abre Estado de fuentes para revisar el avance o los errores de PLATIICA."
                            : allFailed
                              ? "Las consultas a los sitios oficiales fallaron. Abre Estado de las fuentes para ver las direcciones y el motivo; puedes visitar cada sitio directamente."
                              : "Consulta las fuentes para empezar a reunir publicaciones oficiales. Aquí aparecerán sus títulos, fechas y cambios, sin datos de ejemplo.",
                      )}
                    </p>
                    <button
                      className="button paper"
                      onClick={
                        filtered
                          ? reset
                          : view === "historico"
                            ? () => navigate("fuentes")
                            : allFailed
                              ? () => navigate("fuentes")
                              : () => void refresh()
                      }
                      disabled={
                        view !== "historico" &&
                        !allFailed &&
                        !filtered &&
                        (!ready || updating || activeJobs)
                      }
                    >
                      {t(
                        filtered
                          ? "Ver todas las publicaciones"
                          : view === "historico"
                            ? "Ver estado de PLATIICA"
                            : allFailed
                              ? "Revisar las conexiones"
                              : "Consultar fuentes",
                      )}
                      <Icon name="arrow" />
                    </button>
                    <div className="empty-stamp" aria-hidden="true">
                      NOM
                      <br />
                      <span>{t("MÉXICO")}</span>
                    </div>
                  </div>
                ) : (
                  <>
                    {view === "actualidad" && page === 1 && lead && (
                      <article className="lead-story">
                        <div className="article-kicker">
                          <span className="lead-label">
                            {t("PRIMERA LECTURA")}
                          </span>
                          <span>{t(lead.source_name)}</span>
                          {lead.has_changes && (
                            <b className="change-flag">
                              {t("Cambio detectado")}
                            </b>
                          )}
                          {lead.is_demo && (
                            <b className="demo-flag">
                              {t("Muestra sintética")}
                            </b>
                          )}
                        </div>
                        <button
                          className="lead-headline"
                          lang="es"
                          onClick={() => void open(lead.id)}
                        >
                          {lead.title}
                        </button>
                        {lead.excerpt && (
                          <p className="lead-excerpt" lang="es">
                            {lead.excerpt}
                          </p>
                        )}
                        <div className="lead-bottom">
                          <div className="article-meta">
                            <span>
                              {lead.published_on
                                ? t("Publicado {date}", {
                                    date: format(lead.published_on),
                                  })
                                : t("Fecha oficial por confirmar")}
                            </span>
                            <span>{t(types[lead.kind] || "Publicación")}</span>
                          </div>
                          <button
                            className="text-button read-link"
                            onClick={() => void open(lead.id)}
                          >
                            {t("Abrir documento")}
                            <Icon name="arrow" />
                          </button>
                        </div>
                      </article>
                    )}
                    {(view === "actualidad" && page === 1
                      ? publications.slice(1)
                      : publications
                    ).map((item) => (
                      <PublicationRow
                        key={item.id}
                        item={item}
                        open={(id) => void open(id)}
                      />
                    ))}
                  </>
                )}
                {total > 15 && (
                  <div className="pagination">
                    <button
                      className="button paper"
                      disabled={page === 1}
                      onClick={() => setPage(page - 1)}
                    >
                      {t("Anterior")}
                    </button>
                    <span>
                      {t("Página {page} de {total}", {
                        page,
                        total: Math.ceil(total / 15),
                      })}
                    </span>
                    <button
                      className="button paper"
                      disabled={page * 15 >= total}
                      onClick={() => setPage(page + 1)}
                    >
                      {t("Siguiente")}
                    </button>
                  </div>
                )}
                <p className="archive-note">
                  {t(
                    "Orden por fecha de publicación. Cuando la fecha oficial falta, se indica expresamente. Una detección de hoy puede corresponder a un documento anterior.",
                  )}
                </p>
              </section>
            </div>
          </>
        )}
        {view === "fuentes" && (
          <>
            <section className="section-intro">
              <span className="eyebrow">
                {t("DE DÓNDE VIENE LA INFORMACIÓN")}
              </span>
              <h1>
                {t("Estado de fuentes")}
                <span className="accent">.</span>
              </h1>
              <p>
                {t(
                  "El boletín sigue las páginas configuradas en estas fuentes. Aquí puedes ver cuándo se consultaron y si una revisión quedó incompleta.",
                )}
              </p>
            </section>
            <div className="monitor-caption">
              <i
                className={`status-dot ${dashboard.monitor_enabled && dashboard.scheduler_enabled ? "good" : ""}`}
              />
              <span>
                {t(
                  dashboard.monitor_enabled && dashboard.scheduler_enabled
                    ? "Consulta automática activa mientras el servidor esté encendido."
                    : "La consulta automática está desactivada en esta ejecución.",
                )}
              </span>
              <span>{t("La frecuencia se indica por fuente.")}</span>
            </div>
            <section className="source-directory">
              {sources.map((item, index) => (
                <article key={item.id} className="directory-entry">
                  <span className="directory-number">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div className="directory-copy">
                    <div className="article-kicker">
                      <span>{item.kind === "platiica_catalog" ? "PLATIICA" : item.kind.toUpperCase()}</span>
                      <span className={item.last_error ? "issue-text" : ""}>
                        {t(
                          item.last_error
                            ? "Revisión parcial del periodo"
                            : item.latest_check_status === "queued"
                              ? "Consulta en cola"
                              : item.latest_check_status === "running"
                                ? item.latest_check_heartbeat_at &&
                                  Date.now() - Date.parse(item.latest_check_heartbeat_at) > 120_000
                                  ? "Proceso sin señal reciente"
                                  : "Consulta en curso"
                            : item.last_success_at
                              ? "Última revisión completa"
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
                        <strong>{t("Fechas pendientes de verificar")}</strong>
                        <p>
                          {item.pending_dates
                            .map((day: string) => format(day))
                            .join(" · ")}
                        </p>
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
                            total > 0
                              ? "Hay publicaciones guardadas. La última revisión quedó incompleta."
                              : sourceIssue(item.last_error),
                          )}
                        </p>
                        <details className="source-problem">
                          <summary>{t("Detalle original del error")}</summary>
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
                        ? t(" · {count} errores", { count: job.error_count })
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
        <Reader title={detail.title} close={closeReader}>
          <div className="reader-body">
            <div className="article-kicker">
              <span>{t(detail.source_name)}</span>
              <span>{t(types[detail.kind] || "Publicación")}</span>
              {detail.is_demo && (
                <b className="demo-flag">{t("Muestra sintética")}</b>
              )}
            </div>
            <h1 lang="es">{detail.title}</h1>
            <p className="original-language">{t("Texto oficial en español")}</p>
            <div className="reader-dates">
              <span>
                {t("PUBLICACIÓN OFICIAL")}
                <strong>
                  {detail.published_on
                    ? format(detail.published_on)
                    : t("Sin fecha confirmada")}
                </strong>
              </span>
              <span>
                {t("DETECTADO EN EL BOLETÍN")}
                <strong>{format(detail.detected_at, true)}</strong>
              </span>
            </div>
            {link(detail.url) && (
              <a
                className="button ink source-original"
                href={link(detail.url)}
                target="_blank"
                rel="noreferrer"
              >
                {t("Abrir en la fuente oficial")}
                <Icon name="external" />
              </a>
            )}
            {detail.processing_note && (
              <details className="notification">
                <summary>{t("Nota original del documento")}</summary>
                <p lang="es">{detail.processing_note}</p>
              </details>
            )}
            <div className="section-rule">
              <h2>{t("Documento conservado")}</h2>
              <span>
                {t(
                  detail.versions.length === 1
                    ? "{count} versión"
                    : "{count} versiones",
                  { count: detail.versions.length },
                )}
              </span>
            </div>
            {detail.versions.length > 1 && (
              <div className="version-tabs">
                {detail.versions.map((v: Row) => (
                  <button
                    key={v.id}
                    className={selected?.id === v.id ? "selected" : ""}
                    onClick={() => setVersionId(v.id)}
                  >
                    {t("Versión {number}", { number: v.sequence })}
                    <small>{format(v.captured_at)}</small>
                  </button>
                ))}
              </div>
            )}
            {selected ? (
              <>
                <p className="capture-caption">
                  {t(
                    "Copia consultada el {date}. El texto se presenta tal como fue extraído de la fuente.",
                    { date: format(selected.captured_at, true) },
                  )}
                </p>
                <div className="document-text" lang="es">
                  {selected.content ||
                    t(
                      "La fuente no ofreció texto extraíble. Abre el documento oficial o descarga la copia.",
                    )}
                </div>
                {selected.evidence_key && (
                  <button
                    className="button paper"
                    onClick={() => void download(selected)}
                  >
                    <Icon name="download" />
                    {t("Descargar copia consultada")}
                  </button>
                )}
              </>
            ) : (
              <p className="capture-caption">
                {t("Todavía no hay una copia del documento disponible.")}
              </p>
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
            {(inspection.index_checks || []).length === 0 && (
              <p>
                {t("Todavía no hay un día completo registrado en este lote.")}
              </p>
            )}
            {(inspection.index_checks || []).map(
              (check: Row, index: number) => (
                <section className="daily-check" key={`${check.day}-${index}`}>
                  <h2>{format(check.day)}</h2>
                  <p>
                    {t(
                      "{notes} notas revisadas · {selected} publicaciones seleccionadas",
                      {
                        notes: check.notes_checked,
                        selected: check.selected_ids.length,
                      },
                    )}
                  </p>
                  {check.declared_no_publication && (
                    <p>
                      {t(
                        "SIDOF declaró esta fecha sin publicación; no equivale a una garantía de cobertura integral.",
                      )}
                    </p>
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
                <strong>{t("Detalle original del error")}</strong>
                <p lang="es">{inspection.error}</p>
              </div>
            )}
          </div>
        </Reader>
      )}
    </div>
  );
}
