"use client";

import { useEffect, useMemo, useState } from "react";

type Source = { type: string; code: string; quantity: number; arrival: string; original_arrival?: string; status: string; supplier?: string };
type Option = { id: string; type: "transfer" | "supplier"; source_ref: string; title: string; source: string; quantity: number; available: number; expected_arrival: string; delivery_impact: string; status: "on_time" | "late" | "infeasible"; reason: string | null };
type Order = { id: number; code: string; customer: string; priority: string; status: string; facility: string; facility_code: string; promised_date: string; sku: string; sku_name: string; quantity: number; available_by_promise: number; shortage: number; projected_date: string | null; late_days: number; urgency_score: number; affected: boolean; sources: Source[]; calculation: { formula: string; priority_weight: number; shortage_ratio: number; late_day_points: number; deadline_pressure: number }; options?: Option[] };
type Audit = { id: number; actor: string; action: string; entity_type: string; entity_id: string; detail: string; created_at: string };
type Explanation = { answer: string; mode?: string; links: { label: string; href: string }[] };
type Dashboard = { company: string; scenario_date: string; metrics: { active_disruptions: number; orders_at_risk: number; units_exposed: number; recovered: number }; disruptions: { id: number; code: string; severity: string; summary: string; delay_days: number; shipment: string }[]; orders: Order[] };

const options: Option[] = [
  { id: "transfer:2", type: "transfer", source_ref: "2", title: "Transfer from Crosswind Central", source: "DFW-02", quantity: 40, available: 60, expected_arrival: "2026-09-30", delivery_impact: "On time", status: "on_time", reason: null },
  { id: "supplier:2", type: "supplier", source_ref: "2", title: "Expedite from Northstar Industrial", source: "SUP-NOR", quantity: 40, available: 90, expected_arrival: "2026-10-03", delivery_impact: "On time", status: "on_time", reason: null },
  { id: "supplier:1", type: "supplier", source_ref: "1", title: "Reorder from Meridian Components", source: "SUP-MER", quantity: 40, available: 120, expected_arrival: "2026-10-07", delivery_impact: "2 days late", status: "late", reason: null },
  { id: "supplier:3", type: "supplier", source_ref: "3", title: "Expedite from Eastline Works", source: "SUP-EAS", quantity: 18, available: 18, expected_arrival: "2026-10-02", delivery_impact: "Capacity shortfall", status: "infeasible", reason: "Supplier capacity is 18 units; 40 are required." },
];

const baseOrders: Order[] = [
  { id: 1, code: "ORD-4821", customer: "Atlas Field Systems", priority: "critical", status: "open", facility: "Harborpoint East", facility_code: "EWR-01", promised_date: "2026-10-05", sku: "AX-440", sku_name: "Axis control module", quantity: 50, available_by_promise: 10, shortage: 40, projected_date: "2026-10-10", late_days: 5, urgency_score: 101, affected: true,
    sources: [{ type: "inventory", code: "EWR-01", quantity: 10, arrival: "2026-09-28", status: "ready" }, { type: "shipment", code: "INB-7392", quantity: 40, arrival: "2026-10-10", original_arrival: "2026-10-01", status: "delayed", supplier: "Meridian Components" }],
    calculation: { formula: "priority weight + shortage ratio × 35 + projected late days × 6 + deadline pressure", priority_weight: 35, shortage_ratio: .8, late_day_points: 30, deadline_pressure: 8 }, options },
  { id: 2, code: "ORD-4824", customer: "Kestrel Automation", priority: "high", status: "open", facility: "Harborpoint East", facility_code: "EWR-01", promised_date: "2026-10-07", sku: "AX-440", sku_name: "Axis control module", quantity: 30, available_by_promise: 5, shortage: 25, projected_date: "2026-10-10", late_days: 3, urgency_score: 81, affected: true,
    sources: [{ type: "inventory", code: "EWR-01", quantity: 5, arrival: "2026-09-28", status: "ready" }, { type: "shipment", code: "INB-7392", quantity: 25, arrival: "2026-10-10", original_arrival: "2026-10-01", status: "delayed", supplier: "Meridian Components" }],
    calculation: { formula: "priority weight + shortage ratio × 35 + projected late days × 6 + deadline pressure", priority_weight: 24, shortage_ratio: .83, late_day_points: 18, deadline_pressure: 2 }, options: options.map(o => ({ ...o, quantity: Math.min(o.available, 25), reason: o.id === "supplier:3" ? "Supplier capacity is 18 units; 25 are required." : o.reason })) },
  { id: 3, code: "ORD-4830", customer: "Juniper Controls", priority: "standard", status: "open", facility: "Harborpoint East", facility_code: "EWR-01", promised_date: "2026-10-08", sku: "LM-210", sku_name: "Lumen sensor pack", quantity: 20, available_by_promise: 20, shortage: 0, projected_date: "2026-09-28", late_days: 0, urgency_score: 12, affected: false,
    sources: [{ type: "inventory", code: "EWR-01", quantity: 20, arrival: "2026-09-28", status: "ready" }], calculation: { formula: "priority weight + shortage ratio × 35 + projected late days × 6 + deadline pressure", priority_weight: 12, shortage_ratio: 0, late_day_points: 0, deadline_pressure: 0 }, options: [] },
];

