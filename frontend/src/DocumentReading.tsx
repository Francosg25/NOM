import { Fragment, memo, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useLanguage } from "./i18n";

export type Inline = {
  type: "text" | "strong" | "em" | "sup" | "sub" | "break" | "image";
  text?: string;
  children?: Inline[];
  src?: string | null;
  alt?: string;
};
export type ReadingBlock = {
  type: "paragraph" | "heading" | "table" | "list";
  inlines?: Inline[];
  level?: number;
  ordered?: boolean;
  start?: number;
  items?: ReadingBlock[][];
  rows?: { cells: { header: boolean; row_span: number; col_span: number; blocks: ReadingBlock[] }[] }[];
};
export type Reading = { version_id?: number; format: "structured" | "plain"; blocks: ReadingBlock[] };
export type ReadingLoader = (path: string, signal?: AbortSignal) => Promise<unknown>;

export function createReadingLoader(request: ReadingLoader): ReadingLoader {
  // Scoped to a portal session, with a small bound for long official documents.
  const cache = new Map<string, Reading>();
  return async (path, signal) => {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const saved = cache.get(path);
    if (saved) {
      cache.delete(path);
      cache.set(path, saved);
      return saved;
    }
    const value = await request(path, signal) as Reading;
    const id = Number(path.match(/^\/versions\/(\d+)\/reading$/)?.[1]);
    if (!signal?.aborted && Array.isArray(value?.blocks) &&
      (!value.version_id || value.version_id === id)) {
      cache.set(path, value);
      if (cache.size > 4) cache.delete(cache.keys().next().value!);
    }
    return value;
  };
}

function inlineSize(nodes: Inline[]): number {
  return nodes.reduce((size, node) => size + (node.text?.length || 0) +
    (node.type === "image" ? 800 : 0) + inlineSize(node.children || []), 0);
}
function blockSize(block: ReadingBlock): number {
  return 80 + inlineSize(block.inlines || []) +
    (block.items || []).reduce((size, item) => size + item.reduce((n, child) => n + blockSize(child), 0), 0) +
    (block.rows || []).reduce((size, row) => size + row.cells.reduce((n, cell) =>
      n + 120 + cell.blocks.reduce((sum, child) => sum + blockSize(child), 0), 0), 0);
}

export function readingParts(blocks: ReadingBlock[]): ReadingBlock[][] {
  // Keep tables/lists intact. Every block appears once, in its original order.
  const parts: ReadingBlock[][] = [];
  let current: ReadingBlock[] = [], size = 0;
  for (const block of blocks) {
    const cost = blockSize(block);
    if (current.length && (size + cost > 8500 || current.length >= 50)) {
      const heading = current.at(-1)?.type === "heading" ? current.pop() : undefined;
      if (current.length) parts.push(current);
      current = heading ? [heading] : [];
      size = heading ? blockSize(heading) : 0;
    }
    current.push(block);
    size += cost;
  }
  if (current.length) parts.push(current);
  return parts;
}

export function reflowStoredText(content: string): ReadingBlock[] {
  // Only whitespace is changed. Rejoin the common inline split “regulaci / ó / n”
  // and rebuild paragraphs at explicit section labels and sentence boundaries.
  let text = content.replace(/\r\n?/g, "\n")
    .split("\n").map((line) => line.trim()).join("\n")
    .replace(/([\p{Ll}]{2,}i)\s*\n\s*ó\s*\n\s*(n\b)/gu, "$1ó$2");
  // Repair only recognizable words split by the former span-to-line extractor.
  // Match the original letters and remove newlines; do not replace legal text.
  for (const word of ["así", "México", "método", "métodos", "hidráulico", "hidráulicos",
    "parámetro", "parámetros", "químico", "químicos", "físico", "físicos", "técnico", "técnicos",
    "carácter", "público", "pública", "específica", "específicas", "característica", "características",
    "artículo", "artículos", "límite", "límites", "mínimo", "mínimos", "máximo", "máximos"] ) {
    const pattern = new RegExp(`(?<!\\p{L})${Array.from(word).join("(?:\\n)?")}(?!\\p{L})`, "giu");
    text = text.replace(pattern, (match) => match.replace(/\n/g, ""));
  }
  const result: ReadingBlock[] = [];
  let paragraph = "", number = "";
  const add = (value: string, heading = false) => {
    if (value.trim()) result.push({ type: heading ? "heading" : "paragraph",
      ...(heading ? { level: /^\d+\.\d+/.test(value) ? 3 : 2 } : {}),
      inlines: [{ type: "text", text: value.trim() }] });
  };
  const flush = () => { add(paragraph); paragraph = ""; };
  for (const original of text.split("\n")) {
    const line = original.trim();
    if (!line) { flush(); continue; }
    if (/^[,;:.]$/.test(line) && paragraph) { paragraph += line; continue; }
    if (/^\d+(?:\.\d+)*\.$/.test(line)) {
      flush(); if (number) add(number); number = line; continue;
    }
    if (number) { add(`${number} ${line}`, line.length < 180); number = ""; continue; }
    const heading = /^(?:\d+(?:\.\d+)*\.?)\s+\D/.test(line) && line.length < 180 ||
      /^(?:CONSIDERANDO|TRANSITORIOS|[IÍ]NDICE DEL CONTENIDO|CAP[IÍ]TULOS)$/.test(line);
    if (heading) { flush(); add(line, true); continue; }
    if (/^(?:Que\s|Al margen\s)/.test(line) || /[.;:!?]$/.test(paragraph)) flush();
    paragraph += `${paragraph ? " " : ""}${line}`;
  }
  flush(); if (number) add(number);
  return result;
}

