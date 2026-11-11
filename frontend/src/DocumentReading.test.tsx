import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DocumentReading, { createReadingLoader, readingParts, reflowStoredText } from "./DocumentReading";
import type { Reading, ReadingBlock } from "./DocumentReading";
import { LanguageProvider } from "./i18n";

const formatted: Reading = {
  format: "structured", blocks: [
    { type: "paragraph", inlines: [{ type: "text", text: "La regulaci" }, { type: "text", text: "ó" },
      { type: "text", text: "n conserva 40 N/mm" }, { type: "sup", children: [{ type: "text", text: "2" }] },
      { type: "text", text: "." }] },
    { type: "heading", level: 3, inlines: [{ type: "text", text: "3.5. Cemento portland compuesto (CPC)" }] },
    { type: "table", rows: [
      { cells: [{ header: true, row_span: 2, col_span: 1, blocks: [{ type: "paragraph", inlines: [{ type: "text", text: "Clase" }] }] },
        { header: true, row_span: 1, col_span: 2, blocks: [{ type: "paragraph", inlines: [{ type: "text", text: "Resistencia" }] }] }] },
      { cells: [{ header: false, row_span: 1, col_span: 1, blocks: [{ type: "paragraph", inlines: [{ type: "text", text: "30" }] }] },
        { header: false, row_span: 1, col_span: 1, blocks: [{ type: "paragraph", inlines: [{ type: "text", text: "50" }] }] }] },
    ] },
  ],
};

