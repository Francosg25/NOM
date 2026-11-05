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
      await user.click(screen.getByRole("button", { name: "SIDOF status" }));
      expect(screen.getByText("Saved publications")).toBeVisible();
      expect(screen.getByText("Last complete period check")).toBeVisible();
      expect(screen.getByText("Next automatic check")).toBeVisible();
      await waitFor(() => expect(document.documentElement.lang).toBe("en"));
      expect(fetch.mock.calls.some(([url]) => url.includes("source_kind=sidof"))).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