function Figure({ src, alt }: { src?: string | null; alt?: string }) {
  const { t } = useLanguage();
  const [failed, setFailed] = useState(false);
  let safe = false;
  try {
    const url = new URL(src || "");
    safe = url.protocol === "https:" && url.hostname === "sidof.segob.gob.mx" &&
      (!url.port || url.port === "443") &&
      /^\/imagenes_diarios\/[A-Za-z0-9_./-]+\.(png|jpe?g|gif|webp)$/i.test(url.pathname) &&
      !url.username && !url.password && !url.search && !url.hash;
  } catch { /* Missing figures remain explicitly identified. */ }
  return safe && !failed ? (
    <img className="document-figure" src={src!} loading="lazy" decoding="async" referrerPolicy="no-referrer"
      alt={alt || t("Figura o fórmula del documento oficial")}
      onError={() => setFailed(true)} />
  ) : <span className="document-figure-caption">{t("Consulta esta figura o fórmula en la fuente oficial.")}</span>;
}

function InlineContent({ nodes }: { nodes: Inline[] }) {
  return nodes.map((node, index) => {
    const children = node.children ? <InlineContent nodes={node.children} /> : null;
    switch (node.type) {
      case "text": return <Fragment key={index}>{node.text}</Fragment>;
      case "strong": return <strong key={index}>{children}</strong>;
      case "em": return <em key={index}>{children}</em>;
      case "sup": return <sup key={index}>{children}</sup>;
      case "sub": return <sub key={index}>{children}</sub>;
      case "break": return <br key={index} />;
      case "image": return <Figure key={index} src={node.src} alt={node.alt} />;
      default: return null;
    }
  });
}

function Blocks({ blocks }: { blocks: ReadingBlock[] }) {
  const { t } = useLanguage();
  return blocks.map((block, index) => {
    const content = <InlineContent nodes={block.inlines || []} />;
    switch (block.type) {
      case "heading": return block.level === 3 ? <h3 key={index}>{content}</h3> : <h2 key={index}>{content}</h2>;
      case "paragraph": return <p key={index}>{content}</p>;
      case "list": {
        const items = (block.items || []).map((item, i) => <li key={i}><ReadingBlocks blocks={item} /></li>);
        return block.ordered ? <ol start={block.start || 1} key={index}>{items}</ol> : <ul key={index}>{items}</ul>;
      }
      case "table": return (
        <div key={index} className="document-table-scroll" role="region" tabIndex={0} aria-label={t("Tabla del documento")}> 
          <table><tbody>{(block.rows || []).map((row, r) => <tr key={r}>
            {row.cells.map((cell, c) => {
              const Cell = cell.header ? "th" : "td";
              return <Cell key={c} rowSpan={cell.row_span} colSpan={cell.col_span}>
                <ReadingBlocks blocks={cell.blocks} />
              </Cell>;
            })}
          </tr>)}</tbody></table>
        </div>
      );
      default: return null;
    }
  });
}

export const ReadingBlocks = memo(Blocks);