const initialDashboard: Dashboard = {
  company: "Northstar Freightworks", scenario_date: "2026-09-28",
  metrics: { active_disruptions: 1, orders_at_risk: 2, units_exposed: 65, recovered: 0 },
  disruptions: [{ id: 1, code: "DSP-018", severity: "high", summary: "Port congestion moved inbound INB-7392 nine days", delay_days: 9, shipment: "INB-7392" }],
  orders: baseOrders,
};

const initialAudit: Audit[] = [
  { id: 1, actor: "system", action: "scenario.reset", entity_type: "scenario", entity_id: "northstar-demo", detail: "Synthetic Northstar Freightworks demo scenario restored to baseline.", created_at: "2026-09-28T08:00:00Z" },
  { id: 2, actor: "system", action: "disruption.detected", entity_type: "shipment", entity_id: "INB-7392", detail: "Arrival moved from Oct 01 to Oct 10; two dependent orders recalculated.", created_at: "2026-09-28T08:02:00Z" },
];

const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const prettyDate = (value: string | null, short = false) => value ? new Intl.DateTimeFormat("en-US", { month: short ? "short" : "long", day: "numeric", ...(short ? {} : { year: "numeric" }) }).format(new Date(`${value}T12:00:00`)) : "Unconfirmed";
const api = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${apiUrl}${path}`, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`);
  return body as T;
};
const postJson = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const actionLabel = (action: string) => action.split(".").map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");

function Mark() {
  return <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>;
}

function StatusPill({ status }: { status: Option["status"] }) {
  const text = status === "on_time" ? "Feasible · on time" : status === "late" ? "Feasible · late" : "Infeasible";
  return <span className={`status-pill ${status}`}><span />{text}</span>;
}

