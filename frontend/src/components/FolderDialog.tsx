import { type FormEvent, useEffect, useState } from "react";
import { api, type FolderResult, type FolderScan } from "../api";
import { DEFAULT_DISCIPLINE, DISCIPLINES, DOC_TYPES } from "../constants";
import { useErrorText } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { can, useSession } from "../session";
import { ErrorNote } from "./Layout";

interface Row { path: string; status: string; checked: boolean; doc_type: string; discipline: string; doc_number: string; revision: string; result?: FolderResult }

const size = (bytes: number) => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);

/** Loyihaga ulangan papkani skanerlaydi va tanlangan hujjatlarni yuklaydi. */
export function FolderDialog({ projectId, onClose }: { projectId: number; onClose: (changed: boolean) => void }) {
  const { t } = useI18n();
  const { user } = useSession();
  const errorText = useErrorText();
  const [path, setPath] = useState("");
  const [linked, setLinked] = useState<string | null>(null);
  const [scan, setScan] = useState<FolderScan | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changed, setChanged] = useState(false);
  const canLink = can(user, "link_folder");

  const rescan = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await api.folderScan(projectId);
      setScan(data);
      setRows(data.files.map((f) => {
        const doc_type = f.doc_type ?? "";
        return { path: f.path, status: f.status, checked: f.status === "new" && !!doc_type, doc_type,
                 discipline: DEFAULT_DISCIPLINE[doc_type] ?? "process", doc_number: f.doc_number ?? "", revision: f.revision ?? "" };
      }));
    } catch (err) {
      setScan(null);
      setRows([]);
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void (async () => {
      try {
        const current = (await api.folder(projectId)).path;
        setLinked(current);
        setPath(current ?? "");
        if (current) await rescan();
      } catch (err) {
        setError(errorText(err));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const link = async (e: FormEvent, value: string | null) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved = (await api.folderLink(projectId, value)).path;
      setLinked(saved);
      setPath(saved ?? "");
      setScan(null);
      setRows([]);
      setBusy(false);
      if (saved) await rescan();
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  const patch = (i: number, change: Partial<Row>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...change } : r)));
  const chosen = rows.filter((r) => r.checked && r.status === "new" && r.doc_type);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const { results } = await api.folderImport(projectId, chosen.map((r) => ({
        path: r.path, doc_type: r.doc_type, discipline: r.discipline, doc_number: r.doc_number || null, revision: r.revision || null })));
      const byPath = new Map(results.map((r) => [r.path, r]));
      if (results.some((r) => r.status === "imported")) setChanged(true);
      setRows((rs) => rs.map((r) => {
        const result = byPath.get(r.path);
        return result ? { ...r, result, checked: false, status: result.status === "error" ? r.status : "imported" } : r;
      }));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const count = (status: string[]) => rows.filter((r) => status.includes(r.status)).length;
  return (
    <div className="modal-back" role="dialog" aria-modal="true" aria-label={t("folder.title")}>
      <div className="modal">
        <h2 style={{ marginTop: 0 }}>{t("folder.title")}</h2>
        <p className="muted">{t("folder.hint")}</p>
        {canLink ? (
          <form className="filters" onSubmit={(e) => void link(e, path)}>
            <label className="field" style={{ flex: 1 }}>{t("folder.path")}
              <input value={path} onChange={(e) => setPath(e.target.value)} maxLength={1000} placeholder="C:\Loyiha\Hujjatlar" data-testid="folder-path" />
            </label>
            <button className="primary" disabled={busy || !path.trim()} data-testid="folder-link">{t("folder.link")}</button>
            {linked && <button type="button" disabled={busy} onClick={(e) => void link(e, null)} data-testid="folder-unlink">{t("folder.unlink")}</button>}
          </form>
        ) : (
          <p className="note">{linked ? <><strong>{linked}</strong> — </> : <>{t("folder.notLinked")} </>}{t("folder.onlyLead")}</p>
        )}
        <ErrorNote text={error} />
        {busy && !scan && <p className="muted">{t("folder.scanning")}</p>}
        {scan && (
          <>
            <div className="row" style={{ margin: "8px 0" }}>
              <span data-testid="folder-summary">{t("folder.summary", { new: count(["new"]), imported: count(["imported"]), skipped: count(["unsupported", "too_large", "unreadable"]) })}</span>
              <button disabled={busy} onClick={() => void rescan()} data-testid="folder-rescan">{t("folder.rescan")}</button>
            </div>
            {scan.truncated && <p className="warn">{t("folder.truncated")}</p>}
            {rows.length === 0 ? <p className="muted">{t("folder.empty")}</p> : (
              <>
                <p className="muted">{t("folder.typeNote")}</p>
                <div className="table-wrap" style={{ maxHeight: 380, overflow: "auto" }}>
                  <table>
                    <thead>
                      <tr><th /><th>{t("folder.file")}</th><th>{t("doc.type")}</th><th>{t("doc.discipline")}</th><th>{t("doc.number")}</th><th>{t("doc.revision")}</th></tr>
                    </thead>
                    <tbody>
                      {rows.map((r, i) => {
                        const fresh = r.status === "new";
                        return (
                          <tr key={r.path} data-testid="folder-row" data-status={r.status}>
                            <td>{fresh && <input type="checkbox" aria-label={r.path} checked={r.checked} disabled={!r.doc_type} onChange={(e) => patch(i, { checked: e.target.checked })} />}</td>
                            <td>
                              {r.path}
                              <small style={{ display: "block" }} className={r.result?.status === "error" ? "error" : "muted"}>
                                {r.result ? t(`folder.result.${r.result.status}` as Key) : t(`folder.status.${r.status}` as Key)}
                                {" · "}{size(scan.files[i]?.size ?? 0)}
                              </small>
                            </td>
                            {fresh ? (
                              <>
                                <td>
                                  <select aria-label={t("doc.type")} value={r.doc_type}
                                          onChange={(e) => patch(i, { doc_type: e.target.value, checked: !!e.target.value, discipline: DEFAULT_DISCIPLINE[e.target.value] ?? r.discipline })}>
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
                              </>
                            ) : <td colSpan={4} />}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
        <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
          <button onClick={() => onClose(changed)} disabled={busy} data-testid="folder-close">{t("common.close")}</button>
          {scan && <button className="primary" onClick={() => void submit()} disabled={busy || chosen.length === 0} data-testid="folder-import">
            {busy ? t("upload.uploading") : t("folder.import", { count: chosen.length })}
          </button>}
        </div>
      </div>
    </div>
  );
}
