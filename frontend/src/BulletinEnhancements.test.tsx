import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "./i18n";
import { PublicationFacts, VersionComparison, VisitSummary } from "./BulletinEnhancements";

const previous = { version_id: 10, content_hash: "previous", visited_at: "2026-11-15T16:00:00Z" };
const current = { version_id: 20, content_hash: "current", visited_at: "2026-11-17T16:00:00Z" };
const summary = { cursor: current, first_visit: false, reset: false, new_publications: 2,
  changed_publications: 1, new_catalog: 3, changed_catalog: 0 };
const storageKey = "nom-visit-v1:portal:false";
const versions = [{ id: 3, sequence: 3, captured_at: "2026-11-17" },
  { id: 2, sequence: 2, captured_at: "2026-11-15" }, { id: 1, sequence: 1, captured_at: "2026-11-10" }];
function language(language = "es") { history.replaceState({}, "", `/?lang=${language}`); }

describe("visit summary", () => {
  it("keeps the previous-visit cursor across tabs and advances it for the next visit", async () => {
    language();
    localStorage.setItem(storageKey, JSON.stringify(previous));
    const request = vi.fn().mockResolvedValue(summary);
    const select = vi.fn();
    const props = { scope: "portal", demo: false, visible: true, paused: false, request, onSelect: select, onSources: vi.fn() };
    const view = render(<LanguageProvider><VisitSummary {...props} /></LanguageProvider>);
    const button = await screen.findByRole("button", { name: /Publicaciones incorporadas/ });
    await userEvent.click(button);
    expect(select).toHaveBeenCalledWith({ after: 10, type: "new", catalog: false });
    expect(JSON.parse(localStorage.getItem(storageKey)!)).toEqual(current);
    view.rerender(<LanguageProvider><VisitSummary {...props} visible={false} /></LanguageProvider>);
    view.rerender(<LanguageProvider><VisitSummary {...props} /></LanguageProvider>);
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    expect(request.mock.calls[1][0]).toContain("after_version_id=10");
    view.unmount();
    render(<LanguageProvider><VisitSummary {...props} /></LanguageProvider>);
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    expect(request.mock.calls[2][0]).toContain("after_version_id=20");
  });

  it("marks the summary reviewed locally and explains that imported records can be older publications", async () => {
    language();
    localStorage.setItem(storageKey, JSON.stringify(previous));
    const request = vi.fn((path: string) => Promise.resolve(path.includes("after_version_id=10") ? summary
      : { ...summary, new_publications: 0, changed_publications: 0, new_catalog: 0 }));
    render(<LanguageProvider><VisitSummary scope="portal" demo={false} visible paused={false} request={request} onSelect={vi.fn()} onSources={vi.fn()} /></LanguageProvider>);
    await screen.findByText("Incorporado al portal no significa publicado hoy.");
    await userEvent.click(screen.getByRole("button", { name: "Marcar resumen como revisado" }));
    await waitFor(() => expect(request.mock.calls.at(-1)?.[0]).toContain("after_version_id=20"));
    expect(await screen.findByText("Resumen marcado como revisado en este navegador.")).toBeVisible();
    expect(screen.getByRole("button", { name: /Publicaciones incorporadas/ })).toBeDisabled();
    expect(JSON.parse(localStorage.getItem(storageKey)!)).toEqual(current);
  });

  it("starts tracking on the first visit and works when browser storage is unavailable", async () => {
    language("en");
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Disabled"); });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Disabled"); });
    try {
      const request = vi.fn().mockResolvedValue({ ...summary, first_visit: true,
        new_publications: 0, changed_publications: 0, new_catalog: 0 });
      render(<LanguageProvider><VisitSummary scope="portal" demo={false} visible paused={false} request={request} onSelect={vi.fn()} onSources={vi.fn()} /></LanguageProvider>);
      expect(await screen.findByRole("heading", { name: "Your first summary" })).toBeVisible();
      expect(screen.getByText("Tracking starts today. Historical records are not counted as new arrivals.")).toBeVisible();
      expect(request.mock.calls[0][0]).not.toContain("after_version_id");
    } finally { get.mockRestore(); set.mockRestore(); }
  });

  it("shows summary failures locally without claiming there were no updates", async () => {
    language();
    const request = vi.fn().mockRejectedValue(new Error("Unavailable"));
    render(<LanguageProvider><VisitSummary scope="portal" demo={false} visible paused={false} request={request} onSelect={vi.fn()} onSources={vi.fn()} /></LanguageProvider>);
    expect(await screen.findByText("El resumen no pudo actualizarse. Las publicaciones siguen disponibles.")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Publicaciones incorporadas/ })).not.toBeInTheDocument();
  });

  it("distinguishes an ongoing check from an incomplete check and identifies the completed period", async () => {
    language();
    const sources = vi.fn();
    const completed = { finished_at: "2026-11-17T12:00:00Z", period_start: "2026-11-02", period_end: "2026-11-03" };
    const request = vi.fn().mockResolvedValueOnce({ ...summary, latest_check: { status: "running" }, last_complete_check: completed })
      .mockResolvedValueOnce({ ...summary, new_publications: 0, changed_publications: 0, new_catalog: 0,
        latest_check: { status: "partial" }, last_complete_check: completed });
    render(<LanguageProvider><VisitSummary scope="portal" demo={false} visible paused={false} request={request} onSelect={vi.fn()} onSources={sources} /></LanguageProvider>);
    await userEvent.click(await screen.findByRole("button", { name: "SIDOF tiene una consulta en curso. Ver estado de fuentes." }));
    expect(sources).toHaveBeenCalledOnce();
    expect(screen.queryByText("La revisión más reciente está incompleta. Ver estado de fuentes.")).not.toBeInTheDocument();
    expect(screen.getByText(/Periodo de esa consulta:/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Marcar resumen como revisado" }));
    expect(await screen.findByRole("button", { name: "La revisión más reciente está incompleta. Ver estado de fuentes." })).toBeVisible();
  });
});

