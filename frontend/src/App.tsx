import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

type Row = Record<string, any>;
type Page =
  | "Inicio"
  | "Publicaciones"
  | "Alertas"
  | "Productos"
  | "Fuentes y ejecuciones";
const pages: Page[] = [
  "Inicio",
  "Publicaciones",
  "Alertas",
  "Productos",
  "Fuentes y ejecuciones",
];
const labels: Record<string, string> = {
  pendiente: "Pendiente",
  en_revision: "En revisión",
  resuelta: "Resuelta",
  propuesta: "Posible impacto",
  confirmada: "Aplicabilidad confirmada",
  descartada: "Relación descartada",
  clasificacion_pendiente: "Clasificación pendiente",
  proyecto: "Proyecto",
  definitiva: "Norma definitiva",
  norma_definitiva: "Norma definitiva",
  modificacion: "Modificación",
  cancelacion: "Cancelación",
  acuerdo: "Acuerdo",
  aviso: "Aviso",
  queued: "En cola",
  running: "En ejecución",
  completed: "Completada",
  succeeded: "Completada",
  failed: "Con errores",
  partial: "Parcial",
  interrupted: "Interrumpida",
  consulta: "Consulta",
  revisor: "Revisor",
  administrador: "Administrador",
  familia: "Familia",
  subfamilia: "Subfamilia",
  producto: "Producto",
  official: "Oficial",
  demo: "Demostración",
};
const text = (value: any) =>
  value == null || value === "" ? "—" : String(value);
const label = (value: any) => labels[String(value)] || text(value);
const fmt = (value: any, dateOnly = false) => {
  if (!value) return "Sin información";
  try {
    return new Intl.DateTimeFormat("es-MX", {
      timeZone: dateOnly ? "UTC" : "America/Mexico_City",
      dateStyle: "medium",
      ...(dateOnly ? {} : { timeStyle: "short" }),
    }).format(
      new Date(
        dateOnly
          ? `${String(value).slice(0, 10)}T12:00:00Z`
          : /Z$|[+-]\d\d:\d\d$/.test(value)
            ? value
            : `${value}Z`,
      ),
    );
  } catch {
    return "Fecha no disponible";
  }
};
const array = (data: any): Row[] =>
  Array.isArray(data) ? data : data?.items || [];
const split = (value: FormDataEntryValue | null) =>
  String(value || "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    Inicio: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    Publicaciones: (
      <>
        <path d="M7 3h9l4 4v14H4V3z" />
        <path d="M15 3v5h5M8 12h8M8 16h8" />
      </>
    ),
    Alertas: (
      <>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
      </>
    ),
    Productos: (
      <>
        <path d="m3 7 9-5 9 5v11l-9 5-9-5zM3 7l9 5 9-5M12 12v11M7 5l10 5" />
      </>
    ),
    "Fuentes y ejecuciones": (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3a18 18 0 0 1 0 18 18 18 0 0 1 0-18" />
      </>
    ),
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 5 5" />
      </>
    ),
    arrow: <path d="m9 5 7 7-7 7" />,
    plus: <path d="M12 5v14M5 12h14" />,
    check: <path d="m5 12 4 4L19 6" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    refresh: (
      <>
        <path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5" />
      </>
    ),
    external: (
      <>
        <path d="M14 3h7v7M21 3l-11 11M10 3H3v18h18v-7" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 6v6l4 2" />
      </>
    ),
    shield: (
      <>
        <path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6z" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
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
      {paths[name] || paths.Publicaciones}
    </svg>
  );
}
function Badge({ value, children }: { value?: any; children?: ReactNode }) {
  return (
    <span className={`badge ${String(value || "").toLowerCase()}`}>
      {children || label(value)}
    </span>
  );
}
function Empty({
  title = "Todavía no hay información",
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name="Publicaciones" size={28} />
      </span>
      <h3>{title}</h3>
      <p>
        {children ||
          "Los resultados aparecerán aquí cuando se registre la primera consulta."}
      </p>
    </div>
  );
}
function Modal({
  title,
  children,
  close,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  wide?: boolean;
}) {
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", fn);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", fn);
      document.body.style.overflow = previous;
    };
  }, [close]);
  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <section
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <h2>{title}</h2>
          <button className="icon-button" onClick={close} aria-label="Cerrar">
            <Icon name="close" />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
