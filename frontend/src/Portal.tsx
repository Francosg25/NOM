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
type View = "actualidad" | "archivo" | "fuentes" | "guia";
const views: { id: View; name: string }[] = [
  { id: "actualidad", name: "Novedades" },
  { id: "archivo", name: "Buscar publicaciones" },
  { id: "fuentes", name: "Estado de las fuentes" },
  { id: "guia", name: "Cómo funciona" },
];
const types: Record<string, string> = {
  proyecto: "Proyecto de norma",
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
function sourceIssue(error: string) {
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
        <span className="eyebrow">{t("LA GUÍA / NOM MONITOR")}</span>
        <h1>
          {t("De la publicación a la lectura")}
          <span className="accent">.</span>
        </h1>
        <p>
          {t(
            "El portal revisa páginas oficiales configuradas, guarda lo que encuentra y te permite leerlo después. Así se usa.",
          )}
        </p>
      </div>
      <ol className="guide-steps">
        {[
          [
            "01",
            "Consulta las fuentes",
            "Pulsa Consultar fuentes. El servidor revisa las páginas registradas y guarda una copia de los documentos que puede recuperar. Con el monitor activo, repite la revisión según la frecuencia de cada fuente.",
          ],
          [
            "02",
            "Lee las publicaciones",
            "En Novedades aparecen las publicaciones recuperadas. Busca una NOM o una palabra, filtra por fuente o fecha y abre un título para leer el documento.",
          ],
          [
            "03",
            "Comprueba el original",
            "Dentro de cada publicación puedes abrir el sitio oficial, descargar la copia consultada y ver las versiones guardadas. Usa el documento oficial para verificar cualquier obligación.",
          ],
        ].map(([number, title, text]) => (
          <li key={number}>
            <span>{number}</span>
            <div>
              <h2>{t(title)}</h2>
              <p>{t(text)}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="guide-columns">
        <section>
          <span className="eyebrow">{t("CÓMO LEER EL RESULTADO")}</span>
          <h2>{t("Cada estado tiene un significado.")}</h2>
          <dl className="guide-legend">
            <div>
              <dt>{t("Primera copia")}</dt>
              <dd>
                {t(
                  "Se guardó el documento por primera vez. Puede ser una publicación antigua encontrada hoy.",
                )}
              </dd>
            </div>
            <div>
              <dt>{t("Cambio detectado")}</dt>
              <dd>
                {t(
                  "El contenido guardado cambió respecto a una copia anterior. No confirma por sí solo una modificación legal ni que aplique a tu producto.",
                )}
              </dd>
            </div>
            <div>
              <dt>{t("Consulta correcta")}</dt>
              <dd>
                {t(
                  "La consulta terminó correctamente dentro de la cobertura configurada. No garantiza que se hayan encontrado todas las NOM.",
                )}
              </dd>
            </div>
            <div>
              <dt>{t("Consulta incompleta")}</dt>
              <dd>
                {t(
                  "La fuente no pudo revisarse por completo. No significa que no existan novedades; se conserva la última copia válida.",
                )}
              </dd>
            </div>
          </dl>
        </section>
        <section className="guide-scope">
          <span className="eyebrow">{t("QUÉ ESTÁS VIGILANDO")}</span>
          <h2>{t("La cobertura depende de las páginas.")}</h2>
          <p>
            {t(
              "DOF sigue su índice diario. PLATIICA y SNICE siguen las fichas o páginas que se configuren. SIDOF permite seguir un documento conocido. La cobertura diaria de DOF aún requiere validación.",
            )}
          </p>
          <p>
            {t(
              "Guardar un tema solo crea un acceso rápido a la búsqueda del archivo. El portal todavía no determina automáticamente qué norma aplica a cada producto JE ni envía avisos por correo.",
            )}
          </p>
          <p>
            {t(
              "Español / English cambia todos los controles y la guía. Los documentos oficiales se conservan en el español original; no hay una traducción automática del texto legal.",
            )}
          </p>
          <button className="text-button" onClick={() => go("fuentes")}>
            {t("Ver qué páginas se consultan")}
            <Icon name="arrow" />
          </button>
        </section>
      </div>
      <div className="guide-example">
        <span className="eyebrow">{t("UN EJEMPLO DE USO")}</span>
        <p>
          {t(
            "Si quieres revisar una norma: consulta las fuentes, busca su identificador —por ejemplo, NOM-014-ENER— y abre los resultados. Si la búsqueda está vacía, revisa el estado y las páginas de las fuentes antes de concluir que no hay publicaciones.",
          )}
        </p>
        <button className="button ink" onClick={() => go("archivo")}>
          {t("Ir a buscar publicaciones")}
          <Icon name="arrow" />
        </button>
      </div>
    </section>
  );
}
function Icon({ name, size = 18 }: { name: string; size?: number }) {
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
function Reader({
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
          <span>{item.source_name}</span>
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
        </div>
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
  const [versionId, setVersionId] = useState<number | null>(null);
  const [term, setTerm] = useState("");
  const [terms, setTerms] = useState<string[]>(() => {
    try {
      const v = JSON.parse(localStorage.getItem("nom-radar") || "[]");
      return Array.isArray(v)
        ? v.filter((x) => typeof x === "string").slice(0, 12)
        : [];
    } catch {
      return [];
    }
  });
  const generation = useRef(0);
  const sources: Row[] = dashboard.sources || [];
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
        setJobs(runs.items);
        setError("");
      } catch (e) {
        if (id === generation.current) setError((e as Error).message);
      } finally {
        if (id === generation.current) setBusy(false);
      }
    },
    [ready, request, page, query, source, kind, period, changes, demo],
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
      if (views.some((v) => v.id === next)) setView(next as View);
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
            ? "Las fuentes se consultaron hace menos de 15 minutos. Puedes ver el resultado en Estado de las fuentes."
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
      a.download = `norma-${version.id}${version.media_type?.includes("pdf") ? ".pdf" : ".html"}`;
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
  const addTerm = (event: FormEvent) => {
    event.preventDefault();
    const value = term.trim();
    if (!value || terms.includes(value) || terms.length >= 12) return;
    const next = [...terms, value];
    setTerms(next);
    setTerm("");
    try {
      localStorage.setItem("nom-radar", JSON.stringify(next));
    } catch {
      /* Session still works without storage. */
    }
  };
  const removeTerm = (value: string) => {
    const next = terms.filter((x) => x !== value);
    setTerms(next);
    try {
      localStorage.setItem("nom-radar", JSON.stringify(next));
    } catch {
      /* optional */
    }
  };
  const latest = sources
    .map((s) => s.last_success_at as string)
    .filter(Boolean)
    .sort()
    .at(-1);
  const activeSources = sources.filter((s) => s.active);
  const failedSources = activeSources.filter((s) => s.last_error);
  const allFailed =
    activeSources.length > 0 && failedSources.length === activeSources.length;
  const sourceName = (s?: Row) =>
    s?.kind === "sidof"
      ? t("SIDOF · documento de referencia")
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
        <div className="masthead-note">
          <span>
            {t("Lo que se publica.")}
            <br />
            {t("Lo que cambia.")}
          </span>
          <small>{t("NOM Monitor / México")}</small>
        </div>
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
            <span>{t(error)}</span>
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
                    ? "No se pudieron consultar las fuentes."
                    : "La revisión tiene fuentes pendientes.",
                )}
              </strong>
              <p>
                {t(
                  "{failed} de {total} fuentes activas tienen una revisión incompleta. No se ha confirmado la ausencia de novedades.",
                  { failed: failedSources.length, total: activeSources.length },
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
                {t("Normativa mexicana,")}
                <br />
                <em>{t("a primera vista.")}</em>
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
                    : allFailed
                      ? t("La revisión necesita atención")
                      : latest
                        ? t("Última consulta correcta: {date}", {
                            date: format(latest, true),
                          })
                        : t("La primera consulta está pendiente")}
                </span>
              </div>
            </div>
          </section>
        )}
        {view === "actualidad" && (
          <section className="start-here" aria-label={t("Cómo empezar")}>
            <span>{t("EMPIEZA AQUÍ")}</span>
            <button
              onClick={() => void refresh()}
              disabled={!ready || updating || activeJobs}
            >
              <b>01</b>
              {t("Consulta las fuentes")}
              <Icon name="arrow" size={15} />
            </button>
            <button onClick={() => navigate("archivo")}>
              <b>02</b>
              {t("Busca una publicación")}
              <Icon name="arrow" size={15} />
            </button>
            <button onClick={() => navigate("guia")}>
              <b>03</b>
              {t("Entiende los resultados")}
              <Icon name="arrow" size={15} />
            </button>
          </section>
        )}
        {view === "guia" && <Guide go={navigate} />}
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
        {(view === "actualidad" || view === "archivo") && (
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
            <div className="source-wire" aria-label={t("Filtrar por fuente")}>
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
                .filter((s) => s.active)
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
                    {s.kind.toUpperCase()}
                    {s.kind === "sidof" ? ` · ${t("referencia")}` : ""}
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
                          : allFailed
                            ? "Aún no hay documentos recuperados."
                            : "Tu primera edición comienza aquí.",
                      )}
                    </h2>
                    <p>
                      {t(
                        filtered
                          ? "Prueba con otro tema o amplía el periodo. Las publicaciones sin fecha oficial no aparecen al filtrar por últimos días."
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
                          : allFailed
                            ? () => navigate("fuentes")
                            : () => void refresh()
                      }
                      disabled={
                        !allFailed &&
                        !filtered &&
                        (!ready || updating || activeJobs)
                      }
                    >
                      {t(
                        filtered
                          ? "Ver todas las publicaciones"
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
                          <span>{lead.source_name}</span>
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
              <aside className="margin-column">
                <section className="radar">
                  <span className="margin-number">{t("01 / TU RADAR")}</span>
                  <h2>
                    {t("Los temas")}
                    <br />
                    <em>{t("que te importan.")}</em>
                  </h2>
                  <p>
                    {t("Guarda palabras para volver a buscarlas con un clic.")}
                  </p>
                  <form onSubmit={addTerm}>
                    <input
                      aria-label={t("Nuevo tema de seguimiento")}
                      placeholder={t("Añade un tema…")}
                      value={term}
                      maxLength={60}
                      onChange={(e) => setTerm(e.target.value)}
                    />
                    <button
                      className="icon-button"
                      aria-label={t("Guardar tema")}
                      disabled={!term.trim() || terms.length >= 12}
                    >
                      <Icon name="plus" />
                    </button>
                  </form>
                  <div className="saved-topics">
                    {terms.map((value) => (
                      <div key={value}>
                        <button
                          onClick={() => {
                            setQuery(value);
                            setPage(1);
                          }}
                        >
                          {value}
                          <Icon name="arrow" size={14} />
                        </button>
                        <button
                          className="remove-topic"
                          aria-label={t("Quitar tema {topic}", {
                            topic: value,
                          })}
                          onClick={() => removeTerm(value)}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                  {!terms.length && (
                    <small>{t("Tu lista se guarda en este navegador.")}</small>
                  )}
                  <small className="radar-explanation">
                    {t(
                      "Busca en los documentos ya recuperados. No activa notificaciones.",
                    )}
                  </small>
                </section>
                <section className="sources-at-close">
                  <span className="margin-number">{t("02 / AL CIERRE")}</span>
                  <h2>
                    {t("Las fuentes,")}
                    <br />
                    <em>{t("a la vista.")}</em>
                  </h2>
                  {sources.map((s) => (
                    <button
                      key={s.id}
                      className="source-status"
                      onClick={() => navigate("fuentes")}
                    >
                      <span>
                        <i
                          className={`status-dot ${s.last_error ? "issue" : s.last_success_at ? "good" : ""}`}
                        />
                        <strong>{s.kind.toUpperCase()}</strong>
                      </span>
                      <span>
                        {t(
                          s.last_error
                            ? "Requiere atención"
                            : s.last_success_at
                              ? "Consulta correcta"
                              : "Sin consultar",
                        )}
                        <small>
                          {s.last_success_at
                            ? format(s.last_success_at, true)
                            : t("Primera revisión pendiente")}
                        </small>
                      </span>
                    </button>
                  ))}
                  <button
                    className="text-button"
                    onClick={() => navigate("fuentes")}
                  >
                    {t("Ver cobertura y consultas")}
                    <Icon name="arrow" size={16} />
                  </button>
                </section>
                {dashboard.upcoming?.length > 0 && (
                  <section className="datebook">
                    <span className="margin-number">
                      {t("03 / EN EL CALENDARIO")}
                    </span>
                    <h2>{t("Próximas fechas.")}</h2>
                    {dashboard.upcoming.map((item: Row) => (
                      <button key={item.id} onClick={() => void open(item.id)}>
                        <span>{format(item.effective_on)}</span>
                        <strong>{item.title}</strong>
                      </button>
                    ))}
                  </section>
                )}
              </aside>
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
                {t("¿Se pudo revisar?")}
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
                      <span>{item.kind.toUpperCase()}</span>
                      <span className={item.last_error ? "issue-text" : ""}>
                        {t(
                          item.last_error
                            ? "Consulta incompleta"
                            : item.last_success_at
                              ? "Última consulta correcta"
                              : "Pendiente de consultar",
                        )}
                      </span>
                    </div>
                    <h2>{sourceName(item)}</h2>
                    <p>
                      {language === "en"
                        ? t(`coverage.${item.kind}`)
                        : item.coverage}
                    </p>
                    {language === "en" && (
                      <details className="source-notes">
                        <summary>{t("Notas originales de la fuente")}</summary>
                        <p lang="es">{item.coverage}</p>
                      </details>
                    )}
                    {item.urls.map((url: string) => (
                      <a
                        key={url}
                        className="source-url"
                        href={link(url)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {displayUrl(url)}
                        <Icon name="external" size={14} />
                      </a>
                    ))}
                    {item.last_error && (
                      <div className="source-failure">
                        <p>{t(sourceIssue(item.last_error))}</p>
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
                      <dt>{t("Última consulta correcta")}</dt>
                      <dd>{format(item.last_success_at, true)}</dd>
                    </div>
                    <div>
                      <dt>{t("Frecuencia")}</dt>
                      <dd>
                        {item.schedule_enabled
                          ? t("Cada {hours} h", { hours: item.frequency_hours })
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
          <span>DOF / SIDOF · PLATIICA · SNICE</span>
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
              <span>{detail.source_name}</span>
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
    </div>
  );
}
