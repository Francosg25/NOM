import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "./i18n";
import { TariffReferenceResults } from "./TariffReferenceResults";

const reference = { available: true, document_date: "2026-04-02", retrieved_at: "2026-11-17",
  source_url: "https://www.snice.gob.mx/controlled.docx", source_page: "https://www.snice.gob.mx/",
  base_tariff: "12345678", requested_nico: "01", matches: [{ table: 1, row: 2,
    description: "Producto controlado", qualification: "Únicamente: muestra controlada.",
    heading: "1.- Alcance de prueba", nom_codes: ["NOM-999-SE-2099"], nico_rows: [["01", "Modelo pequeño", "Excepto: uso industrial."]] }],
  saved_norms: [{ id: 7, title: "NOM-999-SE-2099 guardada", codes: ["NOM-999-SE-2099"] }] };

describe("tariff reference results", () => {
  it("keeps dated table relationships distinct from text matches and preserves qualifications and NICO", async () => {
    const user = userEvent.setup();
    const open = vi.fn();
    render(<LanguageProvider><TariffReferenceResults reference={reference} open={open} /></LanguageProvider>);
    const region = screen.getByRole("region", { name: "Referencia por fracción arancelaria" });
    expect(within(region).getByText(/Documento referencial de SNICE con modificaciones hasta/)).toHaveTextContent(/abr.*2026/);
    expect(within(region).getByText("Únicamente: muestra controlada.")).toBeVisible();
    await user.click(within(region).getByText("NICO y descripciones de la tabla"));
    expect(within(region).getByText(/Excepto: uso industrial/)).toBeVisible();
    await user.click(within(region).getByRole("button", { name: /Abrir NOM guardada/ }));
    expect(open).toHaveBeenCalledWith(7);
    expect(within(region).getByRole("link", { name: "Descargar referencia oficial" })).toHaveAttribute("href", reference.source_url);
    expect(within(region).getByText(/La consulta usa los 8 dígitos/)).toBeVisible();
  });

  it("does not interpret absent references or an unavailable index as an exemption", () => {
    const view = render(<LanguageProvider><TariffReferenceResults reference={{ ...reference, matches: [] }} open={vi.fn()} /></LanguageProvider>);
    expect(screen.getByText(/Esto no confirma una exención/)).toBeVisible();
    view.rerender(<LanguageProvider><TariffReferenceResults reference={{ available: false, matches: [], source_page: reference.source_page }} open={vi.fn()} /></LanguageProvider>);
    expect(screen.getByText(/La referencia arancelaria no está disponible/)).toBeVisible();
    expect(screen.queryByText(/Esto no confirma una exención/)).not.toBeInTheDocument();
  });

  it("translates date and refresh status without treating retrieval as current validity", () => {
    history.replaceState({}, "", "/?lang=en");
    render(<LanguageProvider><TariffReferenceResults reference={{ ...reference, refresh_failed: true }} open={vi.fn()} /></LanguageProvider>);
    expect(screen.getByRole("heading", { name: "Relationships in Annex 2.4.1" })).toBeVisible();
    expect(screen.getByText(/The retrieval date does not establish current validity/)).toBeVisible();
    expect(screen.getByText(/The SNICE reference could not be refreshed/)).toBeVisible();
  });
});
