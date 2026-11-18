import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "./i18n";
import { ArchiveTools, calendarRange, emptyArchiveDates, PublicationHistory } from "./PublicationHistory";
import Portal from "./Portal";

vi.mock("./apiAccess", () => ({ authConfig: async () => ({ mode: "portal" }), restoreSession: async () => "", accessToken: async () => "", signIn: vi.fn(), signOut: vi.fn() }));
const publication = { id: 10, title: "NOM-016-ENER-2016 · prueba controlada", norm_codes: ["NOM-016-ENER-2016"], kind: "norma_vigente", source_name: "PLATIICA" };
const coverage = { total: 40, first_publication: "2020-01-01", last_publication: "2026-11-17", years: [{ year: 2020, count: 20 }], verified_days: 2, incomplete_days: 1 };
const json = (value: unknown) => new Response(JSON.stringify(value));

describe("historical archive", () => {
  it("calculates complete calendar months including leap years", () => {
    expect(calendarRange("2020", "02")).toEqual({ from: "2020-02-01", to: "2020-02-29" });
    expect(calendarRange("2021", "02")).toEqual({ from: "2021-02-01", to: "2021-02-28" });
    expect(calendarRange("2020")).toEqual({ from: "2020-01-01", to: "2020-12-31" });
    expect(calendarRange("")).toEqual({ from: "", to: "" });
  });

  it("shows honest coverage and restricts import controls to an administrator", async () => {
    const request = vi.fn(async () => coverage);
    render(<LanguageProvider><ArchiveTools dates={emptyArchiveDates} change={vi.fn()} request={request} demo={false} admin={false} sourceId={1} progress="" queued={vi.fn()} sourcesView={vi.fn()} /></LanguageProvider>);
    expect(await screen.findByText(/^40 publicaciones guardadas/)).toBeVisible();
    expect(screen.getByText(/no acreditan que todos los días/)).toBeVisible();
    expect(screen.queryByText("Cargar un periodo anterior")).not.toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("queues a selected historical period through the existing background jobs API", async () => {
    const user = userEvent.setup(); const queued = vi.fn();
    const request = vi.fn(async (path: string) => path.startsWith("/history/") ? coverage : { id: "job", status: "queued" });
    render(<LanguageProvider><ArchiveTools dates={emptyArchiveDates} change={vi.fn()} request={request} demo={false} admin sourceId={1} progress="" queued={queued} sourcesView={vi.fn()} /></LanguageProvider>);
    await user.click(screen.getByText("Cargar un periodo anterior"));
    await user.click(screen.getByRole("button", { name: "Cargar periodo histórico" }));
    expect(await screen.findByText(/La carga quedó en cola/)).toBeVisible();
    expect(request).toHaveBeenCalledWith("/jobs", "POST", expect.objectContaining({ source_id: 1, period_start: expect.stringMatching(/^\d{4}-01-01$/) }));
    expect(queued).toHaveBeenCalledOnce();
  });

  it("keeps reference context and allows opening each related document", async () => {
    const user = userEvent.setup(); const open = vi.fn();
    const request = vi.fn(async () => ({ norm_codes: publication.norm_codes, total: 1, items: [{ id: 2, title: "Aviso controlado", kind: "aviso", published_on: "2020-02-29", reference_location: "text", reference_snippet: "Se menciona NOM-016-ENER-2016." }] }));
    render(<LanguageProvider><PublicationHistory publication={publication} request={request} open={open} /></LanguageProvider>);
    expect(await screen.findByText("Se menciona NOM-016-ENER-2016.")).toBeVisible();
    expect(screen.getByText("Referencia en el texto")).toBeVisible();
    expect(screen.getByText(/Una mención no acredita/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Abrir documento" }));
    expect(open).toHaveBeenCalledWith(2);
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("ignores a late history response after selecting another NOM code", async () => {
    const user = userEvent.setup(); let resolve!: (value: unknown) => void;
    const request = vi.fn((path: string) => path.includes("norm_code=") ? Promise.resolve({ norm_codes: ["NOM-001-SE-2020", "NOM-002-SE-2020"], items: [{ id: 2, title: "Nueva selección", reference_snippet: "Referencia exacta" }] }) : new Promise((done) => { resolve = done; }));
    render(<LanguageProvider><PublicationHistory publication={{ ...publication, norm_codes: ["NOM-001-SE-2020", "NOM-002-SE-2020"] }} request={request} open={vi.fn()} /></LanguageProvider>);
    await user.selectOptions(screen.getByRole("combobox", { name: "Clave NOM" }), "NOM-002-SE-2020");
    await screen.findByText("Nueva selección");
    await act(async () => resolve({ items: [{ id: 1, title: "Respuesta anterior" }] }));
    expect(screen.queryByText("Respuesta anterior")).not.toBeInTheDocument();
  });

  it("connects catalogue history without loading document bodies and resets archive dates on navigation", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn(async (input: string) => {
      const url = new URL(input, "http://localhost");
      if (url.pathname === "/api/me") return json({ role: "consulta" });
      if (url.pathname === "/api/dashboard") return json({ sources: [] });
      if (url.pathname === "/api/jobs") return json({ items: [] });
      if (url.pathname === "/api/publications") return json({ items: [publication], total: 1 });
      if (url.pathname === "/api/history/coverage") return json(coverage);
      if (url.pathname === "/api/history/publications/10") return json({ norm_codes: publication.norm_codes, total: 0, items: [] });
      return json({});
    });
    vi.stubGlobal("fetch", fetcher);
    try {
      render(<Portal />);
      await user.click(screen.getByRole("button", { name: "Catálogo NOM" }));
      await user.click(await screen.findByRole("button", { name: "Ver historial relacionado" }));
      expect(await screen.findByText("No hay publicaciones relacionadas en el archivo guardado.")).toBeVisible();
      expect(fetcher.mock.calls.some(([path]) => /\/versions\/|\/publications\/10\?include/.test(path))).toBe(false);
      await user.click(screen.getByRole("button", { name: "Cerrar lectura" }));
      await user.click(screen.getByRole("button", { name: "Buscar publicaciones" }));
      await user.selectOptions(await screen.findByRole("combobox", { name: "Año" }), "2020");
      await user.selectOptions(screen.getByRole("combobox", { name: "Mes" }), "02");
      await user.selectOptions(screen.getByRole("combobox", { name: "Orden cronológico" }), "asc");
      await waitFor(() => expect(fetcher.mock.calls.some(([path]) => path.includes("published_since=2020-02-01") && path.includes("published_until=2020-02-29") && path.includes("direction=asc") && path.includes("page_size=25"))).toBe(true));
      await user.click(screen.getByRole("button", { name: "Catálogo NOM" }));
      await user.click(screen.getByRole("button", { name: "Buscar publicaciones" }));
      expect(screen.getByRole("combobox", { name: "Año" })).toHaveValue("");
    } finally { vi.unstubAllGlobals(); }
  });
});
