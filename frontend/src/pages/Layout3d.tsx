import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type L3Item, type Layout3dData } from "../api";
import { ErrorNote } from "../components/Layout";
import { ThreeView } from "../components/ThreeView";
import { useErrorText, useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { can, useSession } from "../session";

const KINDS = ["vessel", "column", "tank", "reactor", "exchanger", "pump", "compressor", "heater", "generic"];
const uid = () => `m:${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;

/** Son maydoni: qiymat fokus yo'qolganda yoki Enter bosilganda yuboriladi (har harfda emas). */
function Num({ value, tick, label, testid, disabled, onCommit }: { value: number; tick: number; label: string; testid: string; disabled: boolean; onCommit: (v: number) => void }) {
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value, tick]);   // tick: har bir so'rov tugagach model qiymatiga qaytadi
  const commit = () => {
    const v = Number(text.replace(",", "."));
    if (text.trim() !== "" && Number.isFinite(v) && v !== value) onCommit(v);
    else setText(String(value));
  };
  return <input type="number" step="any" aria-label={label} data-testid={testid} value={text} disabled={disabled}
                onChange={(e) => setText(e.target.value)} onBlur={commit}
                onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />;
}

export function Layout3dPage() {
  const id = Number(useParams().id);
  const { t } = useI18n();
  const { user } = useSession();
  const errorText = useErrorText();
  const project = useLoad(() => api.project(id), [id]);
  const loaded = useLoad(() => api.layout3d(id), [id]);
  const [data, setData] = useState<Layout3dData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [webgl, setWebgl] = useState(true);
  const [newLabel, setNewLabel] = useState("");
  const [newKind, setNewKind] = useState("vessel");
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);
  const editable = can(user, "decide") && !busy;   // so'rov tugaguncha yangi tahrir qabul qilinmaydi (javoblar tartibi buzilmasin)

  useEffect(() => { setData(null); setSelected(null); }, [id]);
  useEffect(() => { if (loaded.data) setData(loaded.data); }, [loaded.data]);
  const run = async (fn: () => Promise<Layout3dData>) => {
    setError(null);
    setBusy(true);
    try {
      setData(await fn());
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
      setTick((n) => n + 1);
    }
  };
  const edit = (op: Record<string, unknown>) => run(() => api.layout3dEdit(id, op));
  if (!data) return <ErrorNote text={loaded.error} />;

  const add = (e: FormEvent) => {
    e.preventDefault();
    if (!newLabel.trim()) return;
    const maxX = Math.max(0, ...data.items.map((i) => i.x));
    void edit({ op: "add_item", id: uid(), label: newLabel.trim(), kind: newKind, x: Math.round(maxX + 12), y: 0 });
    setNewLabel("");
  };
  const src = (value: string) => t(`l3.src.${value}` as Key);
  const row = (i: L3Item) => (
    <tr key={i.id} className={selected === i.id ? "sel" : ""} data-testid="l3-row" data-id={i.id} onClick={() => setSelected(i.id)}>
      <td>
        <strong>{i.label}</strong>
        {i.renamed && <small>({t("dg.was", { label: i.original_label ?? "" })})</small>}
        <small>{t(`dg.kind.${i.kind}` as Key)}</small>
      </td>
      <td>
        <Num tick={tick} value={i.x} label={`${i.label} ${t("l3.x")}`} testid="l3-x" disabled={!editable} onCommit={(v) => void edit({ op: "move", id: i.id, x: v, y: i.y })} />{" "}
        <Num tick={tick} value={i.y} label={`${i.label} ${t("l3.y")}`} testid="l3-y" disabled={!editable} onCommit={(v) => void edit({ op: "move", id: i.id, x: i.x, y: v })} />
        <small data-testid="l3-pos-src">{src(i.position_source)}</small>
      </td>
      <td><Num tick={tick} value={i.rot} label={`${i.label} ${t("l3.rot")}`} testid="l3-rot" disabled={!editable} onCommit={(v) => void edit({ op: "rotate", id: i.id, rot: v })} /></td>
      <td>
        <Num tick={tick} value={i.w} label={`${i.label} ${t("l3.w")}`} testid="l3-w" disabled={!editable} onCommit={(v) => void edit({ op: "resize", id: i.id, w: v, d: i.shape === "cylinder_v" ? v : i.d, h: i.h })} />{" "}
        <Num tick={tick} value={i.d} label={`${i.label} ${t("l3.d")}`} testid="l3-d" disabled={!editable || i.shape !== "box"} onCommit={(v) => void edit({ op: "resize", id: i.id, w: i.w, d: v, h: i.h })} />{" "}
        <Num tick={tick} value={i.h} label={`${i.label} ${t("l3.h")}`} testid="l3-h" disabled={!editable} onCommit={(v) => void edit({ op: "resize", id: i.id, w: i.w, d: i.shape === "cylinder_h" ? v : i.d, h: v })} />
        <small data-testid="l3-size-src">{src(i.size_source)}</small>
      </td>
      <td>
        {can(user, "decide") && (
          <>
            <button className="link" data-testid="l3-rename" onClick={(e) => {
              e.stopPropagation();
              const label = window.prompt(t("dg.rename"), i.label);
              if (label && label.trim() && label.trim() !== i.label) void edit({ op: "rename", id: i.id, label: label.trim() });
            }}>{t("dg.rename")}</button>{" "}
            <button className="link" data-testid="l3-delete" onClick={(e) => { e.stopPropagation(); void edit({ op: "remove_item", id: i.id }); }}>{t("dg.delete")}</button>
          </>
        )}
      </td>
    </tr>
  );

  return (
    <>
      <div className="crumbs"><Link to="/projects">{t("nav.projects")}</Link> / <Link to={`/projects/${id}`}>{project.data?.name ?? "…"}</Link> /</div>
      <h1>{t("l3.title")}</h1>
      <p className="sub">{t("l3.intro")}</p>
      <ErrorNote text={error} />
      {data.stale && <p className="warn" data-testid="l3-stale">{t("l3.stale")}</p>}
      <div className="row" style={{ marginBottom: 10 }}>
        {can(user, "review") && <button className={data.exists ? "" : "primary"} onClick={() => void run(() => api.layout3dGenerate(id))} data-testid="l3-generate">{t(data.exists ? "dg.regenerate" : "l3.generate")}</button>}
        {data.exists && can(user, "decide") && (
          <>
            <button disabled={busy || !data.can_undo} onClick={() => void run(() => api.layout3dUndo(id))} data-testid="l3-undo">{t("dg.undo")}</button>
            <button disabled={busy || !data.can_redo} onClick={() => void run(() => api.layout3dRedo(id))} data-testid="l3-redo">{t("dg.redo")}</button>
          </>
        )}
      </div>
      {!data.exists && <p className="muted">{t("l3.empty")}</p>}
      {data.exists && (
        <>
          <p className={data.plot_plan ? "warn" : "note"} data-testid="l3-source">
            {data.plot_plan ? t("l3.plotPlan", { doc: data.plot_plan, unit: data.unit_assumed === "mm" ? "mm" : "m" }) : t("l3.noPlotPlan")}
          </p>
          {webgl
            ? <ThreeView items={data.items} selected={selected} editable={editable} onSelect={setSelected}
                         onMove={(itemId, x, y) => void edit({ op: "move", id: itemId, x, y })} onError={() => setWebgl(false)} />
            : <p className="warn" data-testid="l3-nowebgl">{t("l3.noWebgl")}</p>}
          <div className="legend">
            <span><span className="swatch" />{t("l3.legend.document")}</span>
            <span><span className="swatch assumed" />{t("l3.legend.assumed")}</span>
            <span><span className="swatch manual" />{t("l3.legend.manual")}</span>
          </div>
          <p className="muted">{t("l3.hint")}</p>
          <p className="note">{t("l3.elevation")} {t("l3.notApplied")}</p>
          {data.orphan_edits.length > 0 && <p className="warn">{t("dg.orphans", { count: data.orphan_edits.length })}</p>}

          <h2>{t("l3.items")}</h2>
          {can(user, "decide") && (
            <form className="filters" onSubmit={add}>
              <label className="field">{t("dg.nodeLabel")}<input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} maxLength={80} data-testid="l3-new-label" /></label>
              <label className="field">{t("doc.type")}
                <select value={newKind} onChange={(e) => setNewKind(e.target.value)}>
                  {KINDS.map((k) => <option key={k} value={k}>{t(`dg.kind.${k}` as Key)}</option>)}
                </select>
              </label>
              <button data-testid="l3-add">{t("l3.addItem")}</button>
            </form>
          )}
          <div className="table-wrap">
            <table className="l3-table">
              <thead>
                <tr><th>{t("doc.tag")}</th><th>{t("l3.x")} / {t("l3.y")}</th><th>{t("l3.rot")}</th><th>{t("l3.w")} / {t("l3.d")} / {t("l3.h")}</th><th /></tr>
              </thead>
              <tbody>{data.items.map(row)}</tbody>
            </table>
          </div>
          <h2>{t("dg.differences")}</h2>
          {data.differences.length === 0 ? <p className="muted">{t("l3.noDifferences")}</p> : (
            <ul data-testid="l3-differences">
              {data.differences.map((d, i) => <li key={i}>{t(`l3.diff.${d.kind}` as Key)}: <strong>{d.label}</strong></li>)}
            </ul>
          )}
        </>
      )}
    </>
  );
}
