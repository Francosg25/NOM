import { useLanguage } from "./i18n";
import "./ProductLookup.css";

type Row = Record<string, any>;

function qualificationParagraphs(text: string, codes: string[]): string[] {
  const escaped = codes.map((code) => code.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return (escaped.length ? text.split(new RegExp(`(?=${escaped.join("|")})`, "g")) : [text])
    .map((part) => part.trim()).filter(Boolean);
}

export function TariffReferenceResults({ reference, open }: {
  reference: Row; open: (id: number) => void;
}) {
  const { t, format } = useLanguage();
  const matches: Row[] = reference.matches || [];
  const tariff = String(reference.base_tariff || "").replace(/^(\d{4})(\d{2})(\d{2})$/, "$1.$2.$3");
  return <section className="tariff-reference" aria-label={t("Referencia por fracción arancelaria")}>
    <header className="tariff-reference-intro">
      <div className="section-rule">
        <h2>{t("Relaciones en el Anexo 2.4.1")}</h2>
        <span>{t("{count} referencias arancelarias", { count: matches.length })}</span>
      </div>
      <p>{t("La relación fracción–NOM se consulta en las tablas de SNICE, aunque el texto de la norma no contenga ese número.")}</p>
      {reference.available && <>
        <div className="tariff-reference-provenance">
          <p>{t("Documento referencial de SNICE con modificaciones hasta {date}.", { date: format(reference.document_date) })}</p>
          <a href={reference.source_url} target="_blank" rel="noreferrer">{t("Descargar referencia oficial")}</a>
        </div>
        <p className="tariff-reference-note">{t("La fecha de consulta no acredita vigencia. Revisa las reformas posteriores, las acotaciones y el campo de aplicación.")}</p>
      </>}
    </header>
    {reference.available ? <>
      {reference.requested_nico && <p className="tariff-reference-note">{t("La consulta usa los 8 dígitos de la fracción base. El NICO se muestra como referencia y no decide aplicabilidad.")}</p>}
      {reference.refresh_failed && <p className="tariff-reference-note" role="status">{t("No se pudo actualizar la referencia de SNICE; se conserva la última copia válida con su fecha documental.")}</p>}
      {matches.length ? <div className="product-match-list tariff-reference-list">{matches.map((row, index) => {
        const codes: string[] = row.nom_codes || [];
        const savedNorms = (reference.saved_norms || []).filter((norm: Row) => norm.codes.some((code: string) => codes.includes(code)));
        return <article className="product-match tariff-reference-card" key={`${row.table}:${row.row}:${index}`}>
          <header className="tariff-card-heading">
            <div className="article-kicker"><span>SNICE · {t("Anexo 2.4.1")}</span><span>{tariff}</span></div>
            <h3 lang="es">{row.description}</h3>
            {codes.length > 0 ? <ul className="tariff-nom-codes" aria-label={t("NOM referenciadas")}>
              {codes.map((code) => <li key={code} lang="es">{code}</li>)}
            </ul> : <p>{t("Consultar acotación")}</p>}
          </header>
          <div className="tariff-qualification">
            <h4>{t("Acotaciones de la referencia")}</h4>
            {qualificationParagraphs(row.qualification || row.heading || "", codes).map((part, i) => {
              const code = codes.find((item) => part.startsWith(item));
              return <p key={i} lang="es">{code ? <><strong>{code}</strong>{" "}{part.slice(code.length).trimStart()}</> : part}</p>;
            })}
          </div>
          <div className="tariff-reference-details">
            {row.qualification && <details><summary>{t("Numeral y alcance de la referencia")}</summary>
              <div className="tariff-detail-body"><p lang="es">{row.heading}</p></div>
            </details>}
            {row.nico_rows.length > 0 && <details><summary>{t("NICO y descripciones de la tabla")}</summary>
              <div className="tariff-detail-body tariff-nico-scroll" role="region" aria-label={t("NICO y descripciones de la tabla")} tabIndex={0}>
                <table><thead><tr><th scope="col">NICO</th><th scope="col">{t("Descripción en la tabla")}</th><th scope="col">{t("Acotación")}</th></tr></thead>
                  <tbody>{row.nico_rows.map((nico: string[], i: number) => <tr key={i} lang="es"><td>{nico[0]}</td><td>{nico[1]}</td><td>{nico[2] || "—"}</td></tr>)}</tbody>
                </table>
              </div>
            </details>}
          </div>
          {savedNorms.length > 0 && <div className="tariff-saved-norms">
            <h4>{t("NOM disponibles en el catálogo")}</h4>
            <ul>{savedNorms.map((norm: Row) => <li key={norm.id}>
              <button type="button" className="tariff-norm-link" onClick={() => open(norm.id)}>
                <span className="tariff-norm-action">{t("Abrir NOM guardada")}</span>
                <span lang="es">{norm.title}</span>
              </button>
            </li>)}</ul>
          </div>}
        </article>;
      })}</div> : <p className="tariff-reference-note" role="status">{t("La fracción no aparece en esta referencia de importación. Esto no confirma una exención ni que el código sea válido.")}</p>}
    </> : <p className="tariff-reference-note" role="status">{t("La referencia arancelaria no está disponible. Las coincidencias textuales se muestran por separado.")}</p>}
    <footer className="tariff-reference-footer"><a href={reference.source_page} target="_blank" rel="noreferrer">{t("Consultar normativa oficial en SNICE")}</a></footer>
  </section>;
}
