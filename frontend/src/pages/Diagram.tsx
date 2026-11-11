import { type PointerEvent as RPointerEvent, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type DgNode, type DiagramData } from "../api";
import { ErrorNote } from "../components/Layout";
import { useErrorText, useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { can, useSession } from "../session";

const W = 150;
const H = 64;
const MANUAL_KINDS = ["vessel", "pump", "exchanger", "column", "compressor", "tank", "reactor", "heater", "generic"];
const uid = () => `m:${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;

export function DiagramPage() {
  const id = Number(useParams().id);
  const { t } = useI18n();
  const { user } = useSession();
  const errorText = useErrorText();
  const project = useLoad(() => api.project(id), [id]);
  const loaded = useLoad(() => api.diagram(id), [id]);
  const [data, setData] = useState<DiagramData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number; x: number; y: number; x0: number; y0: number; moved: boolean } | null>(null);
  const [newLabel, setNewLabel] = useState("");
  const [newKind, setNewKind] = useState("vessel");
  const svgRef = useRef<SVGSVGElement>(null);
  const editable = can(user, "decide");

  useEffect(() => { if (loaded.data) setData(loaded.data); }, [loaded.data]);

  const run = async (fn: () => Promise<DiagramData>) => {
    setError(null);
    try {
      setData(await fn());
    } catch (err) {
      setError(errorText(err));
    }
  };
  const edit = (op: Record<string, unknown>) => run(() => api.diagramEdit(id, op));

  if (!data) return <ErrorNote text={loaded.error} />;
  const nodes = data.nodes.map((n) => (drag && drag.id === n.id ? { ...n, x: drag.x, y: drag.y } : n));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  // Ko'rinish chegarasi saqlangan o'rinlardan hisoblanadi: sudrash paytida butun sxema masshtabi o'zgarib ketmaydi.
  const xs = data.nodes.map((n) => n.x);
  const ys = data.nodes.map((n) => n.y);
  const minX = Math.min(0, ...xs) - 60;
  const minY = Math.min(0, ...ys) - 60;
  const width = Math.max(900, Math.max(0, ...xs) + W + 80 - minX);
  const height = Math.max(520, Math.max(0, ...ys) + H + 80 - minY);

  // Ekran nuqtasini sxema koordinatasiga o'giradi (masshtab va siljishni hisobga oladi).
  const toDiagram = (e: { clientX: number; clientY: number }) => {
    const svg = svgRef.current!;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.getScreenCTM()!.inverse());
    return { x: p.x, y: p.y };
  };
  const onNodeDown = (e: RPointerEvent, n: DgNode) => {
    if (connecting) return;
    const p = toDiagram(e);
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    setSelected(n.id);
    if (editable) setDrag({ id: n.id, dx: p.x - n.x, dy: p.y - n.y, x: n.x, y: n.y, x0: n.x, y0: n.y, moved: false });
  };
  const onNodeMove = (e: RPointerEvent) => {
    if (!drag) return;
    const p = toDiagram(e);
    const x = Math.round(p.x - drag.dx);
    const y = Math.round(p.y - drag.dy);
    // Oddiy bosishdagi mayda titrash ko'chirish hisoblanmaydi: aks holda keraksiz tahrir yozilib, "Oldinga" tarixi o'chadi.
    const moved = drag.moved || Math.hypot(x - drag.x0, y - drag.y0) > 4;
    setDrag(moved ? { ...drag, x, y, moved } : drag);
  };
  const onNodeUp = () => {
    if (!drag) return;
    const d = drag;
    if (d.moved) {
      // Yangi o'rin darhol ko'rsatiladi, keyin saqlanadi: tugun eski joyiga sakrab qaytmaydi.
      setData({ ...data, nodes: data.nodes.map((n) => (n.id === d.id ? { ...n, x: d.x, y: d.y } : n)) });
      void edit({ op: "move", id: d.id, x: d.x, y: d.y });
    }
    setDrag(null);
  };
  const onNodeClick = (n: DgNode) => {
    if (!connecting) return;
    if (!connectFrom) setConnectFrom(n.id);
    else if (connectFrom !== n.id) {
      void edit({ op: "add_edge", id: uid(), from: connectFrom, to: n.id, label: "" });
      setConnectFrom(null);
      setConnecting(false);
    }
  };
  const selectedNode = selected ? byId.get(selected) : undefined;
  const selectedEdge = selected ? data.edges.find((e) => e.id === selected) : undefined;
  const download = async () => {
    try {
      const url = URL.createObjectURL(await api.diagramSvg(id));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${project.data?.name ?? "diagram"}.svg`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (err) {
      setError(errorText(err));
    }
  };

  return (
    <>
      <div className="crumbs"><Link to="/projects">{t("nav.projects")}</Link> / <Link to={`/projects/${id}`}>{project.data?.name ?? "…"}</Link> /</div>
      <h1>{t("dg.title")}</h1>
      <p className="sub">{t("dg.intro")}</p>
      <ErrorNote text={error} />
      {data.stale && <p className="warn" data-testid="dg-stale">{t("dg.stale")}</p>}
      <div className="row" style={{ marginBottom: 10 }}>
        {can(user, "review") && <button className={data.exists ? "" : "primary"} onClick={() => void run(() => api.diagramGenerate(id))} data-testid="dg-generate">{t(data.exists ? "dg.regenerate" : "dg.generate")}</button>}
        {data.exists && editable && (
          <>
            <button disabled={!data.can_undo} onClick={() => void run(() => api.diagramUndo(id))} data-testid="dg-undo">{t("dg.undo")}</button>
            <button disabled={!data.can_redo} onClick={() => void run(() => api.diagramRedo(id))} data-testid="dg-redo">{t("dg.redo")}</button>
            <button className={connecting ? "primary" : ""} onClick={() => { setConnecting(!connecting); setConnectFrom(null); }} data-testid="dg-connect">{t("dg.connect")}</button>
          </>
        )}
        {data.exists && <button onClick={download} data-testid="dg-export">{t("dg.export")}</button>}
      </div>
      {connecting && <p className="note">{t("dg.connectHint")}</p>}
      {!data.exists && <p className="muted">{t("dg.empty")}</p>}

      {data.exists && (
        <>
          {editable && (
            <form className="filters" onSubmit={(e) => {
              e.preventDefault();
              if (!newLabel.trim()) return;
              void edit({ op: "add_node", id: uid(), label: newLabel.trim(), kind: newKind, x: minX + 80, y: minY + 70 });
              setNewLabel("");
            }}>
              <label className="field">{t("dg.nodeLabel")}<input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} maxLength={80} data-testid="dg-new-label" /></label>
              <label className="field">{t("doc.type")}
                <select value={newKind} onChange={(e) => setNewKind(e.target.value)}>
                  {MANUAL_KINDS.map((k) => <option key={k} value={k}>{t(`dg.kind.${k}` as Key)}</option>)}
                </select>
              </label>
              <button data-testid="dg-add-node">{t("dg.addNode")}</button>
              {(selectedNode || selectedEdge) && (
                <>
                  <span className="muted" data-testid="dg-selected">{t("dg.selected", { label: selectedNode?.label ?? selectedEdge?.label ?? "" })}</span>
                  {selectedNode && (
                    <button type="button" data-testid="dg-rename" onClick={() => {
                      const label = window.prompt(t("dg.rename"), selectedNode.label);
                      if (label && label.trim() && label.trim() !== selectedNode.label) void edit({ op: "rename_node", id: selectedNode.id, label: label.trim() });
                    }}>{t("dg.rename")}</button>
                  )}
                  <button type="button" className="danger" data-testid="dg-delete" onClick={() => {
                    void edit({ op: selectedNode ? "remove_node" : "remove_edge", id: selected! });
                    setSelected(null);
                  }}>{t("dg.delete")}</button>
                </>
              )}
            </form>
          )}
          <div className="dg-wrap">
            <svg ref={svgRef} viewBox={`${minX} ${minY} ${width} ${height}`} data-testid="dg-canvas" onPointerDown={(e) => { if (e.target === e.currentTarget) setSelected(null); }}>
              <defs>
                <marker id="dg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M0,0 L10,5 L0,10 z" fill="currentColor" />
                </marker>
              </defs>
              {data.edges.map((e) => {
                const a = byId.get(e.from);
                const b = byId.get(e.to);
                if (!a || !b) return null;
                const [x1, y1, x2, y2] = [a.x + W / 2, a.y + H / 2, b.x + W / 2, b.y + H / 2];
                // Chiziq tugun chetida tugaydi: o'q uchi blok ostida qolib ketmasin.
                const len = Math.hypot(x2 - x1, y2 - y1) || 1;
                const cut = Math.min(len / 2, Math.abs((x2 - x1) / len) > Math.abs((y2 - y1) / len) * (W / H) ? (W / 2) / Math.abs((x2 - x1) / len) : (H / 2) / Math.abs((y2 - y1) / len));
                const ex = x2 - ((x2 - x1) / len) * cut;
                const ey = y2 - ((y2 - y1) / len) * cut;
                return (
                  <g key={e.id} data-testid="dg-edge" data-source={e.source} data-directed={e.directed === false ? "false" : "true"} onPointerDown={() => setSelected(e.id)} style={{ color: "var(--muted)", cursor: "pointer" }}>
                    <line x1={x1} y1={y1} x2={ex} y2={ey} stroke="transparent" strokeWidth={14} />
                    <line className={`dg-edge src-${e.source} ${selected === e.id ? "selected" : ""}`} x1={x1} y1={y1} x2={ex} y2={ey}
                          markerEnd={e.directed === false || (e.directed === undefined && e.source === "inferred") ? undefined : "url(#dg-arrow)"} />
                    {e.label && <text className="dg-edge-label" x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6} textAnchor="middle">{e.label}</text>}
                  </g>
                );
              })}
              {nodes.map((n) => (
                <g key={n.id} className={`dg-node src-${n.renamed ? "manual" : n.source} kind-${n.kind} ${n.line_list_only ? "line-list-only" : ""} ${selected === n.id || connectFrom === n.id ? "selected" : ""}`}
                   data-testid="dg-node" data-id={n.id} data-source={n.source} data-renamed={n.renamed ? "true" : "false"} transform={`translate(${n.x},${n.y})`}
                   onPointerDown={(e) => onNodeDown(e, n)} onPointerMove={onNodeMove} onPointerUp={onNodeUp}
                   onPointerCancel={() => setDrag(null)} onLostPointerCapture={() => setDrag((d) => (d && !d.moved ? null : d))}
                   onClick={() => onNodeClick(n)}>
                  <title>{[t(`dg.kind.${n.kind}` as Key), ...(n.renamed ? [t("dg.was", { label: n.original_label ?? "" })] : []),
                           ...(n.line_list_only ? [t("dg.legend.lineListOnly")] : []), ...Object.values(n.params)].join(" · ")}</title>
                  <rect width={W} height={H} rx={["vessel", "column", "tank", "reactor"].includes(n.kind) ? 32 : 6} />
                  <text x={W / 2} y={H / 2 + (n.renamed ? -2 : 5)} textAnchor="middle">{n.label}</text>
                  {n.renamed && <text x={W / 2} y={H / 2 + 15} textAnchor="middle" style={{ fontSize: 11, fill: "var(--muted)" }}>({t("dg.was", { label: n.original_label ?? "" })})</text>}
                </g>
              ))}
            </svg>
          </div>
          <div className="legend">
            <span><i />{t("dg.legend.document")}</span>
            <span><i className="inferred" />{t("dg.legend.inferred")}</span>
            <span><i className="manual" />{t("dg.legend.manual")}</span>
            {data.nodes.some((n) => n.line_list_only) && <span><i className="dotted" />{t("dg.legend.lineListOnly")}</span>}
          </div>
          <p className="note">{t("dg.notApplied")}</p>
          {data.orphan_edits.length > 0 && <p className="warn" data-testid="dg-orphans">{t("dg.orphans", { count: data.orphan_edits.length })}</p>}
          {data.unconnected.length > 0 && <p className="muted" data-testid="dg-unconnected">{t("dg.unconnected")}: {data.unconnected.join(", ")}</p>}
          <h2>{t("dg.differences")}</h2>
          {data.differences.length === 0 ? <p className="muted">{t("dg.noDifferences")}</p> : (
            <ul data-testid="dg-differences">
              {data.differences.map((d, i) => <li key={i}>{t(`dg.diff.${d.kind}` as Key)}: <strong>{d.label}</strong></li>)}
            </ul>
          )}
        </>
      )}
    </>
  );
}
