import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Portal from "./Portal";

vi.mock("./apiAccess", () => ({
  authConfig: async () => ({ mode: "portal", app_service: false }),
  restoreSession: async () => "", accessToken: async () => "",
  signIn: vi.fn(), signOut: vi.fn(),
}));
const response = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
const list = (title: string) => ({ total: 1, items: [{ id: 1, title, kind: "norma_definitiva", source_name: "SIDOF" }] });

describe("portal navigation with a slow API", () => {
  it("retries a failed identity lookup without requiring a page reload", async () => {
    const user = userEvent.setup();
    let identities = 0;
    vi.stubGlobal("fetch", vi.fn((input: string) => {
      const url = new URL(input, "http://localhost");
      if (url.pathname === "/api/me") {
        return Promise.resolve(++identities === 1
          ? new Response(JSON.stringify({ detail: "Identity temporarily unavailable" }), { status: 503 })
          : response({ role: "administrador", auth_mode: "development" }));
      }
      if (url.pathname === "/api/dashboard") return Promise.resolve(response({ sources: [] }));
      if (url.pathname === "/api/jobs") return Promise.resolve(response({ items: [] }));
      return Promise.resolve(response(list("Saved publication")));
    }));
    try {
      render(<Portal />);
      await screen.findByText("Identity temporarily unavailable");
      await user.click(screen.getByRole("button", { name: "Volver a intentar" }));
      expect(await screen.findByText("EDICIÓN LOCAL")).toBeVisible();
      expect(identities).toBe(2);
      expect(screen.queryByText("Identity temporarily unavailable")).not.toBeInTheDocument();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("displays publications without waiting for identity, overview or jobs", async () => {
    const fetcher = vi.fn((input: string) => {
      const url = new URL(input, "http://localhost");
      if (url.pathname === "/api/publications") return Promise.resolve(response(list("Available publication")));
      return new Promise<Response>(() => {});
    });
    vi.stubGlobal("fetch", fetcher);
    try {
      render(<Portal />);
      expect(await screen.findByRole("button", { name: "Available publication" })).toBeVisible();
      expect(screen.queryByText("Cargando…")).not.toBeInTheDocument();
      expect(fetcher.mock.calls.some(([path]) => path === "/api/dashboard")).toBe(true);
      expect(fetcher.mock.calls.some(([path]) => path === "/api/me")).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("reuses the catalogue prefetch and shows saved news while revalidating", async () => {
    const user = userEvent.setup();
    let finishCatalogue!: (value: Response) => void;
    let finishNews!: (value: Response) => void;
    let newsCalls = 0;
    const fetcher = vi.fn((input: string) => {
      const url = new URL(input, "http://localhost");
      if (url.pathname === "/api/me") return Promise.resolve(response({ role: "consulta" }));
      if (url.pathname === "/api/dashboard") return Promise.resolve(response({ sources: [] }));
      if (url.pathname === "/api/jobs") return Promise.resolve(response({ items: [] }));
      if (url.pathname === "/api/publications") {
        if (url.searchParams.get("source_kind") === "platiica_catalog") {
          return new Promise<Response>((resolve) => { finishCatalogue = resolve; });
        }
        newsCalls++;
        return newsCalls === 1 ? Promise.resolve(response(list("Saved news")))
          : new Promise<Response>((resolve) => { finishNews = resolve; });
      }
      return Promise.resolve(response({}));
    });
    vi.stubGlobal("fetch", fetcher);
    try {
      render(<Portal />);
      await screen.findByRole("button", { name: "Saved news" });
      await waitFor(() => expect(finishCatalogue).toBeTypeOf("function"));
      await user.click(screen.getByRole("button", { name: "Catálogo NOM" }));
      expect(screen.queryByRole("button", { name: "Saved news" })).not.toBeInTheDocument();
      await act(async () => finishCatalogue(response(list("Catalogue entry"))));
      expect(await screen.findByRole("button", { name: "Catalogue entry" })).toBeVisible();
      await user.click(screen.getByRole("button", { name: "Novedades" }));
      expect(screen.getByRole("button", { name: "Saved news" })).toBeVisible();
      expect(screen.queryByRole("button", { name: "Catalogue entry" })).not.toBeInTheDocument();
      await waitFor(() => expect(finishNews).toBeTypeOf("function"));
      expect(fetcher.mock.calls.filter(([path]) => path === "/api/me")).toHaveLength(1);
      expect(fetcher.mock.calls.filter(([path]) => path === "/api/dashboard")).toHaveLength(1);
      expect(fetcher.mock.calls.filter(([path]) => path.startsWith("/api/jobs?"))).toHaveLength(1);
      expect(fetcher.mock.calls.filter(([path]) => path.includes("source_kind=platiica_catalog"))).toHaveLength(1);
      await act(async () => finishNews(response(list("Newly published news"))));
      expect(await screen.findByRole("button", { name: "Newly published news" })).toBeVisible();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
