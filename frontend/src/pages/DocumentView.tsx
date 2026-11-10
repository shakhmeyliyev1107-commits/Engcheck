import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { ParseBadge } from "../components/Badges";
import { ErrorNote } from "../components/Layout";
import { useErrorText, useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";

export function DocumentView() {
  const id = Number(useParams().id);
  const { t } = useI18n();
  const errorText = useErrorText();
  const [search, setSearch] = useSearchParams();
  const { data: doc, error } = useLoad(() => api.document(id), [id]);
  const [fileError, setFileError] = useState<string | null>(null);

  if (!doc) return <ErrorNote text={error} />;
  const total = doc.pages.length;
  const page = Math.min(Math.max(Number(search.get("page")) || 1, 1), Math.max(total, 1));
  const tag = search.get("tag");
  const current = doc.pages.find((p) => p.page_no === page);
  const params = doc.params.filter((p) => p.page_no === page);
  const goto = (n: number) => {
    const next = new URLSearchParams(search);
    next.set("page", String(n));
    setSearch(next, { replace: true });
  };
  // Asl fayl o'zgartirilmagan holda ochiladi (token sarlavhada yuborilgani uchun blob orqali).
  const openOriginal = async () => {
    setFileError(null);
    try {
      const url = URL.createObjectURL(await api.fileBlob(id));
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (err) {
      setFileError(errorText(err));
    }
  };

  return (
    <>
      <div className="crumbs"><Link to={`/projects/${doc.project_id}`}>{t("nav.dashboard")}</Link> / {t("project.documents")} /</div>
      <h1 data-testid="doc-title">{doc.doc_number ?? doc.filename}</h1>
      <div className="row" style={{ margin: "8px 0 14px" }}>
        <span className="badge">{t(`doctype.${doc.doc_type}` as Key)}</span>
        <span className="badge">{t(`discipline.${doc.discipline}` as Key)}</span>
        {doc.revision && <span className="badge">Rev {doc.revision}</span>}
        <ParseBadge value={doc.parse_status} />
        <button onClick={openOriginal} data-testid="open-original">{t("doc.openOriginal")}</button>
        <Link to={`/projects/${doc.project_id}/findings?document_id=${doc.id}`} data-testid="doc-findings">{t("doc.findings")}</Link>
      </div>
      <p className="muted">{doc.filename}</p>
      {doc.parse_message && <p className="warn">{doc.parse_message}</p>}
      {doc.superseded && <p className="warn">{t("doc.superseded")}</p>}
      {doc.skipped_tags.length > 0 && (
        <p className="warn" data-testid="skipped-tags">{t("doc.skippedTags")}: {doc.skipped_tags.join(", ")}</p>
      )}
      <ErrorNote text={fileError} />

      {total > 0 && (
        <>
          <div className="row">
            <button disabled={page <= 1} onClick={() => goto(page - 1)} aria-label="‹">‹</button>
            <span data-testid="page-indicator">{t("doc.pageOf", { page, total })}</span>
            <button disabled={page >= total} onClick={() => goto(page + 1)} aria-label="›">›</button>
          </div>
          <h2>{t("doc.params")}</h2>
          {params.length === 0 ? <p className="muted">{t("doc.noParams")}</p> : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>{t("doc.tag")}</th><th>{t("doc.param")}</th><th>{t("doc.value")}</th><th>{t("doc.si")}</th><th>{t("doc.location")}</th><th>{t("findings.confidence")}</th></tr>
                </thead>
                <tbody>
                  {params.map((p, i) => (
                    <tr key={i} className={p.tag === tag ? "hl" : ""} data-testid={p.tag === tag ? "param-row-hl" : "param-row"}>
                      <td>{p.tag}</td><td>{p.param_name}</td><td>{p.raw_value}</td>
                      <td>{p.si_value === null ? "—" : `${p.si_value} ${p.si_unit ?? ""}`}</td>
                      <td>{p.location}</td><td>{t(`confidence.${p.confidence}` as Key)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {doc.unmapped_headers.length > 0 && (
            <p className="muted" style={{ marginTop: 10 }}>{t("doc.unmapped")}: {doc.unmapped_headers.join(", ")}</p>
          )}
          <h2>{t("doc.extractedText")}</h2>
          <pre className="doc-text" data-testid="doc-text">{current?.text ?? ""}</pre>
        </>
      )}
    </>
  );
}