function DocumentReading({ version, load }: {
  version: { id: number; content?: string; reading?: Reading };
  load: ReadingLoader;
}) {
  const { t } = useLanguage();
  const supplied = version.reading && Array.isArray(version.reading.blocks) &&
    (!version.reading.version_id || version.reading.version_id === version.id) ? version.reading : null;
  const [reading, setReading] = useState<Reading | null>(supplied);
  const [loading, setLoading] = useState(!supplied);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [part, setPart] = useState(0);
  const documentRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(() => {
    const value = Number(localStorage.getItem("nom-reading-size"));
    return value >= 16 && value <= 24 ? value : 18;
  });
  useEffect(() => {
    let current = true;
    const controller = new AbortController();
    setPart(0);
    setFailed(false);
    if (version.reading && Array.isArray(version.reading.blocks) &&
      (!version.reading.version_id || version.reading.version_id === version.id)) {
      setReading(version.reading);
      setLoading(false);
      return;
    }
    setReading(null);
    setLoading(true);
    void load(`/versions/${version.id}/reading`, controller.signal).then((result) => {
      const value = result as Reading;
      if (!Array.isArray(value?.blocks) || value.version_id && value.version_id !== version.id) throw new Error("Invalid reading");
      if (current) setReading(value);
    }).catch(() => { if (current) setFailed(true); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [version.id, version.reading, load, attempt]);
  const resize = (next: number) => {
    setSize(next);
    localStorage.setItem("nom-reading-size", String(next));
  };
  const content = useMemo(() => reading?.format === "structured" ? reading.blocks :
    reflowStoredText(version.content || reading?.blocks.map((block) =>
      (block.inlines || []).map((node) => node.text || "").join("")).join("\n\n") || ""), [reading, version.content]);
  const parts = useMemo(() => readingParts(content), [content]);
  const selectedPart = Math.min(part, Math.max(0, parts.length - 1));
  const move = (next: number) => {
    setPart(next);
    const scroller = documentRef.current?.closest(".reader-body");
    if (scroller) scroller.scrollTop = 0;
  };
  const navigation = (bottom = false) => !loading && parts.length > 1 && (
    <nav className={`reading-pagination${bottom ? " reading-pagination-bottom" : ""}`}
      aria-label={t(bottom ? "Continuar lectura" : "Navegación del documento")}>
      <button type="button" disabled={selectedPart === 0} onClick={() => move(selectedPart - 1)}>{t("Anterior")}</button>
      {bottom ? <span aria-live="polite">{t("Parte {number} de {total}", { number: selectedPart + 1, total: parts.length })}</span> :
        <label><span>{t("Parte")}</span><select aria-label={t("Ir a la parte")} value={selectedPart}
          onChange={(event) => move(Number(event.target.value))}>
          {parts.map((_, index) => <option value={index} key={index}>
            {t("{number} de {total}", { number: index + 1, total: parts.length })}
          </option>)}
        </select></label>}
      <button type="button" disabled={selectedPart === parts.length - 1} onClick={() => move(selectedPart + 1)}>{t("Siguiente")}</button>
    </nav>
  );
  return (
    <>
      <div className="reading-tools" role="group" aria-label={t("Tamaño del texto")}>
        <span>{t("Tamaño del texto")}</span>
        <button type="button" disabled={size <= 16} aria-label={t("Reducir tamaño del texto")} onClick={() => resize(size - 1)}>A−</button>
        <output aria-live="polite">{size} px</output>
        <button type="button" disabled={size >= 24} aria-label={t("Aumentar tamaño del texto")} onClick={() => resize(size + 1)}>A+</button>
      </div>
      {navigation()}
      <div className="document-text document-reading" ref={documentRef} data-reading-format={reading?.format === "structured" ? "structured" : "reflowed"}
        lang="es" style={{ "--reading-font-size": `${size}px` } as CSSProperties} aria-busy={loading}>
        {loading ? <p role="status">{t("Preparando lectura…")}</p> : content.length ? <ReadingBlocks key={selectedPart} blocks={parts[selectedPart]} /> : failed ?
          <div className="reader-load-error" role="alert">
            <p>{t("El documento no pudo cargarse. Vuelve a intentarlo.")}</p>
            <button type="button" className="button paper" onClick={() => setAttempt((value) => value + 1)}>{t("Reintentar")}</button>
          </div> :
          <p>{t("La fuente no ofreció texto extraíble. Abre el documento oficial o descarga la copia.")}</p>}
      </div>
      {navigation(true)}
    </>
  );
}

export default memo(DocumentReading);
