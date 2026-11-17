import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Portal from "./Portal";

vi.mock("./apiAccess", () => ({
  authConfig: async () => ({ mode: "portal", app_service: false }),
  restoreSession: async () => "", accessToken: async () => "", signIn: vi.fn(), signOut: vi.fn(),
}));
const json = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
const publication = { id: 7, title: "NOM-TEST-001-2020 - Copia controlada", kind: "norma_definitiva",
  source_name: "SIDOF", official_id: "DOF:7", published_on: "2020-01-01", url: "https://sidof.segob.gob.mx/" };

describe("bulletin improvements integrated with navigation and reading", () => {
  it("rechecks a summary selection when the user clicks its current card again", async () => {
    const user = userEvent.setup();
    localStorage.setItem("nom-visit-v1:portal:false", JSON.stringify({ version_id: 10, content_hash: "old", visited_at: "2026-11-15T12:00:00Z" }));
    let latest = false;
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      const url = new URL(input, "http://localhost");
      if (url.pathname === "/api/me") return json({ role: "consulta" });
      if (url.pathname === "/api/dashboard") return json({ sources: [] });
      if (url.pathname === "/api/jobs") return json({ items: [] });
      if (url.pathname === "/api/bulletin/updates") return json({ new_publications: 1, changed_publications: 0, new_catalog: 0,
        cursor: { version_id: 20, content_hash: "new", visited_at: "2026-11-17T12:00:00Z" } });
      if (url.pathname === "/api/publications") return json({ total: 1, items: [{ ...publication,
        title: url.searchParams.has("update_type") ? latest ? "Fresh saved record" : "Previously saved record" : "All records" }] });
      return json({});
    }));
    try {
      render(<Portal />);
      const card = await screen.findByRole("button", { name: /Publicaciones incorporadas/ });
      await user.click(card);
      await screen.findByRole("button", { name: "Previously saved record" });
      latest = true;
      await user.click(card);
      expect(await screen.findByRole("button", { name: "Fresh saved record" })).toBeVisible();
    } finally { vi.unstubAllGlobals(); }
  });

  it("opens the summary's matching catalogue records and retains its filter through hash navigation", async () => {
    const user = userEvent.setup();
    localStorage.setItem("nom-visit-v1:portal:false", JSON.stringify({ version_id: 10, content_hash: "old", visited_at: "2026-11-15T12:00:00Z" }));
    const fetcher = vi.fn(async (input: string) => {
      const url = new URL(input, "http://localhost");
      if (url.pathname === "/api/me") return json({ role: "consulta" });
      if (url.pathname === "/api/dashboard") return json({ sources: [] });
      if (url.pathname === "/api/jobs") return json({ items: [] });
      if (url.pathname === "/api/bulletin/updates") return json({ new_publications: 1, changed_publications: 0, new_catalog: 1,
        cursor: { version_id: 20, content_hash: "new", visited_at: "2026-11-17T12:00:00Z" } });
      if (url.pathname === "/api/publications") {
        const catalogue = url.searchParams.get("source_kind") === "platiica_catalog";
        const selected = url.searchParams.get("update_type") === "new";
        return json({ total: 1, items: [{ ...publication,
          title: catalogue ? selected ? "Ficha incorporada recientemente" : "Catálogo completo" : "Boletín general" }] });
      }
      return json({});
    });
    vi.stubGlobal("fetch", fetcher);
    try {
      render(<Portal />);
      await user.click(await screen.findByRole("button", { name: /Fichas incorporadas al catálogo/ }));
      expect(await screen.findByRole("button", { name: "Ficha incorporada recientemente" })).toBeVisible();
      await act(async () => { window.dispatchEvent(new HashChangeEvent("hashchange")); });
      expect(screen.getByRole("button", { name: /Quitar selección del resumen/ })).toBeVisible();
      const requested = fetcher.mock.calls.map(([input]) => new URL(input, "http://localhost"));
      expect(requested.some((url) => url.pathname === "/api/publications" &&
        url.searchParams.get("source_kind") === "platiica_catalog" && url.searchParams.get("after_version_id") === "10" &&
        url.searchParams.get("update_type") === "new")).toBe(true);
      await user.click(screen.getByRole("button", { name: /Quitar selección del resumen/ }));
      expect(await screen.findByRole("button", { name: "Catálogo completo" })).toBeVisible();
    } finally { vi.unstubAllGlobals(); }
  });

  it("shows publication facts and fetches a comparison only after the reader requests it", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn(async (input: string) => {
      const url = new URL(input, "http://localhost");
      if (url.pathname === "/api/me") return json({ role: "consulta" });
      if (url.pathname === "/api/dashboard") return json({ sources: [] });
      if (url.pathname === "/api/jobs") return json({ items: [] });
      if (url.pathname === "/api/publications") return json({ total: 1, items: [publication] });
      if (url.pathname === "/api/publications/7") return json({ ...publication, norm_status: null,
        effective_on: "2026-12-01", effective_verified: false,
        versions: [{ id: 2, sequence: 2, captured_at: "2026-11-17" }, { id: 1, sequence: 1, captured_at: "2026-11-15" }] });
      if (/\/api\/versions\/\d+\/reading/.test(url.pathname)) return json({ format: "structured", blocks: [
        { type: "paragraph", inlines: [{ type: "text", text: "Texto controlado para lectura." }] },
      ] });
      if (url.pathname.endsWith("/comparison")) return json({ classification: "unchanged", items: [], total: 0 });
      return json({});
    });
    vi.stubGlobal("fetch", fetcher);
    try {
      render(<Portal />);
      await user.click(await screen.findByRole("button", { name: publication.title }));
      await screen.findByText("Texto controlado para lectura.");
      const facts = screen.getByRole("region", { name: "Ficha de la publicación" });
      expect(within(facts).getByText("No informado por la fuente")).toBeVisible();
      expect(within(facts).queryByText(/dic.*2026/)).not.toBeInTheDocument();
      expect(fetcher.mock.calls.some(([path]) => path.includes("/comparison"))).toBe(false);
      await user.click(screen.getByRole("button", { name: "Comparar versiones" }));
      expect(await screen.findByText("El texto guardado es idéntico en ambas copias.")).toBeVisible();
      expect(fetcher.mock.calls.some(([path]) => path.includes("from_version_id=1&to_version_id=2"))).toBe(true);
      await user.selectOptions(screen.getByRole("combobox", { name: "Versión del documento" }), "1");
      await waitFor(() => expect(screen.getByText("Esta es la primera versión guardada.")).toBeVisible());
    } finally { vi.unstubAllGlobals(); }
  });
});
