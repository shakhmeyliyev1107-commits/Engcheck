import { type ChangeEvent, useState } from "react";
import { api } from "../api";
import { DEFAULT_DISCIPLINE, DISCIPLINES, DOC_TYPES } from "../constants";
import { useErrorText } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { ErrorNote } from "./Layout";

interface Row { file: File; doc_type: string; discipline: string; doc_number: string; revision: string; error?: string }

export function UploadDialog({ projectId, onClose }: { projectId: number; onClose: (changed: boolean) => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState(false);

  const choose = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    const next: Row[] = [];
    for (const file of files) {
      let hint = { doc_type: null as string | null, doc_number: null as string | null, revision: null as string | null };
      try {
        hint = await api.suggest(file.name);
      } catch {
        /* taklif bo'lmasa foydalanuvchi o'zi tanlaydi */
      }
      const doc_type = hint.doc_type ?? "";
      next.push({ file, doc_type, discipline: DEFAULT_DISCIPLINE[doc_type] ?? "process",
                  doc_number: hint.doc_number ?? "", revision: hint.revision ?? "" });
    }
    setRows(next);
    setError(null);
  };

  const patch = (i: number, change: Partial<Row>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...change } : r)));

  const submit = async () => {
    if (rows.some((r) => !r.doc_type)) {
      setError(t("upload.typeRequired"));
      return;
    }
    setBusy(true);
    setError(null);
    const failed: Row[] = [];
    let ok = false;
    for (const row of rows) {
      try {
        await api.upload(projectId, row.file, row);
        ok = true;
      } catch (err) {
        failed.push({ ...row, error: errorText(err) });  // bitta xato qolganlarini to'xtatmaydi
      }
    }
    setBusy(false);
    if (ok) setUploaded(true);
    if (failed.length === 0) onClose(true);
    else setRows(failed);
  };

  return (
    <div className="modal-back" role="dialog" aria-modal="true" aria-label={t("upload.title")}>
      <div className="modal">
        <h2 style={{ marginTop: 0 }}>{t("upload.title")}</h2>
        <p className="muted">{t("upload.hint")}</p>
        <label className="field">
          {t("upload.choose")}
          <input type="file" multiple onChange={choose} data-testid="file-input" accept=".pdf,.docx,.xlsx,.dxf,.dwg" />
        </label>
        {rows.length > 0 && (
          <div className="table-wrap" style={{ marginTop: 14 }}>
            <table>
              <thead>
                <tr><th>{t("doc.file")}</th><th>{t("doc.type")}</th><th>{t("doc.discipline")}</th><th>{t("doc.number")}</th><th>{t("doc.revision")}</th></tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.file.name} data-testid="upload-row">
                    <td>{r.file.name}{r.error && <div className="error">{r.error}</div>}</td>
                    <td>
                      <select aria-label={t("doc.type")} value={r.doc_type}
                              onChange={(e) => patch(i, { doc_type: e.target.value, discipline: DEFAULT_DISCIPLINE[e.target.value] ?? r.discipline })}>
                        <option value="">{t("upload.selectType")}</option>
                        {DOC_TYPES.map((d) => <option key={d} value={d}>{t(`doctype.${d}` as Key)}</option>)}
                      </select>
                    </td>
                    <td>
                      <select aria-label={t("doc.discipline")} value={r.discipline} onChange={(e) => patch(i, { discipline: e.target.value })}>
                        {DISCIPLINES.map((d) => <option key={d} value={d}>{t(`discipline.${d}` as Key)}</option>)}
                      </select>
                    </td>
                    <td><input aria-label={t("doc.number")} value={r.doc_number} size={14} onChange={(e) => patch(i, { doc_number: e.target.value })} /></td>
                    <td><input aria-label={t("doc.revision")} value={r.revision} size={4} onChange={(e) => patch(i, { revision: e.target.value })} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <ErrorNote text={error} />
        <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
          <button onClick={() => onClose(uploaded)} disabled={busy}>{t("common.cancel")}</button>
          <button className="primary" onClick={submit} disabled={busy || rows.length === 0} data-testid="upload-submit">
            {busy ? t("upload.uploading") : t("upload.submit")}
          </button>
        </div>
      </div>
    </div>
  );
}
