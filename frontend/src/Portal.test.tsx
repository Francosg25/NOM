import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Portal, { Reader } from "./Portal";
import { LanguageProvider } from "./i18n";

vi.mock("./apiAccess", () => ({
  authConfig: async () => ({ mode: "portal", app_service: false }),
  restoreSession: async () => "",
  accessToken: async () => "",
  signIn: vi.fn(), signOut: vi.fn(),
}));

describe("document reader", () => {
  it("contains keyboard focus, closes with Escape and returns focus to its opener", async () => {
    const user = userEvent.setup();
    const close = vi.fn();
    const opener = document.createElement("button");
    opener.textContent = "Open";
    document.body.append(opener);
    opener.focus();
    const view = render(<LanguageProvider><Reader title="Controlled document" close={close}>
      <a href="https://sidof.segob.gob.mx/">Original</a>
    </Reader></LanguageProvider>);
    const dismiss = screen.getByRole("button", { name: "Cerrar lectura" });
    expect(dismiss).toHaveFocus();
    await user.tab({ shift: true });
    expect(screen.getByRole("link", { name: "Original" })).toHaveFocus();
    await user.tab();
    expect(dismiss).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(close).toHaveBeenCalledOnce();
    view.unmount();
    expect(opener).toHaveFocus();
    opener.remove();
  });
});