describe("publication facts", () => {
  it("keeps the source's status distinct from publication kind and hides unverified effective dates", () => {
    language();
    const publication = { title: "Norma NOM-EM-023-SE-2026, muestra controlada", official_id: "DOF:123",
      kind: "norma_definitiva", source_name: "SIDOF", published_on: "2026-11-02",
      effective_on: "2026-12-01", effective_verified: false };
    const view = render(<LanguageProvider><PublicationFacts publication={publication} capturedAt="2026-11-17" /></LanguageProvider>);
    const facts = screen.getByRole("region", { name: "Ficha de la publicación" });
    expect(within(facts).getByText("NOM-EM-023-SE-2026")).toBeVisible();
    expect(within(facts).getByText("No informado por la fuente")).toBeVisible();
    expect(within(facts).queryByText(/dic.*2026/)).not.toBeInTheDocument();
    view.rerender(<LanguageProvider><PublicationFacts publication={{ ...publication, effective_verified: true }} /></LanguageProvider>);
    expect(within(facts).queryByText(/dic.*2026/)).not.toBeInTheDocument();
    view.rerender(<LanguageProvider><PublicationFacts publication={{ ...publication, effective_verified: true, effective_evidence: "Transitorio de la copia verificada." }} /></LanguageProvider>);
    expect(within(facts).getByText(/dic.*2026/)).toBeVisible();
  });
});

describe("version comparison", () => {
  it("loads only on demand, highlights changes safely and renders one page at a time", async () => {
    language();
    const request = vi.fn((path: string) => Promise.resolve({ classification: "text_changed", total: 13,
      page_size: 12, added: 1, removed: 0, modified: 12,
      items: path.endsWith("page=2") ? [{ kind: "added", before: "", after: "Final block" }]
        : Array.from({ length: 12 }, (_, i) => ({ kind: "modified", before: `Valor ${i}: 40`, after: `Valor ${i}: 50`,
          before_marks: [{ kind: "equal", text: `Valor ${i}: ` }, { kind: "removed", text: "40" }],
          after_marks: [{ kind: "equal", text: `Valor ${i}: ` }, { kind: "added", text: "50" }] })),
    }));
    const view = render(<LanguageProvider><VersionComparison publicationId={7} versions={versions} selectedId={3} request={request} /></LanguageProvider>);
    expect(request).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Comparar versiones" }));
    await screen.findByText("Hay diferencias en el texto guardado.");
    expect(view.container.querySelectorAll(".comparison-row")).toHaveLength(12);
    expect(view.container.querySelector(".comparison-row del")).toHaveTextContent("40");
    expect(view.container.querySelector(".comparison-row ins")).toHaveTextContent("50");
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Final block")).toBeVisible();
    expect(view.container.querySelectorAll(".comparison-row")).toHaveLength(1);
    expect(request.mock.calls[0][0]).toContain("from_version_id=2&to_version_id=3");
    expect(request.mock.calls.at(-1)?.[0]).toContain("page=2");
  });

  it("ignores an old pair's late response after selecting another baseline", async () => {
    language();
    let finish!: (value: unknown) => void;
    let oldSignal: AbortSignal | undefined;
    const request = vi.fn((path: string, _method?: string, _body?: unknown, signal?: AbortSignal) => {
      if (path.includes("from_version_id=2")) {
        oldSignal = signal;
        return new Promise((resolve) => { finish = resolve; });
      }
      return Promise.resolve({ classification: "unchanged", items: [], total: 0 });
    });
    render(<LanguageProvider><VersionComparison publicationId={7} versions={versions} selectedId={3} request={request} /></LanguageProvider>);
    await userEvent.click(screen.getByRole("button", { name: "Comparar versiones" }));
    await waitFor(() => expect(request).toHaveBeenCalledOnce());
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Comparar con la versión anterior" }), "1");
    expect(await screen.findByText("El texto guardado es idéntico en ambas copias.")).toBeVisible();
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => finish({ classification: "text_changed", items: [], total: 0 }));
    expect(screen.queryByText("Hay diferencias en el texto guardado.")).not.toBeInTheDocument();
  });

  it("translates format-only results and never executes text from saved copies", async () => {
    language("en");
    const request = vi.fn().mockResolvedValueOnce({ classification: "spacing_only", items: [], total: 0 })
      .mockResolvedValueOnce({ classification: "text_changed", total: 1, page_size: 12, added: 1, removed: 0, modified: 0,
        items: [{ kind: "added", before: "", after: "<script>window.untrusted = true</script>" }] });
    const view = render(<LanguageProvider><VersionComparison publicationId={7} versions={versions} selectedId={3} request={request} /></LanguageProvider>);
    await userEvent.click(screen.getByRole("button", { name: "Compare versions" }));
    expect(await screen.findByText("The text matches after normalizing whitespace and equivalent characters.")).toBeVisible();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Compare with an earlier version" }), "1");
    expect(await screen.findByText("<script>window.untrusted = true</script>")).toBeVisible();
    expect(view.container.querySelector("script")).toBeNull();
  });
});