export function SupplyScopeApp() {
  const [dashboard, setDashboard] = useState<Dashboard>(initialDashboard);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [view, setView] = useState<"tower" | "audit" | "model">("tower");
  const [detailTab, setDetailTab] = useState<"responses" | "evidence" | "logic">("responses");
  const [auditEvents, setAuditEvents] = useState<Audit[]>(initialAudit);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [selectedOption, setSelectedOption] = useState<Option | null>(null);
  const [proposalId, setProposalId] = useState<number | null>(null);
  const [workflow, setWorkflow] = useState<"idle" | "review" | "proposed" | "approved">("idle");
  const [toast, setToast] = useState<{ text: string; ok: boolean } | null>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);

  const selected = useMemo(() => dashboard.orders.find(order => order.id === selectedId) ?? null, [dashboard, selectedId]);

  const syncFromApi = async () => {
    const [data, events] = await Promise.all([api<Dashboard>("/api/dashboard"), api<Audit[]>("/api/audit")]);
    setDashboard(data); setAuditEvents(events.reverse());
  };

  useEffect(() => {
    if (!apiUrl) return;
    const signal = AbortSignal.timeout(1800);
    Promise.all([api<Dashboard>("/api/dashboard", { signal }), api<Audit[]>("/api/audit", { signal })])
      .then(([data, events]) => { setDashboard(data); setAuditEvents(events.reverse()); setConnected(true); })
      .catch(() => setConnected(false));
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const openOrder = async (order: Order) => {
    setSelectedId(order.id); setExplanation(null); setWorkflow("idle"); setSelectedOption(null); setDetailTab("responses");
    if (connected) {
      try {
        const detailed = await api<Order>(`/api/orders/${order.id}`);
        setDashboard(current => ({ ...current, orders: current.orders.map(item => item.id === order.id ? detailed : item) }));
      } catch (error) { setToast({ text: error instanceof Error ? error.message : "Could not load order", ok: false }); }
    }
  };

  const askWhy = async () => {
    if (!selected) return;
    setLoading(true);
    if (connected) {
      try {
        setExplanation(await api<Explanation>(`/api/orders/${selected.id}/explain`, { method: "POST" }));
        setLoading(false); return;
      } catch { /* fall back to the local deterministic explanation */ }
    }
    const delayed = selected.sources.find(source => source.status === "delayed");
    setExplanation({ answer: `${selected.code} needs ${selected.quantity} ${selected.sku} units, but only ${selected.available_by_promise} are available by ${prettyDate(selected.promised_date, true)}. The remaining ${selected.shortage} units are allocated to ${delayed?.code}, now due ${prettyDate(delayed?.arrival ?? null, true)}. That moves fulfillment ${selected.late_days} days past promise.`, links: [{ label: selected.code, href: "#order" }, { label: selected.sku, href: "#sku" }, { label: delayed?.code ?? "Shipment", href: "#shipment" }] });
    setLoading(false);
  };

  const createProposal = async () => {
    if (!selected || !selectedOption) return;
    setLoading(true);
    if (connected) {
      try {
        const created = await api<{ id: number }>("/api/proposals", postJson({ order_id: selected.id, option_type: selectedOption.type, source_ref: selectedOption.source_ref, quantity: selectedOption.quantity, expected_arrival: selectedOption.expected_arrival, actor: "Maya Chen", rationale: "Fastest feasible recovery with traceable supply." }));
        setProposalId(created.id);
        await syncFromApi();
      } catch (error) { setToast({ text: error instanceof Error ? error.message : "Proposal failed", ok: false }); setLoading(false); return; }
    } else {
      setProposalId(1042);
      setAuditEvents(current => [...current, { id: current.length + 1, actor: "Maya Chen", action: "proposal.created", entity_type: "proposal", entity_id: "1042", detail: `Created ${selectedOption.type} proposal for ${selectedOption.quantity} units. Inventory unchanged.`, created_at: new Date().toISOString() }]);
    }
    setWorkflow("proposed"); setLoading(false);
    setToast({ text: "Proposal created — inventory is unchanged", ok: true });
  };

  const approveProposal = async () => {
    if (!selected || !selectedOption || !proposalId) return;
    setLoading(true);
    if (connected) {
      try {
        await api(`/api/proposals/${proposalId}/approve`, postJson({ actor: "Maya Chen", idempotency_key: `ui-${proposalId}-approval` }));
        await syncFromApi();
      } catch (error) {
        setToast({ text: error instanceof Error ? error.message : "Approval failed", ok: false });
        await syncFromApi().catch(() => {});
        setLoading(false); return;
      }
      setWorkflow("approved"); setLoading(false); setToast({ text: `${selected.code} response approved`, ok: true });
      return;
    }
    const previousShortage = selected.shortage;
    setDashboard(current => ({
      ...current,
      metrics: { ...current.metrics, orders_at_risk: current.metrics.orders_at_risk - 1, units_exposed: current.metrics.units_exposed - previousShortage, recovered: current.metrics.recovered + 1 },
      orders: current.orders.map(order => order.id === selected.id ? { ...order, status: "recovered", affected: false, available_by_promise: order.quantity, shortage: 0, projected_date: selectedOption.expected_arrival, late_days: 0, sources: [...order.sources.filter(source => source.status !== "delayed"), { type: selectedOption.type, code: selectedOption.type === "transfer" ? "TRN-1042" : "EXP-1042", quantity: selectedOption.quantity, arrival: selectedOption.expected_arrival, status: "confirmed", supplier: selectedOption.title.replace("Expedite from ", "") }] } : order),
    }));
    const now = new Date().toISOString();
    setAuditEvents(current => [...current,
      { id: current.length + 1, actor: "Maya Chen", action: "approval.attempted", entity_type: "proposal", entity_id: String(proposalId), detail: "Availability and timing constraints rechecked.", created_at: now },
      { id: current.length + 2, actor: "Maya Chen", action: "inventory.reserved", entity_type: "inventory", entity_id: selectedOption.source, detail: `Reserved ${selectedOption.quantity} units; created ${selectedOption.type === "transfer" ? "TRN-1042" : "EXP-1042"}.`, created_at: now },
      { id: current.length + 3, actor: "Maya Chen", action: "proposal.approved", entity_type: "order", entity_id: selected.code, detail: "Order outlook recovered and dependency plan updated.", created_at: now },
    ]);
    setWorkflow("approved"); setLoading(false); setToast({ text: `${selected.code} recovered — action approved`, ok: true });
  };

  const resetScenario = async () => {
    if (connected) {
      try { await api("/api/scenario/reset", { method: "POST" }); await syncFromApi(); }
      catch (error) { setToast({ text: error instanceof Error ? error.message : "Reset failed", ok: false }); return; }
    } else { setDashboard(initialDashboard); setAuditEvents(initialAudit); }
    setSelectedId(null); setExplanation(null); setSelectedOption(null); setWorkflow("idle"); setProposalId(null); setView("tower"); setToast({ text: "Scenario reset to baseline", ok: true });
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => { setSelectedId(null); setView("tower"); }} aria-label="SupplyScope home"><Mark /><span>Supply<span>Scope</span></span></button>
        <nav aria-label="Primary navigation">
          <button className={view === "tower" ? "active" : ""} onClick={() => { setView("tower"); setSelectedId(null); }}>Control tower</button>
          <button className={view === "audit" ? "active" : ""} onClick={() => { setView("audit"); setSelectedId(null); }}>Decision log <em>{auditEvents.length}</em></button>
          <button className={view === "model" ? "active" : ""} onClick={() => { setView("model"); setSelectedId(null); }}>Data map</button>
        </nav>
        <div className="top-actions"><span className={`connection ${connected ? "live" : "demo"}`}><i />{connected ? "API live" : "Demo mode"}</span><span className="operator"><b>MC</b><span>Maya Chen<small>Response lead</small></span></span></div>
      </header>

      {view === "tower" && !selected && <DashboardView dashboard={dashboard} onOpen={openOrder} onReset={resetScenario} onViewLog={() => setView("audit")} />}
      {view === "tower" && selected && <OrderDetail order={selected} tab={detailTab} setTab={setDetailTab} onBack={() => setSelectedId(null)} explanation={explanation} onAsk={askWhy} loading={loading} workflow={workflow} option={selectedOption} setOption={(choice) => { setSelectedOption(choice); setWorkflow("review"); }} onCreate={createProposal} onApprove={approveProposal} />}
      {view === "audit" && <AuditView events={auditEvents} />}
      {view === "model" && <DataMapView />}
      {toast && <div className={`toast ${toast.ok ? "" : "error"}`} role={toast.ok ? "status" : "alert"}><span>{toast.ok ? "✓" : "!"}</span>{toast.text}</div>}
    </div>
  );
}