describe("public portal", () => {
  it("keeps valid downloads visible while explaining partial coverage in both languages", async () => {
    const user = userEvent.setup();
    const fetch = vi.fn(async (input: string) => {
      const url = new URL(input, "http://localhost");
      let data: unknown = {};
      if (url.pathname === "/api/me") data = { role: "consulta" };
      if (url.pathname === "/api/dashboard") data = {
        monitor_enabled: true, scheduler_enabled: true,
        sources: [{ id: 1, kind: "sidof", name: "SIDOF", active: true,
          urls: ["https://sidof.segob.gob.mx/dof/sidof"], publication_count: 1,
          last_error: "2026-10-01: HTTP 404", last_download_at: "2026-10-02T15:00:00Z",
          last_full_review_at: null, pending_dates: ["2026-10-01"], frequency_hours: 1,
          schedule_enabled: true, next_due_at: "2026-10-02T16:00:00Z" }],
      };
      if (url.pathname === "/api/publications") data = { total: 1, items: [{ id: 1,
        title: "Controlled NOM", source_name: "SIDOF", published_on: "2026-10-02",
        excerpt: "Controlled sample; no legal determination", kind: "proyecto" }] };
      if (url.pathname === "/api/jobs") data = { items: [] };
      return new Response(JSON.stringify(data), { status: 200 });
    });
    vi.stubGlobal("fetch", fetch);
    try {
      render(<Portal />);
      expect(await screen.findByRole("button", { name: "Controlled NOM" })).toBeVisible();
      expect(screen.getByText("Hay fechas pendientes de verificar.")).toBeVisible();
      await user.click(screen.getByRole("button", { name: "English" }));
      expect(screen.getByText("Some dates still need checking.")).toBeVisible();
      expect(localStorage.getItem("nom-language")).toBe("en");
      await user.click(screen.getByRole("button", { name: "Source status" }));
      expect(screen.getByText("Saved publications")).toBeVisible();
      expect(screen.getByText("Last complete period check")).toBeVisible();
      expect(screen.getByText("Next automatic check")).toBeVisible();
      await waitFor(() => expect(document.documentElement.lang).toBe("en"));
      expect(fetch.mock.calls.some(([url]) => url.includes("source_kind=sidof"))).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("shows imported current and historical PLATIICA NOM records in a dedicated catalogue", async () => {
    const user = userEvent.setup();
    const fetch = vi.fn(async (input: string) => {
      const url = new URL(input, "http://localhost");
      let data: unknown = {};
      if (url.pathname === "/api/me") data = { role: "consulta" };
      if (url.pathname === "/api/dashboard") data = {
        monitor_enabled: true,
        scheduler_enabled: true,
        sources: [
          { id: 1, kind: "sidof", name: "SIDOF", active: true, urls: [] },
          { id: 2, kind: "platiica_catalog", name: "PLATIICA", active: true,
            urls: [], pending_items: 0 },
        ],
      };
      if (url.pathname === "/api/publications") {
        data = url.searchParams.get("source_kind") === "platiica_catalog"
          ? {
              total: 1,
              items: [{
                id: 22,
                title: "NOM-TEST-001-2020 - Norma de prueba histórica",
                official_id: "PLATIICA:NOM-TEST-001-2020",
                source_name: "PLATIICA",
                published_on: "2020-01-01",
                detected_at: "2026-11-06T12:00:00Z",
                kind: "norma_no_vigente",
                norm_status: "Cancelada",
                product_scope: "Productos de prueba",
                excerpt: "Ficha oficial de prueba",
              }],
            }
          : { total: 0, items: [] };
      }
      if (url.pathname === "/api/jobs") data = { items: [] };
      return new Response(JSON.stringify(data), { status: 200 });
    });
    vi.stubGlobal("fetch", fetch);
    try {
      render(<Portal />);
      await user.click(await screen.findByRole("button", { name: "Catálogo NOM" }));
      expect(await screen.findByRole("button", {
        name: "NOM-TEST-001-2020 - Norma de prueba histórica",
      })).toBeVisible();
      expect(screen.getByText("Estado oficial: Cancelada")).toBeVisible();
      expect(screen.getByText("Producto/servicio en PLATIICA: Productos de prueba")).toBeVisible();
      expect(fetch.mock.calls.some(([input]) => {
        const url = new URL(input, "http://localhost");
        return url.pathname === "/api/publications" &&
          url.searchParams.get("source_kind") === "platiica_catalog";
      })).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("keeps the empty catalogue status link available while another source is running", async () => {
    const user = userEvent.setup();
    const fetch = vi.fn(async (input: string) => {
      const url = new URL(input, "http://localhost");
      let data: unknown = {};
      if (url.pathname === "/api/me") data = { role: "consulta" };
      if (url.pathname === "/api/dashboard") data = {
        monitor_enabled: true,
        scheduler_enabled: true,
        sources: [
          { id: 1, kind: "sidof", name: "SIDOF", active: true,
            urls: ["https://sidof.segob.gob.mx/dof/sidof"] },
          { id: 2, kind: "platiica_catalog", name: "PLATIICA", active: true,
            urls: ["https://platiica.economia.gob.mx/normalizacion/wp-sitemap.xml"],
            latest_check_status: "running",
            latest_check_heartbeat_at: "2026-01-01T00:00:00Z",
            latest_check_reviewed_count: 40,
            catalog_discovered_count: 823,
            catalog_unchanged_count: 12,
            pending_items: 771 },
        ],
      };
      if (url.pathname === "/api/publications") data = { total: 0, items: [] };
      if (url.pathname === "/api/jobs") {
        data = { items: [{ id: "running-job", source_id: 1, status: "running" }] };
      }
      return new Response(JSON.stringify(data), { status: 200 });
    });
    vi.stubGlobal("fetch", fetch);
    try {
      render(<Portal />);
      await user.click(await screen.findByRole("button", { name: "Catálogo NOM" }));
      const statusLink = await screen.findByRole("button", { name: "Ver estado de PLATIICA" });
      expect(statusLink).toBeEnabled();
      await user.click(statusLink);
      expect(await screen.findByRole("heading", { name: /Estado de fuentes/ })).toBeVisible();
      expect(screen.getByText("Proceso sin señal reciente")).toBeVisible();
      expect(screen.getByText(
        "40 revisadas de 823 fichas detectadas; 771 pendientes y 12 sin cambios.",
      )).toBeVisible();
      expect(screen.getByText(
        "El proceso no ha enviado una señal reciente. Reinicia el portal para recuperar la consulta interrumpida; el trabajo pendiente se conserva.",
      )).toBeVisible();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("searches saved NOM publications by Mexican tariff code or product description", async () => {
    const user = userEvent.setup();
    const fetch = vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, "http://localhost");
      let data: unknown = {};
      if (url.pathname === "/api/me") data = { role: "consulta" };
      if (url.pathname === "/api/dashboard") data = { sources: [] };
      if (url.pathname === "/api/publications") data = { total: 0, items: [] };
      if (url.pathname === "/api/jobs") data = { items: [] };
      if (url.pathname === "/api/product-search") {
        const body = JSON.parse(String(init?.body));
        data = {
          mode: body.mode,
          value: body.value,
          total: 1,
          searched_publications: 12,
          catalog: {
            records: 5,
            current_norms: 4,
            unresolved_status: 0,
            missing_product_scope: 0,
            synchronized: true,
            last_job_status: "succeeded",
            last_checked_at: "2026-01-03T00:00:00Z",
            pending_pages: 0,
          },
          truncated: false,
          disclaimer: "Coincidencias textuales en publicaciones SIDOF guardadas. No determinan si una NOM aplica al producto ni sustituyen la clasificación arancelaria o revisión de la disposición oficial.",
          results: [{
            publication: {
              id: 8, title: "Publicación controlada NOM", official_id: "CONTROLLED-8",
              published_on: "2026-01-02", kind: "norma_definitiva", source_name: "SIDOF",
            },
            match: {
              type: body.mode === "fraccion" ? "fraccion_exacta" : "descripcion",
              matched_terms: [body.value], evidence: "Evidencia textual controlada.",
            },
          }],
        };
      }
      return new Response(JSON.stringify(data), { status: 200 });
    });
    vi.stubGlobal("fetch", fetch);
    try {
      render(<Portal />);
      await user.click(await screen.findByRole("button", { name: "Consultar producto" }));
      await user.type(screen.getByLabelText("Fracción arancelaria / NICO"), "85011001");
      await user.click(screen.getByRole("button", { name: "Buscar posibles coincidencias" }));
      expect(await screen.findByRole("button", { name: "Publicación controlada NOM" })).toBeVisible();
      expect(screen.getByText("Evidencia textual controlada.")).toBeVisible();
      expect(screen.getByText("Se revisaron 12 documentos de NOM vigentes y publicaciones SIDOF.")).toBeVisible();
      expect(screen.getByText("Catálogo PLATIICA: 4 NOM vigentes entre 5 fichas guardadas.")).toBeVisible();
      expect(fetch.mock.calls.some(([url]) => url.endsWith("/api/product-search"))).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("lets administrators save a tariff code for ongoing monitoring and review suggestions", async () => {
    const user = userEvent.setup();
    const fetch = vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, "http://localhost");
      let data: unknown = {};
      if (url.pathname === "/api/me") data = { role: "administrador" };
      if (url.pathname === "/api/dashboard") data = { sources: [] };
      if (url.pathname === "/api/publications") data = { total: 0, items: [] };
      if (url.pathname === "/api/jobs") data = { items: [] };
      if (url.pathname === "/api/catalog" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        data = {
          ...body, id: 21, missing_fields: [],
        };
      }
      if (url.pathname === "/api/catalog" && init?.method !== "POST") data = { items: [] };
      if (url.pathname === "/api/alerts") {
        data = {
          items: [{
            id: 31, publication_id: 8, publication_title: "NOM para revisión",
            reason: "Coincidencia de fracción base", status: "pendiente", decision: "propuesta",
          }],
        };
      }
      return new Response(JSON.stringify(data), { status: 200 });
    });
    vi.stubGlobal("fetch", fetch);
    try {
      render(<Portal />);
      await user.click(await screen.findByRole("button", { name: "Consultar producto" }));
      await user.type(screen.getByLabelText("Fracción arancelaria / NICO"), "8501.10.01 12");
      await user.click(screen.getByRole("button", { name: "Guardar para seguimiento" }));
      expect(await screen.findByText("NOM para revisión")).toBeVisible();
      const saved = fetch.mock.calls.find(
        ([url, init]) => url.endsWith("/api/catalog") && init?.method === "POST",
      );
      expect(saved).toBeDefined();
      const body = JSON.parse(String(saved?.[1]?.body));
      expect(body.tariff_code).toBe("85011001");
      expect(body.nico).toBe("12");
      expect(body.active).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