describe("document reading", () => {
  it("uses the formatted document delivered with the publication without another request", async () => {
    const load = vi.fn(async () => { throw new Error("This path must not be needed"); });
    render(<LanguageProvider><DocumentReading version={{ id: 7, content: "Broken fallback",
      reading: { ...formatted, version_id: 7 } }} load={load} /></LanguageProvider>);
    expect(screen.getByRole("heading", { name: "3.5. Cemento portland compuesto (CPC)" })).toBeVisible();
    expect(screen.getByRole("table")).toBeVisible();
    expect(load).not.toHaveBeenCalled();
  });

  it("reflows the old stored lines while preserving characters, figures and section numbers", () => {
    const source = "Que en México la regulaci\nó\nn existente para especificaciones de cemento\npermite homologar los\nrequisitos.\n3.5.\nCemento portland compuesto (CPC)\nEl producido con 40 N/mm2\ny 5 800 unidades;\n3.6.\nCemento ordinario (CPO)\nLos m\né\ntodos para cementos hidr\ná\nulicos, as\ní\ncomo sus límites.";
    const blocks = reflowStoredText(source);
    const text = blocks.map((block) => block.inlines?.map((node) => node.text).join("")).join("\n");
    expect(text).toContain("regulación existente");
    expect(text).toContain("permite homologar los requisitos.");
    expect(text).toContain("3.5. Cemento portland compuesto (CPC)");
    expect(text).toContain("40 N/mm2 y 5 800 unidades;");
    expect(text).toContain("métodos para cementos hidráulicos, así como sus límites.");
    expect(text.replace(/\s/g, "")).toBe(source.replace(/\s/g, ""));
    expect(blocks[1].type).toBe("heading");
  });

  it("renders readable paragraphs, section numbers, units and actual table cells", async () => {
    const load = vi.fn(async () => formatted);
    const user = userEvent.setup();
    const view = render(<LanguageProvider><DocumentReading version={{ id: 1, content: "Broken fallback" }} load={load} /></LanguageProvider>);
    expect(await screen.findByRole("heading", { name: "3.5. Cemento portland compuesto (CPC)" })).toBeVisible();
    expect(view.container.querySelector(".document-reading > p")?.textContent).toBe("La regulación conserva 40 N/mm2.");
    expect(view.container.querySelector("sup")).toHaveTextContent("2");
    expect(screen.getByRole("columnheader", { name: "Clase" })).toHaveAttribute("rowspan", "2");
    expect(screen.getByRole("columnheader", { name: "Resistencia" })).toHaveAttribute("colspan", "2");
    expect(screen.getByRole("cell", { name: "30" })).toBeVisible();
    expect(screen.getByRole("region", { name: "Tabla del documento" })).toHaveAttribute("tabindex", "0");
    await user.click(screen.getByRole("button", { name: "Aumentar tamaño del texto" }));
    expect(screen.getByText("19 px")).toBeVisible();
    expect(localStorage.getItem("nom-reading-size")).toBe("19");
    expect((view.container.querySelector(".document-reading") as HTMLElement).style.getPropertyValue("--reading-font-size")).toBe("19px");
    await user.click(screen.getByRole("button", { name: "Reducir tamaño del texto" }));
    expect(screen.getByText("18 px")).toBeVisible();
  });

  it("keeps stored text visible when the reading response cannot load", async () => {
    const load = vi.fn(async () => { throw new Error("HTTP 503"); });
    render(<LanguageProvider><DocumentReading version={{ id: 1, content: "Texto conservado.\n\n3.5. CPC." }} load={load} /></LanguageProvider>);
    expect(await screen.findByText("Texto conservado.")).toBeVisible();
    expect(screen.getByText("3.5. CPC.")).toBeVisible();
    expect(screen.queryByText("HTTP 503")).not.toBeInTheDocument();
  });

  it("reads a plain saved copy without downloading all version bodies and can retry a failed load", async () => {
    const user = userEvent.setup();
    const load = vi.fn().mockRejectedValueOnce(new Error("Unavailable"))
      .mockResolvedValueOnce({ version_id: 10, format: "plain", blocks: [
        { type: "paragraph", inlines: [{ type: "text", text: "La regulaci\nó\nn conserva 40 N/mm2." }] },
      ] });
    render(<LanguageProvider><DocumentReading version={{ id: 10 }} load={load} /></LanguageProvider>);
    expect(await screen.findByRole("alert")).toHaveTextContent("El documento no pudo cargarse.");
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("La regulación conserva 40 N/mm2.")).toBeVisible();
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("cannot replace a newly selected version with a stale reading response", async () => {
    let finish: ((value: Reading) => void) | undefined;
    const latest: Reading = { format: "structured", blocks: [{ type: "paragraph", inlines: [{ type: "text", text: "Versión nueva." }] }] };
    const load = vi.fn((path: string): Promise<Reading> => path.includes("/1/")
      ? new Promise((resolve) => { finish = resolve; }) : Promise.resolve(latest));
    const view = render(<LanguageProvider><DocumentReading version={{ id: 1, content: "Original." }} load={load} /></LanguageProvider>);
    await waitFor(() => expect(load).toHaveBeenCalledWith("/versions/1/reading", expect.any(AbortSignal)));
    view.rerender(<LanguageProvider><DocumentReading version={{ id: 2, content: "New fallback." }} load={load} /></LanguageProvider>);
    expect(await screen.findByText("Versión nueva.")).toBeVisible();
    await act(async () => { finish?.(formatted); });
    expect(screen.getByText("Versión nueva.")).toBeVisible();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("keeps long readings bounded while every paragraph and intact table remains reachable", async () => {
    const user = userEvent.setup();
    const paragraphs: ReadingBlock[] = Array.from({ length: 120 }, (_, index) => ({
      type: "paragraph", inlines: [{ type: "text", text: `Párrafo ${index}. ` + "Contenido conservado. ".repeat(35) }],
    }));
    const blocks = [...paragraphs.slice(0, 60), formatted.blocks[2], ...paragraphs.slice(60)];
    const parts = readingParts(blocks);
    expect(parts.length).toBeGreaterThan(5);
    expect(parts.flat()).toEqual(blocks);
    expect(parts.filter((part) => part.includes(formatted.blocks[2]))).toHaveLength(1);
    const view = render(<LanguageProvider><DocumentReading version={{ id: 8,
      reading: { version_id: 8, format: "structured", blocks } }} load={vi.fn()} /></LanguageProvider>);
    expect(view.container.querySelectorAll(".document-reading p").length).toBeLessThan(20);
    expect(view.container.textContent).toContain("Párrafo 0.");
    expect(view.container.textContent).not.toContain("Párrafo 119.");
    await user.selectOptions(screen.getByRole("combobox", { name: "Ir a la parte" }), String(parts.length - 1));
    expect(view.container.textContent).toContain("Párrafo 119.");
    expect(view.container.textContent).not.toContain("Párrafo 0.");
    const tablePart = parts.findIndex((part) => part.includes(formatted.blocks[2]));
    await user.selectOptions(screen.getByRole("combobox", { name: "Ir a la parte" }), String(tablePart));
    expect(screen.getByRole("columnheader", { name: "Clase" })).toHaveAttribute("rowspan", "2");
    expect(screen.getByRole("cell", { name: "50" })).toBeVisible();
  });

  it("reuses a bounded cache and aborts formatting when the document closes", async () => {
    const request = vi.fn(async () => formatted);
    const load = createReadingLoader(request);
    await load("/versions/1/reading");
    await load("/versions/1/reading");
    expect(request).toHaveBeenCalledTimes(1);
    for (let id = 2; id <= 5; id++) await load(`/versions/${id}/reading`);
    await load("/versions/1/reading");
    expect(request).toHaveBeenCalledTimes(6);
    let signal: AbortSignal | undefined;
    const pending = vi.fn((_path: string, current?: AbortSignal) => {
      signal = current;
      return new Promise(() => {});
    });
    const view = render(<LanguageProvider><DocumentReading version={{ id: 9 }} load={pending} /></LanguageProvider>);
    await waitFor(() => expect(signal).toBeDefined());
    view.unmount();
    expect(signal?.aborted).toBe(true);
  });
});