function DashboardView({ dashboard, onOpen, onReset, onViewLog }: { dashboard: Dashboard; onOpen: (order: Order) => void; onReset: () => void; onViewLog: () => void }) {
  const riskOrders = dashboard.orders.filter(order => order.affected);
  const covered = dashboard.orders.filter(order => !order.affected);
  const disruption = dashboard.disruptions[0];
  return <main className="page dashboard-page">
    <section className="page-heading">
      <div><p className="eyebrow">Monday · September 28</p><h1>Good morning, Maya.</h1><p>Here’s what changed across the network since your last review.</p></div>
      <button className="secondary-button" onClick={onReset}><span>↻</span> Reset scenario</button>
    </section>
    <section className="metric-grid" aria-label="Network summary">
      <Metric label="Active disruptions" value={dashboard.metrics.active_disruptions} trend="1 new today" tone="risk" glyph="!" />
      <Metric label="Orders at risk" value={dashboard.metrics.orders_at_risk} trend={`${dashboard.metrics.units_exposed} units exposed`} tone="risk" glyph="↗" />
      <Metric label="Recovered today" value={dashboard.metrics.recovered} trend="Actions approved" tone="good" glyph="✓" />
      <Metric label="Network coverage" value="94%" trend="−2.4% from plan" tone="neutral" glyph="◫" />
    </section>
    {disruption && <section className="alert-strip">
      <div className="alert-icon">!</div><div><span>New disruption</span><strong>{disruption.summary}</strong><p>{disruption.code} · {disruption.shipment} · {disruption.delay_days}-day slip</p></div>
      {riskOrders[0] && <button onClick={() => onOpen(riskOrders[0])}>Review impact <span>→</span></button>}
    </section>}
    <div className="dashboard-grid">
      <section className="panel orders-panel">
        <div className="panel-title"><div><p className="eyebrow">Prioritized queue</p><h2>Orders needing attention</h2></div><span className="quiet-chip">Ranked by urgency</span></div>
        <div className="orders-head"><span>Order & customer</span><span>Supply gap</span><span>Promise</span><span>Impact</span><span>Urgency</span><span /></div>
        {riskOrders.map(order => <button className="order-row" onClick={() => onOpen(order)} key={order.id}>
          <span className="order-name"><b>{order.code}</b><small>{order.customer}</small></span>
          <span><b>{order.shortage} / {order.quantity}</b><small>{order.sku} units</small></span>
          <span><b>{prettyDate(order.promised_date, true)}</b><small>{order.facility_code}</small></span>
          <span className="impact"><b>+{order.late_days} days</b><small>{prettyDate(order.projected_date, true)} projected</small></span>
          <span className="urgency"><i style={{ "--fill": `${Math.min(order.urgency_score, 100)}%` } as React.CSSProperties} /><b className="capitalize">{order.priority}</b></span><span className="row-arrow">→</span>
        </button>)}
        {covered.length > 0 && <div className="covered-row"><span className="check-dot">✓</span><div><b>{`${covered.length} active ${covered.length === 1 ? "order is" : "orders are"} fully covered`}</b><small>{`${covered.map(order => order.code).join(", ")} ${covered.length === 1 ? "has enough on-hand inventory and is" : "have enough supply and are"} not included in the risk queue.`}</small></div></div>}
      </section>
      <aside className="side-stack">
        <section className="panel response-card"><p className="eyebrow">Response window</p><div className="donut"><span><b>6</b><small>days</small></span></div><h3>Act before Oct 04</h3><p>Approve a response before the transfer cutoff to protect the earliest promise.</p><div className="mini-scale"><i /><i /><i /><i /><i /><i /><i /></div><div className="scale-labels"><span>Today</span><span>Promise</span></div></section>
        <section className="panel recent-card"><div className="panel-title"><h3>Latest signals</h3><button onClick={onViewLog}>View log</button></div><ul><li><span className="event-dot risk" /><div><b>Shipment delay detected</b><small>INB-7392 · 8:02 AM</small></div></li><li><span className="event-dot good" /><div><b>Inventory sync complete</b><small>2 facilities · 7:58 AM</small></div></li><li><span className="event-dot neutral" /><div><b>Scenario baseline loaded</b><small>Synthetic data · 7:55 AM</small></div></li></ul></section>
      </aside>
    </div>
  </main>;
}

