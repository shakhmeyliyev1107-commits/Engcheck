import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { SeverityBadge, StatusBadge } from "../components/Badges";
import { ErrorNote } from "../components/Layout";
import { useErrorText, useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { can, useSession } from "../session";
import { sourceRef } from "./Kb";

// Holat bo'yicha mumkin bo'lgan amallar (xizmatdagi o'tishlar jadvali bilan bir xil).
const ACTIONS: Record<string, string[]> = {
  new: ["review", "confirm", "reject"],
  reviewed: ["confirm", "reject"],
  confirmed: ["mark_fixed", "reject"],
  rejected: ["confirm"],
  fixed: [],
};

export function FindingDetailPage() {
  const id = Number(useParams().id);
  const { t, locale } = useI18n();
  const { user } = useSession();
  const errorText = useErrorText();
  const loaded = useLoad(() => api.finding(id), [id]);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [asking, setAsking] = useState(false);
  const [lesson, setLesson] = useState("");
  const [lessonSent, setLessonSent] = useState(false);
  const f = loaded.data;

  const act = async (action: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.act(id, action, comment);
      setComment("");
      loaded.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const guard = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      loaded.reload();
    } catch (err) {
      setError(errorText(err));
    }
  };
  const askAi = async () => {
    setAsking(true);
    await guard(() => api.requestAiNote(id));
    setAsking(false);
  };

  if (!f) return <ErrorNote text={loaded.error} />;
  const fmt = (iso: string) => new Date(iso + "Z").toLocaleString(locale === "uz" ? "uz-UZ" : locale);
  return (
    <>
      <div className="crumbs">
        <Link to={`/projects/${f.project_id}`}>{t("nav.dashboard")}</Link> / <Link to={`/projects/${f.project_id}/findings`}>{t("nav.findings")}</Link> /
      </div>
      <h1 data-testid="finding-title">{f.description}</h1>
      <div className="row" style={{ margin: "8px 0 16px" }}>
        <SeverityBadge value={f.severity} />
        <StatusBadge value={f.status} />
        <span className="badge">{f.rule} — {f.rule_title}</span>
        {f.source_type === "ai" && <span className="ai-label">{t("ai.unconfirmed")}</span>}
      </div>
      <div className="grid2">
        <div className="panel">
          <dl className="kv">
            <dt>{t("finding.rationale")}</dt><dd>{f.rationale}</dd>
            <dt>{t("finding.source")}</dt><dd>{f.source}<br /><small className="muted">{t(f.source_type === "ai" ? "ai.sourceAi" : "finding.sourceRule")}</small></dd>
            <dt>{t("findings.confidence")}</dt><dd>{t(`confidence.${f.confidence}` as Key)}</dd>
            <dt>{t("finding.recommendation")}</dt><dd>{f.recommendation}</dd>
          </dl>
          <p className="note" style={{ marginBottom: 0 }}>{t("finding.notApplied")}</p>
        </div>
        <div className="panel">
          <strong>{t("finding.decision")}</strong>
          {can(user, "decide") ? (
            ACTIONS[f.status].length > 0 && (
              <>
                <label className="field" style={{ marginTop: 8 }}>
                  {t("finding.comment")}
                  <textarea value={comment} onChange={(e) => setComment(e.target.value)} data-testid="comment" />
                  <small>{t("finding.commentHint")}</small>
                </label>
                <div className="row" style={{ marginTop: 10 }}>
                  {ACTIONS[f.status].map((a) => (
                    <button key={a} className={a === "confirm" || a === "mark_fixed" ? "primary" : a === "reject" ? "danger" : ""}
                            disabled={busy} onClick={() => act(a)} data-testid={`action-${a}`}>
                      {t(`action.${a}` as Key)}
                    </button>
                  ))}
                </div>
              </>
            )
          ) : (
            <p className="muted" data-testid="view-only">{t("finding.viewOnly")}</p>
          )}
          <ErrorNote text={error} />
          <h2>{t("finding.history")}</h2>
          {f.actions.length === 0 && <p className="muted">{t("finding.noHistory")}</p>}
          {f.actions.map((a, i) => (
            <p key={i} style={{ margin: "6px 0" }} data-testid="history-row">
              <strong>{t(`action.${a.action}` as Key)}</strong> — {a.user ?? "—"}, {fmt(a.created_at)}
              {a.comment && <><br /><span className="muted">{a.comment}</span></>}
            </p>
          ))}
        </div>
      </div>
      <div className="row spread">
        <h2>{t("ai.notes")}</h2>
        {can(user, "review") && <button onClick={askAi} disabled={asking} data-testid="ask-ai">{asking ? t("ai.requesting") : t("ai.requestNote")}</button>}
      </div>
      {f.ai_notes.length === 0 && <p className="muted">{t("ai.noNotes")}</p>}
      {f.ai_notes.map((n) => (
        <div className="ai-box" key={n.id} data-testid="ai-note">
          <span className="ai-label">{t("ai.unconfirmed")}</span>{" "}
          <span className="badge" data-testid="ai-note-status">{t(`ai.note.${n.status}` as Key)}</span>{" "}
          <small className="muted">{n.provider} · {n.model} · {t(n.ai_mode === "local" ? "ai.local" : "ai.cloud")} · {fmt(n.created_at)}</small>
          <p style={{ whiteSpace: "pre-wrap" }}>{n.text}</p>
          {n.assumptions.length > 0 && (
            <>
              <strong>{t("ai.assumptions")}</strong>
              <ul>{n.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </>
          )}
          <strong>{t("ai.citations")}</strong>
          {n.citations.length === 0 && <p className="muted">{t("ai.noCitations")}</p>}
          {n.citations.map((c) => (
            <div className="cite" key={c.key} data-testid="ai-citation">
              <strong>[{c.key}] {sourceRef(c)}</strong>, {t("kb.page", { page: c.page_no })}{" "}
              {c.status !== "active" && <span className="badge parse-error">{t(`kb.status.${c.status}` as Key)}</span>}
              <div className="muted">{c.excerpt}</div>
            </div>
          ))}
          {can(user, "decide") && n.status === "proposed" && (
            <div className="row" style={{ marginTop: 8 }}>
              <button onClick={() => void guard(() => api.decideAiNote(n.id, "accepted"))} data-testid="ai-accept">{t("ai.accept")}</button>
              <button onClick={() => void guard(() => api.decideAiNote(n.id, "rejected"))}>{t("ai.rejectNote")}</button>
            </div>
          )}
        </div>
      ))}

      {can(user, "decide") && ["confirmed", "rejected", "fixed"].includes(f.status) && (
        <div className="panel" style={{ marginTop: 16 }}>
          <strong>{t("lesson.title")}</strong>
          <p className="muted">{t("lesson.hint")}</p>
          {lessonSent ? <p className="note" data-testid="lesson-sent">{t("lesson.sent")}</p> : (
            <>
              <textarea value={lesson} onChange={(e) => setLesson(e.target.value)} placeholder={t("lesson.placeholder")} data-testid="lesson-text" />
              <button style={{ marginTop: 8 }} data-testid="lesson-submit"
                      onClick={() => void guard(async () => { await api.proposeLesson(id, lesson); setLessonSent(true); })}>{t("lesson.submit")}</button>
            </>
          )}
        </div>
      )}

      <h2>{t("finding.evidence")}</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>{t("doc.number")}</th><th>{t("doc.type")}</th><th>{t("doc.revision")}</th><th>{t("doc.page")}</th><th>{t("doc.location")}</th><th>{t("doc.value")}</th><th /></tr>
          </thead>
          <tbody>
            {f.evidence.map((e, i) => (
              <tr key={i} data-testid="evidence-row">
                <td>{e.doc_number ?? e.filename}</td>
                <td>{t(`doctype.${e.doc_type}` as Key)}</td>
                <td>{e.revision ?? "—"}</td>
                <td>{e.page_no}</td>
                <td>{e.location}</td>
                <td><strong>{e.value}</strong></td>
                <td>
                  <Link to={`/documents/${e.document_id}?page=${e.page_no}${f.tag ? `&tag=${encodeURIComponent(f.tag)}` : ""}`} data-testid="evidence-link">
                    {t("finding.openDocument")}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
