import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { ReactNode } from "react";

type Language = "es" | "en";
const english: Record<string, string> = {
  "El boletín": "The bulletin",
  "Explorar publicaciones": "Explore publications",
  "Las fuentes": "The sources",
  "Proyecto de norma": "Draft standard",
  "Norma definitiva": "Final standard",
  Modificación: "Amendment",
  Cancelación: "Cancellation",
  Acuerdo: "Agreement",
  Aviso: "Notice",
  Publicación: "Publication",
  "En espera": "Queued",
  Consultando: "Checking",
  Completada: "Completed",
  "Con error": "Failed",
  "Consulta parcial": "Partial check",
  Interrumpida: "Interrupted",
  Pendiente: "Pending",
  "Fecha por confirmar": "Date to be confirmed",
  "ARCHIVO / LECTURA": "ARCHIVE / READING",
  "Cerrar lectura": "Close reader",
  "Cambio detectado": "Change detected",
  "Muestra sintética": "Synthetic sample",
  "Sin fecha oficial confirmada": "Official date unconfirmed",
  "Detectado {date}": "Detected {date}",
  "Leer {title}": "Read {title}",
  "No se pudo completar la solicitud. Intenta de nuevo.":
    "The request could not be completed. Please try again.",
  "No se pudo conectar con el portal.": "Could not connect to the portal.",
  "Consultando las fuentes. Los resultados aparecerán aquí al terminar.":
    "Checking the sources. Results will appear here when the check is complete.",
  "Las fuentes se consultaron hace menos de 15 minutos. Puedes ver el resultado en Las fuentes.":
    "The sources were checked less than 15 minutes ago. See The sources for the results.",
  "Configura una fuente para comenzar.": "Configure a source to get started.",
  "Consulta en cola. Inicia el portal con MONITOR_ENABLED=true para procesarla.":
    "The check is queued. Start the portal with MONITOR_ENABLED=true to process it.",
  "No fue posible recuperar esta copia.":
    "This saved copy could not be retrieved.",
  "Seguimiento actualizado.": "Monitoring settings updated.",
  "Ir al contenido": "Skip to content",
  "MÉXICO / OBSERVATORIO REGULATORIO": "MEXICO / REGULATORY WATCH",
  "NOM Monitor, inicio": "NOM Monitor, home",
  "UN BOLETÍN DE JOHNSON ELECTRIC": "A JOHNSON ELECTRIC BULLETIN",
  "Lo que se publica.": "What is published.",
  "Lo que cambia.": "What is changing.",
  "NOM Monitor / México": "NOM Monitor / Mexico",
  "Consultando…": "Checking…",
  "Solicitando…": "Requesting…",
  "Consultar fuentes": "Check sources",
  Idioma: "Language",
  "Navegación principal": "Main navigation",
  "EDICIÓN LOCAL": "LOCAL EDITION",
  "CONSULTA ABIERTA": "OPEN ACCESS",
  "Volver a intentar": "Try again",
  "Esta instalación tiene acceso Microsoft habilitado.":
    "Microsoft sign-in is enabled for this installation.",
  "Iniciar sesión": "Sign in",
  "EL BOLETÍN": "THE BULLETIN",
  "Las normas cambian.": "Standards change.",
  "Sigue el movimiento.": "Stay in the know.",
  "Publicaciones oficiales, cambios y referencias para seguir la normativa mexicana desde un solo lugar.":
    "Official publications, changes and references to follow Mexican standards in one place.",
  "Revisión en curso": "Check in progress",
  "Última consulta correcta: {date}": "Last successful check: {date}",
  "La primera consulta está pendiente": "The first check is pending",
  "LA HEMEROTECA": "THE REFERENCE LIBRARY",
  "Busca por título, norma o palabras del documento. Cada publicación conserva su fuente y sus versiones.":
    "Search by title, standard or words in the document. Every publication keeps its source and version history.",
  "Buscar publicaciones": "Search publications",
  "Busca una NOM, un tema o una palabra…":
    "Search for a NOM, a topic or a keyword…",
  "Limpiar búsqueda": "Clear search",
  "ARCHIVO OFICIAL": "OFFICIAL ARCHIVE",
  "Filtrar por fuente": "Filter by source",
  "Todas las fuentes": "All sources",
  referencia: "reference",
  "Tu selección": "Your selection",
  "En portada": "In this edition",
  "El archivo": "The archive",
  "Cargando…": "Loading…",
  "{count} publicación": "{count} publication",
  "{count} publicaciones": "{count} publications",
  "Fecha oficial": "Official date",
  "Periodo de publicación": "Publication period",
  "Todas las fechas": "All dates",
  "Últimos 7 días": "Last 7 days",
  "Últimos 30 días": "Last 30 days",
  Tipo: "Type",
  "Tipo de publicación": "Publication type",
  "Todos los tipos": "All types",
  "Con cambios": "With changes",
  "Quitar filtros": "Clear filters",
  "Ninguna publicación coincide.": "No matching publications.",
  "Tu primera edición comienza aquí.": "Your first edition starts here.",
  "Prueba con otro tema o amplía el periodo. Las publicaciones sin fecha oficial no aparecen al filtrar por últimos días.":
    "Try another topic or a wider period. Publications without an official date are excluded from recent-date filters.",
  "Consulta las fuentes para empezar a reunir publicaciones oficiales. Aquí aparecerán sus títulos, fechas y cambios, sin datos de ejemplo.":
    "Check the sources to start collecting official publications. Their titles, dates and changes will appear here once retrieved.",
  "Ver todas las publicaciones": "View all publications",
  "Preparar el boletín": "Prepare the bulletin",
  MÉXICO: "MEXICO",
  "PRIMERA LECTURA": "FIRST READING",
  "Publicado {date}": "Published {date}",
  "Fecha oficial por confirmar": "Official date to be confirmed",
  "Abrir documento": "Open document",
  Anterior: "Previous",
  Siguiente: "Next",
  "Página {page} de {total}": "Page {page} of {total}",
  "Orden por fecha de publicación. Cuando la fecha oficial falta, se indica expresamente. Una detección de hoy puede corresponder a un documento anterior.":
    "Ordered by publication date. Missing official dates are marked explicitly. A document detected today may have been published earlier.",
  "01 / TU RADAR": "01 / YOUR RADAR",
  "Los temas": "The topics",
  "que te importan.": "that matter to you.",
  "Guarda palabras para volver a buscarlas con un clic.":
    "Save keywords to search for them again with one click.",
  "Nuevo tema de seguimiento": "New topic to follow",
  "Añade un tema…": "Add a topic…",
  "Guardar tema": "Save topic",
  "Quitar tema {topic}": "Remove topic {topic}",
  "Tu lista se guarda en este navegador.":
    "Your list is saved in this browser.",
  "02 / AL CIERRE": "02 / AT A GLANCE",
  "Las fuentes,": "The sources,",
  "a la vista.": "in plain sight.",
  "Requiere atención": "Needs attention",
  "Consulta correcta": "Successful check",
  "Sin consultar": "Not checked",
  "Primera revisión pendiente": "First check pending",
  "Ver cobertura y consultas": "See coverage and checks",
  "03 / EN EL CALENDARIO": "03 / ON THE CALENDAR",
  "Próximas fechas.": "Upcoming dates.",
  "DE DÓNDE VIENE LA INFORMACIÓN": "WHERE THE INFORMATION COMES FROM",
  "Documentos con origen": "Documents with a source",
  "El boletín sigue las páginas configuradas en estas fuentes. Aquí puedes ver cuándo se consultaron y si una revisión quedó incompleta.":
    "The bulletin follows the pages configured for these sources. See when they were checked and whether a check was incomplete.",
  "Consulta automática activa mientras el servidor esté encendido.":
    "Automatic checks are active while the server is running.",
  "La consulta automática está desactivada en esta ejecución.":
    "Automatic checks are turned off for this session.",
  "La frecuencia se indica por fuente.":
    "The frequency is listed for each source.",
  "Consulta incompleta": "Incomplete check",
  "Última consulta correcta": "Last successful check",
  "Pendiente de consultar": "Check pending",
  "Ver motivo de la consulta incompleta": "See why the check was incomplete",
  "Editar seguimiento": "Edit monitoring settings",
  "Páginas a consultar, una por línea": "Pages to check, one per line",
  "Frecuencia en horas": "Frequency in hours",
  "Consultar desde": "Check from",
  "Referencia esperada, opcional": "Expected reference, optional",
  "Revisión automática de esta fuente": "Check this source automatically",
  "Guardar seguimiento": "Save settings",
  "Último intento": "Last attempt",
  Frecuencia: "Frequency",
  "Cada {hours} h": "Every {hours} h",
  Manual: "Manual",
  "Registro de consultas": "Check history",
  "Últimas ejecuciones": "Recent runs",
  "Todavía no se ha solicitado una consulta.":
    "No check has been requested yet.",
  Fuente: "Source",
  "{new} nuevos · {changes} cambios": "{new} new · {changes} changes",
  " · {count} errores": " · {count} errors",
  Retomar: "Resume",
  "Un punto de consulta para la normativa mexicana.":
    "A reference point for Mexican standards.",
  "Ver muestras sintéticas": "Show synthetic samples",
  "Cerrar sesión": "Sign out",
  "PUBLICACIÓN OFICIAL": "OFFICIAL PUBLICATION",
  "Sin fecha confirmada": "Date unconfirmed",
  "DETECTADO EN EL BOLETÍN": "DETECTED IN THE BULLETIN",
  "Abrir en la fuente oficial": "Open the official source",
  "Documento conservado": "Saved document",
  "{count} versión": "{count} version",
  "{count} versiones": "{count} versions",
  "Versión {number}": "Version {number}",
  "Copia consultada el {date}. El texto se presenta tal como fue extraído de la fuente.":
    "Copy retrieved on {date}. The text is shown as extracted from the source.",
  "La fuente no ofreció texto extraíble. Abre el documento oficial o descarga la copia.":
    "The source did not provide extractable text. Open the official document or download the saved copy.",
  "Descargar copia consultada": "Download saved copy",
  "Todavía no hay una copia del documento disponible.":
    "No saved copy is available yet.",
  "Texto oficial en español": "Official text in Spanish",
  "La interfaz está en inglés. Los títulos y documentos oficiales se muestran en el español de la fuente.":
    "The interface is in English. Official titles and documents are shown in their original Spanish.",
  "Notas originales de la fuente": "Original source notes (Spanish)",
  "coverage.dof":
    "Daily DOF index: discovers linked notes and editions. Live daily coverage still needs verification.",
  "coverage.platiica":
    "Tracks the configured PLATIICA standard pages and their document links. Does not discover the complete catalogue.",
  "coverage.snice":
    "Tracks the configured SNICE regulatory pages and their links. Does not automatically consolidate Annex 2.4.1.",
  "coverage.sidof":
    "Tracks a known SIDOF reference document. Does not replace discovery through the daily DOF index.",
  "coverage.demo":
    "Synthetic samples for practising with the portal. This source does not retrieve official publications.",
};
type Translator = (
  message: string,
  params?: Record<string, string | number>,
) => string;
type Locale = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: Translator;
  format: (value?: string | null, time?: boolean) => string;
};
const Context = createContext<Locale | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    try {
      return localStorage.getItem("nom-language") === "en" ? "en" : "es";
    } catch {
      return "es";
    }
  });
  useEffect(() => {
    document.documentElement.lang = language;
    document.title =
      language === "en"
        ? "norma. — The NOM Monitor bulletin"
        : "norma. — El boletín de NOM Monitor";
    try {
      localStorage.setItem("nom-language", language);
    } catch {
      /* Optional preference storage. */
    }
  }, [language]);
  const t: Translator = useCallback(
    (message, params = {}) => {
      const translated =
        language === "en" ? english[message] || message : message;
      return translated.replace(/\{(\w+)\}/g, (match, key) =>
        String(params[key] ?? match),
      );
    },
    [language],
  );
  const format = useCallback(
    (value?: string | null, time = false) => {
      if (!value) return t("Pendiente");
      const date = new Date(
        value.length === 10
          ? `${value}T12:00:00Z`
          : /Z$|[+-]\d\d:\d\d$/.test(value)
            ? value
            : `${value}Z`,
      );
      if (Number.isNaN(date.valueOf())) return t("Fecha por confirmar");
      return new Intl.DateTimeFormat(language === "en" ? "en-US" : "es-MX", {
        timeZone: value.length === 10 ? "UTC" : "America/Mexico_City",
        day: "numeric",
        month: "short",
        year: "numeric",
        ...(time ? { hour: "2-digit", minute: "2-digit" } : {}),
      }).format(date);
    },
    [language, t],
  );
  return (
    <Context.Provider value={{ language, setLanguage, t, format }}>
      {children}
    </Context.Provider>
  );
}

export function useLanguage() {
  const value = useContext(Context);
  if (!value) throw new Error("Missing language provider");
  return value;
}