function Metric({ label, value, trend, tone, glyph }: { label: string; value: string | number; trend: string; tone: string; glyph: string }) {
  return <article className="metric-card"><div className={`metric-glyph ${tone}`}>{glyph}</div><div><span>{label}</span><strong>{value}</strong><small className={tone}>{trend}</small></div></article>;
}

function OrderDetail({ order, tab, setTab, onBack, explanation, onAsk, loading, workflow, option, setOption, onCreate, onApprove }: { order: Order; tab: string; setTab: (tab: "responses" | "evidence" | "logic") => void; onBack: () => void; explanation: Explanation | null; onAsk: () => void; loading: boolean; workflow: string; option: Option | null; setOption: (option: Option) => void; onCreate: () => void; onApprove: () => void }) {
  const recovered = order.shortage === 0;
  return <main className="page detail-page">
    <button className="back-button" onClick={onBack}>← <span>Risk queue</span></button>
    <section className="detail-hero">
      <div><div className="title-line"><h1>{order.code}</h1><span className={`order-state ${recovered ? "recovered" : "at-risk"}`}>{recovered ? "Recovered" : "At risk"}</span><span className="priority">{order.priority} priority</span></div><p>{order.customer} · {order.sku_name} · Destination {order.facility_code}</p></div>
      <div className="promise-block"><span>Customer promise</span><strong>{prettyDate(order.promised_date)}</strong><small>{recovered ? `Protected by ${prettyDate(order.projected_date, true)}` : `Currently ${order.late_days} days at risk`}</small></div>
    </section>
    <section className="order-kpis">
      <article><span>Ordered</span><strong>{order.quantity}<small> units</small></strong><p>{order.sku}</p></article>
      <article><span>Available by promise</span><strong>{order.available_by_promise}<small> units</small></strong><p>{Math.round(order.available_by_promise / order.quantity * 100)}% covered</p></article>
      <article className={recovered ? "good" : "risk"}><span>{recovered ? "Shortage resolved" : "Supply shortfall"}</span><strong>{order.shortage}<small> units</small></strong><p>{recovered ? "Action applied" : "Needs response"}</p></article>
      <article><span>Projected fulfillment</span><strong className={recovered ? "good-text" : "risk-text"}>{prettyDate(order.projected_date, true)}</strong><p>{recovered ? "On time" : `+${order.late_days} days vs promise`}</p></article>
    </section>
    <section className="panel dependency-panel">
      <div className="panel-title"><div><p className="eyebrow">Record-level evidence</p><h2>Why this order is exposed</h2></div><span className="quiet-chip">Last calculated 8:04 AM</span></div>
      <div className="dependency-flow">
        <EvidenceCard label="Supplier" code="SUP-MER" title="Meridian Components" meta="Penang, MY" state="Watch" />
        <span className="flow-line"><b>40 units</b></span>
        <EvidenceCard label="Inbound shipment" code="INB-7392" title={recovered ? "Replanned" : "Delayed 9 days"} meta="Oct 01 → Oct 10" state="Delayed" risk />
        <span className="flow-line"><b>{order.shortage || 40} units</b></span>
        <EvidenceCard label="Inventory" code="EWR-01 · AX-440" title={`${order.available_by_promise} usable units`} meta="55 on hand · 45 reserved" state="Tight" />
        <span className="flow-line"><b>{order.quantity} needed</b></span>
        <EvidenceCard label="Customer order" code={order.code} title={`${order.quantity} units`} meta={`Promise ${prettyDate(order.promised_date, true)}`} state={recovered ? "Covered" : "At risk"} risk={!recovered} />
      </div>
    </section>
    <div className="detail-grid">
      <section className="panel decision-panel">
        <div className="tabbar"><button className={tab === "responses" ? "active" : ""} onClick={() => setTab("responses")}>Response options</button><button className={tab === "evidence" ? "active" : ""} onClick={() => setTab("evidence")}>Supporting records</button><button className={tab === "logic" ? "active" : ""} onClick={() => setTab("logic")}>Calculation</button></div>
        {tab === "responses" && <div className="option-list">
          {recovered && <div className="resolved-banner"><span>✓</span><div><b>Response applied successfully</b><p>{order.quantity} units are now covered by the approved plan. The original delayed allocation remains in the audit trail.</p></div></div>}
          {!recovered && order.options?.map((item, index) => <article className={`option-card ${item.status} ${option?.id === item.id ? "selected" : ""}`} key={item.id}>
            <div className="option-rank">{item.status === "on_time" ? index + 1 : "—"}</div><div className="option-main"><div><h3>{item.title}</h3><StatusPill status={item.status} /></div><p>{item.type === "transfer" ? "Reposition unreserved stock between facilities." : "Create a new supplier commitment for the gap."}</p><div className="option-facts"><span><small>Quantity</small><b>{item.quantity} units</b></span><span><small>Arrival</small><b>{prettyDate(item.expected_arrival, true)}</b></span><span><small>Promise impact</small><b>{item.delivery_impact}</b></span><span><small>Available</small><b>{item.available} units</b></span></div>{item.reason && <div className="option-reason"><b>Why unavailable:</b> {item.reason}</div>}</div><button disabled={item.status === "infeasible"} onClick={() => setOption(item)}>{option?.id === item.id ? "Selected" : item.status === "infeasible" ? "Unavailable" : "Review"}</button>
          </article>)}
        </div>}
        {tab === "evidence" && <div className="record-table"><div><span>Record</span><span>Role in calculation</span><span>Observed value</span></div><div><b>{order.code}</b><span>Demand + promise</span><span>{order.quantity} units · {prettyDate(order.promised_date, true)}</span></div><div><b>{order.sku}</b><span>Required item</span><span>{order.sku_name}</span></div>{order.sources.map(source => <div key={source.code}><b>{source.code}</b><span>{source.type === "inventory" ? "Ready allocation" : "Planned supply"}</span><span>{source.quantity} units · {prettyDate(source.arrival, true)}</span></div>)}</div>}
        {tab === "logic" && <div className="logic-view"><p>SupplyScope computes urgency in deterministic application code. The assistant never chooses quantities, feasibility, ranking, or approval outcomes.</p><div className="formula">{order.calculation.formula}</div><div className="score-parts"><span><small>Priority</small><b>{order.calculation.priority_weight}</b></span><i>+</i><span><small>Shortage</small><b>{Math.round(order.calculation.shortage_ratio * 35)}</b></span><i>+</i><span><small>Late days</small><b>{order.calculation.late_day_points}</b></span><i>+</i><span><small>Deadline</small><b>{order.calculation.deadline_pressure}</b></span><i>=</i><span className="total"><small>Urgency</small><b>{order.urgency_score}</b></span></div></div>}
      </section>
      <aside className="side-stack detail-side">
        <section className="panel assistant-card"><div className="assistant-title"><div className="spark">✦</div><div><p className="eyebrow">Grounded assistant</p><h3>Ask SupplyScope</h3></div></div>{!explanation ? <><p>Get a plain-language explanation tied directly to the records above.</p><button className="assistant-prompt" onClick={onAsk} disabled={loading}><span>“</span>Why is this order at risk?<b>→</b></button></> : <div className="answer"><p>{explanation.answer}</p><div className="source-links">Sources {explanation.links.map(link => <a key={link.label} href={link.href}>{link.label}</a>)}</div><small>{explanation.mode === "llm_grounded" ? "Model-rewritten from deterministic facts" : "Deterministic · No AI key required"}</small></div>}</section>
        {workflow !== "idle" && option && <section className={`panel approval-card ${workflow === "approved" ? "approved" : ""}`}>
          <div className="approval-step"><span>{workflow === "approved" ? "✓" : workflow === "proposed" ? "2" : "1"}</span><div><p className="eyebrow">{workflow === "review" ? "Step 1 of 2" : workflow === "proposed" ? "Step 2 of 2" : "Decision complete"}</p><h3>{workflow === "review" ? "Review proposal" : workflow === "proposed" ? "Approve action" : "Action approved"}</h3></div></div>
          <div className="proposal-summary"><span><small>Response</small><b>{option.type === "transfer" ? "Inventory transfer" : "Alternate supplier"}</b></span><span><small>Source</small><b>{option.source}</b></span><span><small>Quantity</small><b>{option.quantity} units</b></span><span><small>Expected</small><b>{prettyDate(option.expected_arrival, true)}</b></span></div>
          {workflow === "review" && <><div className="no-effect"><span>i</span>Creating this proposal will not change inventory.</div><button className="primary-button" onClick={onCreate} disabled={loading}>{loading ? "Creating…" : "Create proposal"}</button></>}
          {workflow === "proposed" && <><div className="recheck"><span>↻</span><div><b>Constraints will be rechecked</b><small>Availability, timing, and competing reservations.</small></div></div><button className="primary-button" onClick={onApprove} disabled={loading}>{loading ? "Rechecking…" : "Approve & apply"}</button><button className="text-button" onClick={onBack}>Keep pending</button></>}
          {workflow === "approved" && <div className="approved-message"><span>✓</span><div><b>Inventory reserved</b><small>Outlook and audit trail updated.</small></div></div>}
        </section>}
      </aside>
    </div>
  </main>;
}

