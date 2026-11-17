import { useLanguage } from "./i18n";

type Row = Record<string, any>;
export function TariffReferenceResults({ reference, open }: {
  reference: Row; open: (id: number) => void;
}) {
  const { t, format } = useLanguage();
  const matches: Row[] = reference.matches || [];
  return <section className="tariff-reference" aria-label={t("Referencia por fracción arancelaria")}>
    <div className="section-rule">
      <h2>{t("Relaciones en el Anexo 2.4.1")}</h2>
      <span>{t("{count} referencias arancelarias", { count: matches.length })}</span>
    </div>
    <p>{t("La relación fracción–NOM se consulta en las tablas de SNICE, aunque el texto de la norma no contenga ese número.")}</p>
    {reference.available ? <>
      <p>{t("Documento referencial de SNICE con modificaciones hasta {date}.", { date: format(reference.document_date) })}
        {" "}<a href={reference.source_url} target="_blank" rel="noreferrer">{t("Descargar referencia oficial")}</a></p>
      <p>{t("La fecha de consulta no acredita vigencia. Revisa las reformas posteriores, las acotaciones y el campo de aplicación.")}</p>
      {reference.requested_nico && <p>{t("La consulta usa los 8 dígitos de la fracción base. El NICO se muestra como referencia y no decide aplicabilidad.")}</p>}
      {reference.refresh_failed && <p role="status">{t("No se pudo actualizar la referencia de SNICE; se conserva la última copia válida con su fecha documental.")}</p>}
      {matches.length ? <div className="product-match-list">{matches.map((row, index) => <article className="product-match" key={`${row.table}:${row.row}:${index}`}>
        <div className="article-kicker"><span>SNICE · {t("Anexo 2.4.1")}</span><span>{reference.base_tariff}</span></div>
        <h3 lang="es">{row.description}</h3>
        <p lang="es"><strong>{row.nom_codes.join(" · ") || t("Consultar acotación")}</strong></p>
        <p className="article-excerpt" lang="es">{row.qualification || row.heading}</p>
        {row.qualification && <details><summary>{t("Numeral y alcance de la referencia")}</summary><p lang="es">{row.heading}</p></details>}
        {row.nico_rows.length > 0 && <details><summary>{t("NICO y descripciones de la tabla")}</summary>
          {row.nico_rows.map((nico: string[], i: number) => <p key={i} lang="es"><strong>{nico[0]}</strong> · {nico[1]} {nico[2]}</p>)}
        </details>}
        {(reference.saved_norms || []).filter((norm: Row) => norm.codes.some((code: string) => row.nom_codes.includes(code)))
          .map((norm: Row) => <p key={norm.id}><button type="button" className="text-button" onClick={() => open(norm.id)}>{t("Abrir NOM guardada")}: {norm.title}</button></p>)}
      </article>)}</div> : <p role="status">{t("La fracción no aparece en esta referencia de importación. Esto no confirma una exención ni que el código sea válido.")}</p>}
    </> : <p role="status">{t("La referencia arancelaria no está disponible. Las coincidencias textuales se muestran por separado.")}</p>}
    <p><a href={reference.source_page} target="_blank" rel="noreferrer">{t("Consultar normativa oficial en SNICE")}</a></p>
  </section>;
}