function Field({
  label: title,
  children,
  full = false,
}: {
  label: string;
  children: ReactNode;
  full?: boolean;
}) {
  return (
    <label className={`field ${full ? "full" : ""}`}>
      <span>{title}</span>
      {children}
    </label>
  );
}
function Pager({
  page,
  total,
  setPage,
  size = 20,
}: {
  page: number;
  total: number;
  setPage: (n: number) => void;
  size?: number;
}) {
  return (
    <div className="pager">
      <span>
        {total
          ? `${(page - 1) * size + 1}–${Math.min(page * size, total)} de ${total} registros`
          : "0 registros"}
      </span>
      <div>
        <button
          className="button secondary small"
          disabled={page <= 1}
          onClick={() => setPage(page - 1)}
        >
          Anterior
        </button>
        <span>Página {page}</span>
        <button
          className="button secondary small"
          disabled={page * size >= total}
          onClick={() => setPage(page + 1)}
        >
          Siguiente
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>(
    pages.find((p) => p === decodeURIComponent(location.hash.slice(1))) ||
      "Inicio",
  );
  const [me, setMe] = useState<Row | null>(null),
    [authError, setAuthError] = useState(""),
    [platformAuthChecked, setPlatformAuthChecked] = useState(false),
    [token, setToken] = useState(""),
    [tokenDraft, setTokenDraft] = useState(""),
    [role, setRole] = useState("administrador"),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [data, setData] = useState<Row>({}),
    [sources, setSources] = useState<Row[]>([]),
    [catalog, setCatalog] = useState<Row[]>([]),
    [jobs, setJobs] = useState<Row[]>([]),
    [busy, setBusy] = useState(false),
    [saving, setSaving] = useState(false);
  const [query, setQuery] = useState(""),
    [status, setStatus] = useState(""),
    [source, setSource] = useState(""),
    [kind, setKind] = useState(""),
    [origin, setOrigin] = useState("official"),
    [listPage, setListPage] = useState(1),
    [general, setGeneral] = useState(false);
  const [detail, setDetail] = useState<Row | null>(null),
    [modal, setModal] = useState<string | null>(null),
    [edit, setEdit] = useState<Row | null>(null),
    [jobDetail, setJobDetail] = useState<Row | null>(null);
  const dev = Boolean(
      me?.dev_auth_enabled ||
        me?.auth_mode === "development" ||
        me?.development_auth,
    ),
    canReview = ["revisor", "administrador"].includes(me?.role || ""),
    admin = me?.role === "administrador";
  const request = useCallback(
    async (path: string, method = "GET", body?: Row) => {
      const headers: Record<string, string> = {};
      if (body) headers["Content-Type"] = "application/json";
      if (token) headers.Authorization = `Bearer ${token}`;
      if (dev) headers["X-Dev-Role"] = role;
      const response = await fetch(`/api${path}`, {
        method,
        headers,
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      if (!response.ok) {
        let message = `${response.status}: No se pudo completar la solicitud`;
        try {
          const e = await response.json();
          message =
            typeof e.detail === "string"
              ? e.detail
              : Array.isArray(e.detail)
                ? e.detail
                    .map((v: Row) => `${v.loc?.slice(1).join(".")}: ${v.msg}`)
                    .join("; ")
                : message;
        } catch {
          /* Keep safe status text. */
        }
        throw new Error(message);
      }
      return response.status === 204 ? null : response.json();
    },
    [token, dev, role],
  );
  const loadMe = useCallback(async () => {
    try {
      const value = await request("/me");
      setMe(value);
      setAuthError("");
    } catch (e) {
      setAuthError((e as Error).message);
    }
  }, [request]);
  useEffect(() => {
    void loadMe();
  }, [loadMe]);
  useEffect(() => {
    if (!authError || token || platformAuthChecked) return;
    setPlatformAuthChecked(true);
    void fetch("/.auth/me")
      .then((r) => (r.ok ? r.json() : []))
      .then((entries) => {
        const aad =
          Array.isArray(entries) &&
          entries.find(
            (entry: Row) =>
              entry.provider_name === "aad" &&
              typeof entry.access_token === "string",
          );
        if (aad) setToken(aad.access_token);
      })
      .catch(() => {
        /* Token store is optional; backend remains the identity authority. */
      });
  }, [authError, token, platformAuthChecked]);
  useEffect(() => {
    const fn = () => {
      const found = pages.find(
        (p) => p === decodeURIComponent(location.hash.slice(1)),
      );
      if (found) setPage(found);
    };
    window.addEventListener("hashchange", fn);
    return () => window.removeEventListener("hashchange", fn);
  }, []);
  const load = useCallback(
    async (quiet = false) => {
      if (!me) return;
      if (!quiet) setBusy(true);
      setError("");
      try {
        const params = new URLSearchParams({
          page: String(listPage),
          page_size: "20",
          is_demo: String(origin === "demo"),
        });
        if (query) params.set("q", query);
        if (status) params.set("status", status);
        if (source) params.set("source_id", source);
        if (kind) params.set("kind", kind);
        if (page === "Alertas" && general) params.set("general", "true");
        const endpoint =
          page === "Inicio"
            ? "/dashboard"
            : page === "Publicaciones"
              ? `/publications?${params}`
              : page === "Alertas"
                ? `/alerts?${params}`
                : page === "Productos"
                  ? `/catalog?${params}`
                  : `/jobs?page=${listPage}&page_size=20`;
        const allPages = async (path: string) => {
          let combined: Row[] = [];
          for (let p = 1; ; p++) {
            const next = await request(`${path}?page=${p}&page_size=200`);
            combined = combined.concat(array(next));
            if (combined.length >= next.total || !array(next).length)
              return combined;
          }
        };
        const [main, src, cat] = await Promise.all([
          request(endpoint),
          allPages("/sources"),
          allPages("/catalog"),
        ]);
        setData(main || {});
        setSources(array(src));
        setCatalog(array(cat));
        if (page === "Fuentes y ejecuciones") setJobs(array(main));
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [me, request, page, query, status, source, kind, origin, listPage, general],
  );
  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), query ? 250 : 0);
    return () => clearTimeout(timeout);
  }, [load, query]);
  useEffect(() => {
    if (
      page !== "Fuentes y ejecuciones" ||
      !jobs.some((j) => ["queued", "running"].includes(j.status))
    )
      return;
    const id = window.setInterval(() => void load(true), 2500);
    return () => clearInterval(id);
  }, [jobs, page, load]);
  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(""), 6000);
    return () => clearTimeout(id);
  }, [notice]);
  const navigate = (next: Page) => {
    setPage(next);
    setData({});
    location.hash = encodeURIComponent(next);
    setQuery("");
    setStatus("");
    setSource("");
    setKind("");
    setGeneral(false);
    setListPage(1);
    setDetail(null);
  };
  const mutate = async (
    path: string,
    method: string,
    body: Row,
    success: string,
  ) => {
    setSaving(true);
    setError("");
    try {
      const result = await request(path, method, body);
      setNotice(success);
      await load(true);
      return result;
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  };
  const openPublication = async (id: number) => {
    setBusy(true);
    setError("");
    try {
      setDetail(await request(`/publications/${id}`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const download = async (version: Row) => {
    setError("");
    try {
      const headers: Record<string, string> = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      if (dev) headers["X-Dev-Role"] = role;
      const response = await fetch(`/api/versions/${version.id}/evidence`, {
        headers,
      });
      if (!response.ok) throw new Error("No se pudo recuperar la evidencia");
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `evidencia-${version.id}${version.media_type?.includes("pdf") ? ".pdf" : ".html"}`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const rows = array(data),
    total = data.total ?? rows.length;
  const sourceName = (id: any) =>
    sources.find((s) => s.id === id)?.name || text(id);
  const catalogName = (id: any) =>
    catalog.find((s) => s.id === id)?.name || "Relevancia por evaluar";
  const toolbar = (
    <div className="toolbar">
      <div className="search">
        <Icon name="search" size={18} />
        <input
          aria-label="Buscar"
          placeholder={
            page === "Productos"
              ? "Buscar producto, modelo, número de parte…"
              : "Buscar por título, identificador o contenido…"
          }
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setListPage(1);
          }}
        />
      </div>
      {page !== "Productos" && (
        <select
          aria-label="Filtrar por estado"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setListPage(1);
          }}
        >
          <option value="">Todos los estados</option>
          {["pendiente", "en_revision", "resuelta"].map((s) => (
            <option key={s} value={s}>
              {label(s)}
            </option>
          ))}
        </select>
      )}
      {page === "Publicaciones" && (
        <>
          <select
            aria-label="Filtrar fuente"
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              setListPage(1);
            }}
          >
            <option value="">Todas las fuentes</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Filtrar tipo"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setListPage(1);
            }}
          >
            <option value="">Todos los tipos</option>
            {[
              "proyecto",
              "norma_definitiva",
              "modificacion",
              "cancelacion",
              "acuerdo",
              "aviso",
              "clasificacion_pendiente",
            ].map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </>
      )}
      <select
        aria-label="Origen de los datos"
        value={origin}
        onChange={(e) => {
          setOrigin(e.target.value);
          setListPage(1);
        }}
      >
        <option value="official">Datos oficiales</option>
        <option value="demo">Demostración</option>
      </select>
    </div>
  );
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="#Inicio" onClick={() => navigate("Inicio")}>
          <span className="brand-symbol">JE</span>
          <div>
            JOHNSON ELECTRIC<small>NOM Monitor</small>
          </div>
        </a>
        <div className="nav-label">ESPACIO DE TRABAJO</div>
        <nav aria-label="Navegación principal">
          {pages.map((p) => (
            <button
              key={p}
              className={page === p ? "active" : ""}
              onClick={() => navigate(p)}
            >
              <Icon name={p} />
              <span>{p}</span>
              {p === "Alertas" && data.alerts_pending > 0 && (
                <b>{data.alerts_pending}</b>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="monitor-dot" />
          <div>
            Monitoreo regulatorio<small>México · Uso interno</small>
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="breadcrumb">
            Regulación en México <Icon name="arrow" size={13} />{" "}
            <strong>{page}</strong>
          </div>
          <div className="user">
            <span className="environment">
              {dev ? "Entorno local" : "Acceso corporativo"}
            </span>
            <span className="avatar">
              {(me?.name || me?.user_id || "JE").slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{me?.name || me?.user_id || "Johnson Electric"}</strong>
              {dev ? (
                <select
                  aria-label="Rol local de desarrollo"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                >
                  {["consulta", "revisor", "administrador"].map((r) => (
                    <option key={r} value={r}>
                      {label(r)} · local
                    </option>
                  ))}
                </select>
              ) : (
                <small>{label(me?.role || "consulta")}</small>
              )}
            </div>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">JE NOM MONITOR</div>
              <h1>{page === "Inicio" ? "Panorama regulatorio" : page}</h1>
              <p>
                {page === "Inicio"
                  ? "Publicaciones, posibles impactos y seguimiento en un solo lugar."
                  : page === "Publicaciones"
                    ? "Evidencia oficial e historial de documentos detectados."
                    : page === "Alertas"
                      ? "Evalúa cada relación con evidencia y criterio del revisor."
                      : page === "Productos"
                        ? "Un catálogo flexible para todas las familias de productos."
                        : "Cobertura, consultas manuales y trazabilidad de cada ejecución."}
              </p>
            </div>
            <div className="heading-actions">
              {page === "Productos" && admin && (
                <button
                  className="button primary"
                  onClick={() => {
                    setEdit(null);
                    setModal("catalog");
                  }}
                >
                  <Icon name="plus" size={17} />
                  Agregar registro
                </button>
              )}
              {page === "Fuentes y ejecuciones" && admin && (
                <button
                  className="button secondary"
                  onClick={() => {
                    setEdit(null);
                    setModal("source");
                  }}
                >
                  <Icon name="plus" size={17} />
                  Agregar fuente
                </button>
              )}
              {(page === "Inicio" || page === "Fuentes y ejecuciones") &&
                canReview && (
                  <button
                    className="button primary"
                    onClick={() => setModal("run")}
                  >
                    <Icon name="refresh" size={17} />
                    Revisión manual
                  </button>
                )}
            </div>
          </div>
          {authError && (
            <div className="auth-panel">
              <Icon name="shield" size={28} />
              <h2>Acceso requerido</h2>
              <p>
                Inicia sesión con tu cuenta corporativa o proporciona un token
                de acceso para esta aplicación.
              </p>
              <a
                className="button primary"
                href="/.auth/login/aad?post_login_redirect_uri=/"
              >
                Iniciar sesión con Microsoft
              </a>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setToken(tokenDraft);
                }}
              >
                <input
                  type="password"
                  aria-label="Token de acceso"
                  placeholder="Token de acceso (solo en memoria)"
                  value={tokenDraft}
                  onChange={(e) => setTokenDraft(e.target.value)}
                />
                <button className="button secondary">Acceder</button>
              </form>
              <small>{authError}</small>
            </div>
          )}
          {error && (
            <div className="message error" role="alert">
              <div>
                <strong>No se pudo completar la operación</strong>
                <p>{error}</p>
              </div>
              <button
                className="button secondary small"
                onClick={() => void load()}
              >
                Reintentar
              </button>
            </div>
          )}
          {notice && (
            <div className="message success" role="status">
              <Icon name="check" size={18} />
              {notice}
            </div>
          )}
          {dev && (
            <div className="local-note">
              Modo de desarrollo: la identidad y los roles son locales. No
              utilizar para acceso de producción.
            </div>
          )}
          {origin === "demo" && page !== "Inicio" && (
            <div className="message warning">
              DATOS DE DEMOSTRACIÓN · Separados de las publicaciones oficiales.
              No constituyen información regulatoria.
            </div>
          )}
          {busy && (
            <div className="loading" role="status">
              <span />
              Cargando información…
            </div>
          )}
          {me && page === "Inicio" && (
            <>
              <div className="stats">
                {[
                  {
                    title: "Publicaciones detectadas",
                    value:
                      data.publications ??
                      data.publications_detected ??
                      data.publication_count ??
                      0,
                    icon: "Publicaciones",
                    note: "Documentos registrados",
                    color: "green",
                  },
                  {
                    title: "Alertas pendientes",
                    value: data.alerts_pending ?? 0,
                    icon: "Alertas",
                    note: "Requieren revisión humana",
                    color: "amber",
                  },
                  {
                    title: "Fuentes con errores",
                    value: data.sources_with_errors ?? 0,
                    icon: "Fuentes y ejecuciones",
                    note: "Revisa el último intento",
                    color: "red",
                  },
                ].map((s) => (
                  <article className="stat" key={s.title}>
                    <div>
                      <span>{s.title}</span>
                      <span className={`stat-icon ${s.color}`}>
                        <Icon name={s.icon} />
                      </span>
                    </div>
                    <strong>{s.value}</strong>
                    <p>{s.note}</p>
                  </article>
                ))}
              </div>
              <div className="dashboard-grid">
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Próximas entradas en vigor</h2>
                    <span className="subtle">Solo fechas verificadas</span>
                  </div>
                  {array(data.upcoming_effective_dates || data.upcoming)
                    .length ? (
                    <div className="upcoming">
                      {array(
                        data.upcoming_effective_dates || data.upcoming,
                      ).map((p) => (
                        <button
                          className="upcoming-row"
                          key={p.id}
                          onClick={() => void openPublication(p.id)}
                        >
                          <span className="date-square">
                            <Icon name="clock" />
                          </span>
                          <span>
                            <strong>{p.title}</strong>
                            <small>
                              {p.effective_date_evidence ||
                                p.effective_evidence ||
                                "Fecha verificada por revisor"}
                            </small>
                          </span>
                          <b>{fmt(p.effective_on || p.effective_date, true)}</b>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <Empty title="No hay fechas verificadas">
                      Las próximas entradas en vigor aparecerán cuando un
                      revisor registre una fecha y su evidencia.
                    </Empty>
                  )}
                </section>
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Estado de las fuentes</h2>
                    <button
                      className="text-button"
                      onClick={() => navigate("Fuentes y ejecuciones")}
                    >
                      Ver todas <Icon name="arrow" size={14} />
                    </button>
                  </div>
                  {sources.length ? (
                    <div className="source-summary">
                      {sources.map((s) => (
                        <div key={s.id}>
                          <span
                            className={`source-dot ${s.last_error ? "failed" : s.last_success_at ? "success" : ""}`}
                          />
                          <div>
                            <strong>{s.name}</strong>
                            <small>
                              Última revisión exitosa: {fmt(s.last_success_at)}
                            </small>
                          </div>
                          {s.last_error ? (
                            <Badge value="failed">Error</Badge>
                          ) : (
                            <Badge
                              value={
                                s.last_success_at ? "completed" : "pendiente"
                              }
                            >
                              {s.last_success_at
                                ? "Consultada"
                                : "Sin consultar"}
                            </Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty title="Configura las fuentes">
                      Inicializa las fuentes desde el comando documentado y
                      agrega las fichas conocidas que se vigilarán.
                    </Empty>
                  )}
                </section>
              </div>
              <div className="review-note">
                <Icon name="shield" size={23} />
                <div>
                  <strong>La detección es el comienzo de la revisión</strong>
                  <p>
                    Las coincidencias proponen un posible impacto. La
                    aplicabilidad requiere confirmación de un revisor y nunca
                    determina automáticamente si un producto puede importarse.
                  </p>
                </div>
              </div>
            </>
          )}
          {me && page === "Publicaciones" && (
            <section className="panel">
              {toolbar}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Publicación / identificador</th>
                      <th>Fuente / tipo</th>
                      <th>Publicada</th>
                      <th>Primera detección</th>
                      <th>Revisión</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <button
                            className="title-link"
                            onClick={() => void openPublication(p.id)}
                          >
                            {p.title}
                          </button>
                          <small className="mono">
                            {p.official_id ||
                              p.identifier ||
                              "Sin identificador"}
                          </small>
                          {p.is_demo && <Badge value="demo" />}
                        </td>
                        <td>
                          <strong>
                            {p.source_name || sourceName(p.source_id)}
                          </strong>
                          <small>{label(p.kind)}</small>
                        </td>
                        <td>
                          {p.published_on ? (
                            fmt(p.published_on, true)
                          ) : (
                            <span className="subtle">No verificada</span>
                          )}
                        </td>
                        <td>
                          {fmt(p.detected_at || p.first_detected_at)}
                          <small>
                            {p.published_on &&
                            String(p.published_on) <
                              String(
                                p.detected_at || p.first_detected_at,
                              ).slice(0, 10)
                              ? "Detectada después de publicarse"
                              : "Detección ≠ publicación"}
                          </small>
                        </td>
                        <td>
                          <Badge value={p.review_status || p.status} />
                        </td>
                        <td>
                          <button
                            className="icon-button"
                            aria-label={`Ver ${p.title}`}
                            onClick={() => void openPublication(p.id)}
                          >
                            <Icon name="arrow" size={16} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!rows.length && !busy && (
                <Empty title="No hay publicaciones para estos filtros">
                  Ejecuta una revisión manual o ajusta los filtros. Una fuente
                  fallida nunca se considera “sin cambios”.
                </Empty>
              )}
              <Pager page={listPage} total={total} setPage={setListPage} />
            </section>
          )}
          {me && page === "Alertas" && (
            <section className="panel">
              {toolbar}
              <div className="inbox-tabs">
                <button
                  className={!general ? "selected" : ""}
                  onClick={() => {
                    setGeneral(false);
                    setListPage(1);
                  }}
                >
                  Todas las propuestas
                </button>
                <button
                  className={general ? "selected" : ""}
                  onClick={() => {
                    setGeneral(true);
                    setListPage(1);
                  }}
                >
                  Relevancia por evaluar
                </button>
              </div>
              <div className="panel-caption">
                <Icon name="shield" size={16} />
                <span>
                  Relevancia por evaluar: toda publicación conserva una revisión
                  general, incluso sin coincidencias.
                </span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Publicación / posible relación</th>
                      <th>Motivo y evidencia</th>
                      <th>Decisión</th>
                      <th>Estado / responsable</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <button
                            className="title-link"
                            onClick={() =>
                              void openPublication(a.publication_id)
                            }
                          >
                            {a.publication_title ||
                              `Publicación ${a.publication_id}`}
                          </button>
                          <small>
                            {a.catalog_name || catalogName(a.catalog_id)}
                          </small>
                          {a.is_demo && <Badge value="demo" />}
                        </td>
                        <td className="evidence-cell">
                          {a.reason || "Revisión general pendiente"}
                          <small>{text(a.evidence)}</small>
                        </td>
                        <td>
                          <Badge value={a.decision || "propuesta"} />
                        </td>
                        <td>
                          <Badge value={a.status} />
                          <small>{a.assigned_to || "Sin asignar"}</small>
                        </td>
                        <td>
                          <button
                            className="button secondary small"
                            onClick={async () => {
                              try {
                                setEdit(await request(`/alerts/${a.id}`));
                                setModal("alert");
                              } catch (e) {
                                setError((e as Error).message);
                              }
                            }}
                          >
                            {canReview ? "Revisar" : "Detalle"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!rows.length && !busy && (
                <Empty title="No hay alertas para estos filtros">
                  Las publicaciones recopiladas generan una revisión general y
                  propuestas basadas en criterios transparentes.
                </Empty>
              )}
              <Pager page={listPage} total={total} setPage={setListPage} />
            </section>
          )}
          {me && page === "Productos" && (
            <section className="panel">
              {toolbar}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Registro / modelo</th>
                      <th>Tipo / jerarquía</th>
                      <th>Fracción / NICO</th>
                      <th>Responsable</th>
                      <th>Información</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <strong>{p.name}</strong>
                          <small>
                            {[p.model, p.part_number]
                              .filter(Boolean)
                              .join(" · ") ||
                              "Modelo y número de parte pendientes"}
                          </small>
                          {!p.active && (
                            <Badge value="discarded">Inactivo</Badge>
                          )}
                        </td>
                        <td>
                          {label(p.kind)}
                          <small>
                            {p.parent_id
                              ? catalogName(p.parent_id)
                              : "Nivel principal"}
                          </small>
                        </td>
                        <td>
                          <span className="mono">
                            {p.tariff_code || "Pendiente"}
                          </span>
                          <small>NICO: {p.nico || "Pendiente"}</small>
                        </td>
                        <td>{p.owner || "Sin asignar"}</td>
                        <td>
                          {p.missing_fields?.length ? (
                            <span className="incomplete">
                              Faltan {p.missing_fields.length} campos
                              <small>{p.missing_fields.join(", ")}</small>
                            </span>
                          ) : (
                            <Badge value="completed">Completa</Badge>
                          )}
                        </td>
                        <td>
                          <button
                            className="button secondary small"
                            onClick={() => {
                              setEdit(p);
                              setModal("catalog");
                            }}
                          >
                            {admin ? "Editar" : "Detalle"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!rows.length && !busy && (
                <Empty title="Tu catálogo empieza aquí">
                  Agrega familias, subfamilias y productos. Puedes guardar
                  información incompleta y completarla después.
                </Empty>
              )}
              <Pager page={listPage} total={total} setPage={setListPage} />
            </section>
          )}
          {me && page === "Fuentes y ejecuciones" && (
            <>
              <div className="source-cards">
                {sources.map((s) => (
                  <section key={s.id} className="panel source-card">
                    <div className="source-card-heading">
                      <span className="source-letter">
                        {s.kind?.slice(0, 1).toUpperCase() ||
                          s.name.slice(0, 1)}
                      </span>
                      <div>
                        <h2>{s.name}</h2>
                        <small>
                          {s.active
                            ? `Cada ${s.frequency_hours || 24} h · frecuencia deseada`
                            : "Desactivada"}
                        </small>
                      </div>
                      <button
                        className="icon-button"
                        aria-label={`Configurar ${s.name}`}
                        onClick={() => {
                          setEdit(s);
                          setModal("source");
                        }}
                      >
                        <Icon name="arrow" size={16} />
                      </button>
                    </div>
                    <p className="coverage">
                      {s.coverage || "Cobertura pendiente de verificación"}
                    </p>
                    <dl>
                      <div>
                        <dt>Último intento</dt>
                        <dd>{fmt(s.last_attempt_at)}</dd>
                      </div>
                      <div>
                        <dt>Última consulta exitosa</dt>
                        <dd>{fmt(s.last_success_at)}</dd>
                      </div>
                    </dl>
                    {s.last_error && (
                      <p className="source-error">{s.last_error}</p>
                    )}
                    <div className="source-card-footer">
                      <Badge
                        value={
                          s.last_error
                            ? "failed"
                            : s.last_success_at
                              ? "completed"
                              : "pendiente"
                        }
                      >
                        {s.last_error
                          ? "Consulta fallida"
                          : s.last_success_at
                            ? "Última consulta exitosa"
                            : "Sin validar en vivo"}
                      </Badge>
                      {canReview && (
                        <button
                          className="text-button"
                          onClick={() => {
                            setSource(String(s.id));
                            setModal("run");
                          }}
                        >
                          Consultar <Icon name="arrow" size={14} />
                        </button>
                      )}
                    </div>
                  </section>
                ))}
              </div>
              {!sources.length && (
                <section className="panel">
                  <Empty title="No hay fuentes configuradas">
                    Ejecuta “python -m app.cli init-sources” o agrega una fuente
                    oficial. La cobertura inicial es explícitamente limitada.
                  </Empty>
                </section>
              )}
              <section className="panel">
                <div className="panel-heading">
                  <h2>Historial de ejecuciones</h2>
                  <button
                    className="text-button"
                    onClick={() => void load(true)}
                  >
                    <Icon name="refresh" size={15} />
                    Actualizar
                  </button>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Trabajo / fuente</th>
                        <th>Periodo solicitado</th>
                        <th>Inicio / fin</th>
                        <th>Resultado</th>
                        <th>Estado</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.map((j) => (
                        <tr key={j.id}>
                          <td>
                            <span className="mono">#{j.id}</span>
                            <small>
                              {j.source_name || sourceName(j.source_id)}
                            </small>
                          </td>
                          <td>
                            {text(j.period_start)}
                            <small>hasta {text(j.period_end)}</small>
                          </td>
                          <td>
                            {fmt(j.started_at || j.requested_at)}
                            <small>
                              {j.finished_at
                                ? fmt(j.finished_at)
                                : "Pendiente de finalizar"}
                            </small>
                          </td>
                          <td>
                            {j.reviewed_count ?? 0} revisados
                            <small>
                              {j.new_documents ?? j.new_count ?? 0} nuevos ·{" "}
                              {j.modified_documents ?? j.modified_count ?? 0}{" "}
                              modificados · {j.error_count ?? 0} errores
                            </small>
                          </td>
                          <td>
                            <Badge value={j.status} />
                            {j.status === "running" && (
                              <span className="progress-track">
                                <i />
                              </span>
                            )}
                          </td>
                          <td>
                            <button
                              className="button secondary small"
                              onClick={async () => {
                                try {
                                  setJobDetail(await request(`/jobs/${j.id}`));
                                } catch (e) {
                                  setError((e as Error).message);
                                }
                              }}
                            >
                              Ver detalle
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!jobs.length && !busy && (
                  <Empty title="Aún no hay ejecuciones">
                    Solicita una revisión manual y mantén activo el proceso
                    worker para que ejecute los trabajos persistidos.
                  </Empty>
                )}
                <Pager
                  page={listPage}
                  total={data.total || 0}
                  setPage={setListPage}
                />
              </section>
              <p className="footnote">
                Todos los horarios se muestran en America/Mexico_City. Los
                registros se conservan en UTC. La frecuencia deseada requiere un
                programador externo configurado.
              </p>
            </>
          )}
        </main>
        <footer className="footer">
          <span>
            JOHNSON ELECTRIC <i /> JE NOM Monitor
          </span>
          <span>Evaluación regulatoria asistida por evidencia · v0.1</span>
        </footer>
      </div>
      {detail && (
        <Modal
          title="Detalle de publicación"
          close={() => setDetail(null)}
          wide
        >
          <div className="detail-content">
            <div className="detail-tags">
              <Badge value={detail.kind} />
              <Badge value={detail.review_status} />
              {detail.is_demo && <Badge value="demo" />}
            </div>
            <h2>{detail.title}</h2>
            <p className="mono subtle">{detail.official_id}</p>
            {detail.url && (
              <a
                className="text-button"
                href={detail.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Abrir documento oficial <Icon name="external" size={15} />
              </a>
            )}
            <div className="detail-dates">
              <div>
                <small>Fecha de publicación</small>
                <strong>
                  {detail.published_on
                    ? fmt(detail.published_on, true)
                    : "No verificada"}
                </strong>
              </div>
              <div>
                <small>Primera detección</small>
                <strong>
                  {fmt(detail.detected_at || detail.first_detected_at)}
                </strong>
              </div>
              <div>
                <small>Entrada en vigor verificada</small>
                <strong>
                  {detail.effective_verified && detail.effective_on
                    ? fmt(detail.effective_on, true)
                    : "Sin fecha verificada"}
                </strong>
              </div>
            </div>
            <h3>Contenido recuperado</h3>
            {detail.processing_note && (
              <div className="message warning">{detail.processing_note}</div>
            )}
            <pre className="document-content">
              {detail.content ||
                detail.versions?.[0]?.content ||
                "No hay texto procesable. Consulta la evidencia y los pendientes de extracción."}
            </pre>
            <h3>Relaciones propuestas</h3>
            {(detail.alerts || []).length ? (
              <div className="relation-list">
                {detail.alerts.map((a: Row) => (
                  <button
                    key={a.id}
                    className="relation-row"
                    onClick={async () => {
                      try {
                        setEdit(await request(`/alerts/${a.id}`));
                        setDetail(null);
                        setModal("alert");
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    <span>
                      <strong>
                        {a.catalog_name || "Relevancia por evaluar"}
                      </strong>
                      <small>{a.reason}</small>
                    </span>
                    <Badge value={a.decision} />
                    <Icon name="arrow" size={16} />
                  </button>
                ))}
              </div>
            ) : (
              <p className="subtle">Sin relaciones registradas.</p>
            )}
            {canReview && (
              <details className="proposal-form">
                <summary>Proponer relación con una familia o producto</summary>
                <form
                  className="form-grid"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    const result = await mutate(
                      "/alerts",
                      "POST",
                      {
                        publication_id: detail.id,
                        catalog_id: Number(f.get("catalog_id")),
                        reason: f.get("reason"),
                        evidence: f.get("evidence"),
                      },
                      "Relación propuesta para revisión",
                    );
                    if (result)
                      setDetail(await request(`/publications/${detail.id}`));
                  }}
                >
                  <Field label="Familia, subfamilia o producto" full>
                    <select name="catalog_id" required>
                      <option value="">Selecciona un registro activo</option>
                      {catalog
                        .filter(
                          (c) =>
                            c.active &&
                            Boolean(c.is_demo) === Boolean(detail.is_demo),
                        )
                        .map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name} · {label(c.kind)}
                          </option>
                        ))}
                    </select>
                  </Field>
                  <Field label="Motivo de la propuesta" full>
                    <textarea name="reason" required />
                  </Field>
                  <Field
                    label="Evidencia (fragmento y referencia oficial)"
                    full
                  >
                    <textarea name="evidence" required />
                  </Field>
                  <div className="form-actions full">
                    <button className="button secondary" disabled={saving}>
                      Registrar propuesta
                    </button>
                  </div>
                </form>
              </details>
            )}
            <h3>Historial de versiones y evidencia</h3>
            <p className="subtle">
              Cada cambio conserva la captura original. Las reversiones también
              generan una versión.
            </p>
            <div className="version-list">
              {(detail.versions || []).map((v: Row, i: number) => (
                <article key={v.id}>
                  <span className="version-number">{v.sequence || i + 1}</span>
                  <div>
                    <strong>Versión {v.sequence || i + 1}</strong>
                    <small>Consultada: {fmt(v.captured_at)}</small>
                    <small className="mono">
                      SHA-256: {v.content_hash || v.sha256 || "No disponible"}
                    </small>
                    {v.processing_note && (
                      <p className="source-error">{v.processing_note}</p>
                    )}
                    <details>
                      <summary>Ver texto de esta versión</summary>
                      <pre className="document-content">
                        {v.content || "Sin texto extraído"}
                      </pre>
                    </details>
                  </div>
                  <button
                    className="button secondary small"
                    onClick={() => void download(v)}
                  >
                    Evidencia
                  </button>
                </article>
              ))}
            </div>
            {canReview && (
              <form
                className="form-grid review-form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  const body: Row = {
                    kind: f.get("kind"),
                    review_status: f.get("review_status"),
                  };
                  if (
                    (f.get("effective_on") || null) !==
                      (detail.effective_on || null) ||
                    f.get("effective_evidence")
                  )
                    Object.assign(body, {
                      effective_on: f.get("effective_on") || null,
                      effective_evidence: f.get("effective_evidence") || null,
                      effective_verified: Boolean(f.get("effective_on")),
                    });
                  const result = await mutate(
                    `/publications/${detail.id}`,
                    "PATCH",
                    body,
                    "Revisión de publicación actualizada",
                  );
                  if (result)
                    setDetail(await request(`/publications/${detail.id}`));
                }}
              >
                <h3 className="full">Clasificación y fecha verificada</h3>
                <Field label="Tipo de documento">
                  <select name="kind" defaultValue={detail.kind}>
                    {[
                      "clasificacion_pendiente",
                      "proyecto",
                      "norma_definitiva",
                      "modificacion",
                      "cancelacion",
                      "acuerdo",
                      "aviso",
                    ].map((k) => (
                      <option key={k} value={k}>
                        {label(k)}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Estado de revisión">
                  <select
                    name="review_status"
                    defaultValue={detail.review_status}
                  >
                    {["pendiente", "en_revision", "resuelta"].map((k) => (
                      <option key={k} value={k}>
                        {label(k)}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Entrada en vigor verificada">
                  <input
                    type="date"
                    name="effective_on"
                    defaultValue={detail.effective_on || ""}
                  />
                </Field>
                <Field label="Evidencia de fecha (obligatoria si se informa)">
                  <input
                    name="effective_evidence"
                    defaultValue={detail.effective_evidence || ""}
                    placeholder="Artículo, transitorio y referencia"
                  />
                </Field>
                <div className="form-actions full">
                  <button disabled={saving} className="button primary">
                    Guardar revisión
                  </button>
                </div>
              </form>
            )}
          </div>
        </Modal>
      )}
      {error && (modal || detail || jobDetail) && (
        <div className="modal-error message error" role="alert">
          <span>{error}</span>
          <button
            className="icon-button"
            aria-label="Cerrar error"
            onClick={() => setError("")}
          >
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
      {modal === "catalog" && (
        <Modal
          title={edit ? "Detalle del catálogo" : "Agregar al catálogo"}
          close={() => setModal(null)}
          wide
        >
          <form
            className="form-grid modal-form"
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              let technical = {};
              try {
                technical = JSON.parse(
                  String(f.get("technical_characteristics") || "{}"),
                );
              } catch {
                setError(
                  "Las características técnicas deben ser un objeto JSON válido.",
                );
                return;
              }
              const result = await mutate(
                edit ? `/catalog/${edit.id}` : "/catalog",
                edit ? "PATCH" : "POST",
                {
                  name: f.get("name"),
                  kind: f.get("kind"),
                  parent_id: f.get("parent_id")
                    ? Number(f.get("parent_id"))
                    : null,
                  model: f.get("model"),
                  part_number: f.get("part_number"),
                  description: f.get("description"),
                  technical: technical,
                  use: f.get("intended_use"),
                  tariff_code: f.get("tariff_fraction") || null,
                  nico: f.get("nico") || null,
                  owner: f.get("owner"),
                  keywords: split(f.get("keywords")),
                  synonyms: split(f.get("synonyms")),
                  watched_norms: split(f.get("watched_norms")),
                  active: f.get("active") === "on",
                  is_demo: edit ? edit.is_demo : origin === "demo",
                },
                "Registro del catálogo guardado",
              );
              if (result) setModal(null);
            }}
          >
            <div className="form-tip full">
              Puedes guardar datos incompletos. Las familias no están limitadas
              a motores, bombas o actuadores.
            </div>
            <fieldset className="form-grid full" disabled={!admin}>
              <Field label="Nombre *">
                <input name="name" required defaultValue={edit?.name || ""} />
              </Field>
              <Field label="Tipo">
                <select name="kind" defaultValue={edit?.kind || "producto"}>
                  <option value="familia">Familia</option>
                  <option value="subfamilia">Subfamilia</option>
                  <option value="producto">Producto</option>
                </select>
              </Field>
              <Field label="Registro superior">
                <select name="parent_id" defaultValue={edit?.parent_id || ""}>
                  <option value="">Sin superior</option>
                  {catalog
                    .filter((p) => p.id !== edit?.id && p.kind !== "producto")
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({label(p.kind)})
                      </option>
                    ))}
                </select>
              </Field>
              <Field label="Responsable">
                <input name="owner" defaultValue={edit?.owner || ""} />
              </Field>
              <Field label="Modelo">
                <input name="model" defaultValue={edit?.model || ""} />
              </Field>
              <Field label="Número de parte">
                <input
                  name="part_number"
                  defaultValue={edit?.part_number || ""}
                />
              </Field>
              <Field label="Descripción" full>
                <textarea
                  name="description"
                  defaultValue={edit?.description || ""}
                />
              </Field>
              <Field label="Uso previsto" full>
                <textarea name="intended_use" defaultValue={edit?.use || ""} />
              </Field>
              <Field label="Fracción arancelaria">
                <input
                  name="tariff_fraction"
                  defaultValue={edit?.tariff_code || ""}
                />
              </Field>
              <Field label="NICO">
                <input name="nico" defaultValue={edit?.nico || ""} />
              </Field>
              <Field label="Características técnicas (JSON)" full>
                <textarea
                  className="mono"
                  name="technical_characteristics"
                  defaultValue={JSON.stringify(edit?.technical || {}, null, 2)}
                />
              </Field>
              <Field label="Palabras clave (separadas por coma)" full>
                <input
                  name="keywords"
                  defaultValue={(edit?.keywords || []).join(", ")}
                />
              </Field>
              <Field label="Sinónimos (separados por coma)" full>
                <input
                  name="synonyms"
                  defaultValue={(edit?.synonyms || []).join(", ")}
                />
              </Field>
              <Field label="Normas vigiladas (separadas por coma)" full>
                <input
                  name="watched_norms"
                  defaultValue={(edit?.watched_norms || []).join(", ")}
                  placeholder="Identificadores exactos a vigilar"
                />
              </Field>
              <label className="checkbox full">
                <input
                  type="checkbox"
                  name="active"
                  defaultChecked={edit?.active ?? true}
                />
                Registro activo <small>Desactivar conserva el historial.</small>
              </label>
            </fieldset>
            <div className="form-actions full">
              <button
                type="button"
                className="button secondary"
                onClick={() => setModal(null)}
              >
                Cerrar
              </button>
              {admin && (
                <button className="button primary" disabled={saving}>
                  {saving ? "Guardando…" : "Guardar registro"}
                </button>
              )}
            </div>
          </form>
        </Modal>
      )}
      {modal === "alert" && edit && (
        <Modal
          title="Revisión de posible impacto"
          close={() => setModal(null)}
          wide
        >
          <div className="modal-form">
            <h3>
              {edit.publication_title || `Publicación ${edit.publication_id}`}
            </h3>
            <p>{edit.catalog_name || catalogName(edit.catalog_id)}</p>
            <div className="evidence-block">
              <strong>Motivo de la propuesta</strong>
              <p>{edit.reason || "Relevancia por evaluar"}</p>
              <small>{text(edit.evidence)}</small>
            </div>
            <p className="form-tip">
              Confirmar expresa la decisión del revisor. La propuesta automática
              no es una conclusión legal.
            </p>
            <form
              className="form-grid"
              onSubmit={async (e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                const result = await mutate(
                  `/alerts/${edit.id}`,
                  "PATCH",
                  {
                    status: f.get("status"),
                    assigned_to: f.get("assignee"),
                    decision: f.get("decision"),
                    closure_reason: f.get("closure_reason"),
                  },
                  "Revisión guardada con autor y fecha",
                );
                if (result) {
                  setEdit(await request(`/alerts/${edit.id}`));
                }
              }}
            >
              <fieldset className="form-grid full" disabled={!canReview}>
                <Field label="Estado">
                  <select name="status" defaultValue={edit.status}>
                    {["pendiente", "en_revision", "resuelta"].map((s) => (
                      <option key={s} value={s}>
                        {label(s)}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Responsable">
                  <input
                    name="assignee"
                    defaultValue={edit.assigned_to || ""}
                  />
                </Field>
                <Field label="Relación propuesta">
                  <select
                    name="decision"
                    defaultValue={edit.decision || "propuesta"}
                  >
                    <option value="propuesta">
                      Posible impacto · sin decisión
                    </option>
                    <option value="confirmada">
                      Aplicabilidad confirmada por revisor
                    </option>
                    <option value="descartada">
                      Relación descartada por revisor
                    </option>
                  </select>
                </Field>
                <Field
                  label="Justificación de la decisión o cierre (obligatoria al confirmar, descartar o resolver)"
                  full
                >
                  <textarea
                    name="closure_reason"
                    defaultValue={edit.closure_reason || ""}
                  />
                </Field>
              </fieldset>
              {edit.decided_by && (
                <p className="subtle full">
                  Decisión de {edit.decided_by} · {fmt(edit.decided_at)}
                </p>
              )}
              {canReview && (
                <div className="form-actions full">
                  <button disabled={saving} className="button primary">
                    Guardar revisión
                  </button>
                </div>
              )}
            </form>
            <h3>Historial de revisión</h3>
            {(edit.history || []).length ? (
              <div className="comments">
                {edit.history.map((event: Row) => (
                  <article key={event.id}>
                    <strong>{event.actor}</strong>
                    <small>{fmt(event.created_at)}</small>
                    <p>
                      {event.action === "revisar_relacion"
                        ? `Revisión: ${label(event.before?.decision)} → ${label(event.after?.decision)} · ${label(event.after?.status)}`
                        : event.action === "comentar"
                          ? "Comentario registrado"
                          : event.action === "reabrir_por_cambio"
                            ? "Reabierta por cambio de documento"
                            : event.action}
                    </p>
                    {event.after?.closure_reason && (
                      <p>{event.after.closure_reason}</p>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <p className="subtle">Sin decisiones anteriores registradas.</p>
            )}
            <h3>Comentarios</h3>
            {(edit.comments || []).length ? (
              <div className="comments">
                {edit.comments.map((c: Row) => (
                  <article key={c.id}>
                    <strong>{c.author}</strong>
                    <small>{fmt(c.created_at)}</small>
                    <p>{c.body || c.text}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="subtle">Sin comentarios registrados.</p>
            )}
            {canReview && (
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  const result = await mutate(
                    `/alerts/${edit.id}/comments`,
                    "POST",
                    { text: f.get("comment") },
                    "Comentario registrado",
                  );
                  if (result) {
                    const updated = await request(`/alerts/${edit.id}`);
                    setEdit(updated);
                  }
                }}
              >
                <Field label="Agregar comentario">
                  <textarea
                    name="comment"
                    required
                    placeholder="Agrega observaciones y referencias…"
                  />
                </Field>
                <div className="form-actions">
                  <button className="button secondary" disabled={saving}>
                    Agregar comentario
                  </button>
                </div>
              </form>
            )}
          </div>
        </Modal>
      )}
      {modal === "source" && (
        <Modal
          title={edit ? "Configuración de fuente" : "Agregar fuente oficial"}
          close={() => setModal(null)}
        >
          <form
            className="form-grid modal-form"
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const result = await mutate(
                edit ? `/sources/${edit.id}` : "/sources",
                edit ? "PATCH" : "POST",
                {
                  name: f.get("name"),
                  kind: f.get("kind"),
                  urls: String(f.get("urls") || "")
                    .split("\n")
                    .map((u) => u.trim())
                    .filter(Boolean),
                  frequency_hours: Number(f.get("frequency_hours")),
                  active: f.get("enabled") === "on",
                  coverage: f.get("coverage"),
                },
                "Configuración de fuente guardada",
              );
              if (result) setModal(null);
            }}
          >
            <p className="form-tip full">
              Solo destinos oficiales HTTPS permitidos. Los canales no validados
              deben conservar una cobertura explícitamente pendiente.
            </p>
            <fieldset className="form-grid full" disabled={!admin}>
              <Field label="Nombre">
                <input name="name" required defaultValue={edit?.name || ""} />
              </Field>
              <Field label="Conector">
                <select name="kind" defaultValue={edit?.kind || "dof"}>
                  <option value="dof">DOF / SIDOF</option>
                  <option value="platiica">PLATIICA · fichas conocidas</option>
                  <option value="snice">SNICE · enlaces conocidos</option>
                </select>
              </Field>
              <Field label="URLs (una por línea)" full>
                <textarea
                  name="urls"
                  defaultValue={(edit?.urls || []).join("\n")}
                  rows={4}
                />
              </Field>
              <Field label="Frecuencia deseada (horas)">
                <input
                  type="number"
                  min="1"
                  max="8760"
                  required
                  name="frequency_hours"
                  defaultValue={edit?.frequency_hours || 24}
                />
              </Field>
              <label className="checkbox">
                <input
                  type="checkbox"
                  name="enabled"
                  defaultChecked={edit?.active ?? true}
                />
                Activa
              </label>
              <Field label="Cobertura y límites" full>
                <textarea
                  name="coverage"
                  required
                  defaultValue={
                    edit?.coverage ||
                    "Pendiente de validación en vivo. Seguimiento limitado a las URLs configuradas."
                  }
                />
              </Field>
            </fieldset>
            <div className="form-actions full">
              <button
                type="button"
                className="button secondary"
                onClick={() => setModal(null)}
              >
                Cerrar
              </button>
              {admin && (
                <button className="button primary" disabled={saving}>
                  Guardar fuente
                </button>
              )}
            </div>
          </form>
        </Modal>
      )}
      {modal === "run" && (
        <Modal title="Solicitar revisión manual" close={() => setModal(null)}>
          <form
            className="form-grid modal-form"
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const result = await mutate(
                "/jobs",
                "POST",
                {
                  source_id: Number(f.get("source_id")),
                  period_start: f.get("period_start"),
                  period_end: f.get("period_end"),
                },
                "Trabajo registrado. El worker procesará la consulta.",
              );
              if (result) {
                setModal(null);
                navigate("Fuentes y ejecuciones");
                setJobDetail(result);
              }
            }}
          >
            <p className="form-tip full">
              La consulta se registra de forma persistente. El worker
              independiente debe estar activo. Puedes revisar periodos
              anteriores para cubrir interrupciones.
            </p>
            <Field label="Fuente" full>
              <select name="source_id" required defaultValue={source}>
                <option value="">Selecciona una fuente</option>
                {sources
                  .filter((s) => s.active)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Desde">
              <input
                type="date"
                name="period_start"
                required
                defaultValue={new Date().toLocaleDateString("en-CA", {
                  timeZone: "America/Mexico_City",
                })}
              />
            </Field>
            <Field label="Hasta">
              <input
                type="date"
                name="period_end"
                required
                defaultValue={new Date().toLocaleDateString("en-CA", {
                  timeZone: "America/Mexico_City",
                })}
              />
            </Field>
            <div className="form-actions full">
              <button
                type="button"
                className="button secondary"
                onClick={() => setModal(null)}
              >
                Cancelar
              </button>
              <button
                className="button primary"
                disabled={saving || !sources.length}
              >
                {saving ? "Registrando…" : "Solicitar consulta"}
              </button>
            </div>
          </form>
        </Modal>
      )}
      {jobDetail && (
        <Modal
          title={`Ejecución #${jobDetail.id}`}
          close={() => setJobDetail(null)}
        >
          <div className="modal-form">
            <div className="detail-tags">
              <Badge value={jobDetail.status} />
              <strong>
                {jobDetail.source_name || sourceName(jobDetail.source_id)}
              </strong>
            </div>
            <dl className="job-details">
              <div>
                <dt>Periodo solicitado</dt>
                <dd>
                  {text(jobDetail.period_start)} — {text(jobDetail.period_end)}
                </dd>
              </div>
              <div>
                <dt>Solicitada</dt>
                <dd>{fmt(jobDetail.requested_at)}</dd>
              </div>
              <div>
                <dt>Inicio / fin</dt>
                <dd>
                  {fmt(jobDetail.started_at)} / {fmt(jobDetail.finished_at)}
                </dd>
              </div>
              <div>
                <dt>Cobertura observada</dt>
                <dd>
                  {jobDetail.coverage ||
                    "Consulta pendiente o sin cobertura completada"}
                </dd>
              </div>
            </dl>
            {jobDetail.error && (
              <div className="message error">{jobDetail.error}</div>
            )}
            {jobDetail.errors && (
              <pre className="document-content">
                {typeof jobDetail.errors === "string"
                  ? jobDetail.errors
                  : JSON.stringify(jobDetail.errors, null, 2)}
              </pre>
            )}
            {jobDetail.continuation && (
              <div className="message warning">
                Periodo parcial. Existe un punto de continuación; este trabajo
                no representa cobertura completa.
              </div>
            )}
            {(jobDetail.runs || []).length > 0 && (
              <>
                <h3>Intentos registrados</h3>
                <div className="comments">
                  {jobDetail.runs.map((run: Row) => (
                    <article key={run.id}>
                      <strong>
                        Intento {run.id} · {label(run.status)}
                      </strong>
                      <small>
                        {fmt(run.started_at)} — {fmt(run.finished_at)}
                      </small>
                      <p>
                        {run.reviewed_count} revisados · {run.new_count} nuevos
                        · {run.modified_count} modificados · {run.error_count}{" "}
                        errores
                      </p>
                      {run.error && <p className="source-error">{run.error}</p>}
                      <details>
                        <summary>Configuración utilizada</summary>
                        <pre className="document-content">
                          {JSON.stringify(run.source_snapshot || {}, null, 2)}
                        </pre>
                      </details>
                    </article>
                  ))}
                </div>
              </>
            )}
            <div className="form-actions">
              <button
                className="button secondary"
                onClick={async () => {
                  try {
                    setJobDetail(await request(`/jobs/${jobDetail.id}`));
                    await load(true);
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                <Icon name="refresh" size={16} />
                Actualizar
              </button>
              {canReview &&
                ["partial", "interrupted", "failed"].includes(
                  jobDetail.status,
                ) && (
                  <button
                    className="button primary"
                    disabled={saving}
                    onClick={async () => {
                      const result = await mutate(
                        "/jobs",
                        "POST",
                        {
                          source_id: jobDetail.source_id,
                          resume_job_id: jobDetail.id,
                        },
                        "Continuación registrada",
                      );
                      if (result) setJobDetail(result);
                    }}
                  >
                    Reanudar
                  </button>
                )}
            </div>
            <p className="footnote">
              Un error o una ejecución parcial nunca se presentan como “sin
              cambios”.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
}