function EvidenceCard({ label, code, title, meta, state, risk = false }: { label: string; code: string; title: string; meta: string; state: string; risk?: boolean }) {
  return <article className={`evidence-card ${risk ? "risk" : ""}`}><div><span>{label}</span><em>{state}</em></div><b>{code}</b><strong>{title}</strong><small>{meta}</small></article>;
}

function exportCsv(events: Audit[]) {
  // Prefix formula-leading cells so spreadsheet apps don't execute them.
  const cell = (value: string | number) => `"${String(value).replace(/^[=+\-@]/, "'$&").replaceAll('"', '""')}"`;
  const rows = [["time", "actor", "action", "entity_type", "entity_id", "detail"], ...events.map(e => [e.created_at, e.actor, e.action, e.entity_type, e.entity_id, e.detail])];
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([rows.map(row => row.map(cell).join(",")).join("\n")], { type: "text/csv" }));
  link.download = "supplyscope-decision-log.csv";
  link.click();
  URL.revokeObjectURL(link.href);
}

function AuditView({ events }: { events: Audit[] }) {
  return <main className="page"><section className="page-heading"><div><p className="eyebrow">Traceable by design</p><h1>Decision log</h1><p>Every proposal, check, inventory effect, and outcome in one immutable narrative.</p></div><button className="secondary-button" onClick={() => exportCsv(events)}>Export CSV</button></section><section className="panel audit-panel"><div className="audit-head"><span>Time</span><span>Actor</span><span>Action</span><span>Entity</span><span>Detail</span></div>{[...events].reverse().map(event => <div className="audit-row" key={`${event.id}-${event.action}`}><time>{new Date(event.created_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</time><span className="actor-cell"><b>{event.actor === "system" ? "SY" : "MC"}</b>{event.actor}</span><span><em className={event.action.includes("approved") || event.action.includes("reserved") ? "green" : event.action.includes("detected") ? "red" : "blue"}>{actionLabel(event.action)}</em></span><span><b>{event.entity_id}</b><small>{event.entity_type}</small></span><p>{event.detail}</p></div>)}</section></main>;
}

function DataMapView() {
  const nodes = ["Suppliers", "Supplier capabilities", "Facilities", "SKUs", "Inventory", "Inbound shipments", "Disruptions", "Orders", "Order lines", "Allocations", "Proposals", "Approvals", "Audit events"];
  return <main className="page"><section className="page-heading"><div><p className="eyebrow">Relational foundation</p><h1>Operational data map</h1><p>The exact records SupplyScope uses to detect impact, test responses, and apply decisions.</p></div><span className="schema-badge">13 entity types</span></section><section className="panel map-panel"><div className="map-core"><Mark /><b>SupplyScope</b><small>Deterministic services</small></div>{nodes.map((node, index) => <div className={`map-node n${index + 1}`} key={node}><span>{String(index + 1).padStart(2, "0")}</span><b>{node}</b></div>)}</section><section className="principles"><article><span>01</span><h3>Dependency-correct</h3><p>Only orders whose usable stock and planned supply miss the promise are surfaced.</p></article><article><span>02</span><h3>Approval-safe</h3><p>Proposals have no side effects. Approval rechecks constraints in a transaction.</p></article><article><span>03</span><h3>Assistant-grounded</h3><p>Explanations cite records; deterministic code owns every operational decision.</p></article></section></main>;
}
