const main = document.getElementById("main");
const refreshBtn = document.getElementById("refreshBtn");
const reportSelect = document.getElementById("reportSelect");
const toastEl = document.getElementById("toast");

let currentReport = null;
let inboxSummary = null;

const STATUS_LABEL = { green: "順調", yellow: "要注意", red: "危険" };
const KPI_STATUS = { good: "k-good", watch: "k-watch", bad: "k-bad", unknown: "" };
const TREND = { up: "▲", down: "▼", flat: "→", unknown: "—" };
const URGENCY = { high: "至急", medium: "今週中", low: "余裕あり" };
const PRIORITY = { high: "高", medium: "中", low: "低", A: "A", B: "B", C: "C" };
const EFFORT = { small: "小", medium: "中", large: "大" };
const SEVERITY = { high: "高", medium: "中", low: "低" };
const DECISION_LABEL = {
  pending: "未決", approved: "承認済み", rejected: "却下", deferred: "保留",
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function toast(message) {
  toastEl.textContent = message;
  toastEl.hidden = false;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toastEl.hidden = true; }, 3200);
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `通信に失敗しました (${res.status})`);
  }
  return res.json();
}

/* ---------- 各セクションの描画 ---------- */

function renderSummary(r) {
  const status = r.overall_status || "unknown";
  const sample = r.is_sample
    ? `<div class="db-sample-banner">これはサンプルレポートです。<b>data/inbox</b> に資料を置いて「レポートを更新」を押すと、実データの報告に切り替わります。</div>`
    : "";
  return `
    ${sample}
    <div class="db-summary status-${esc(status)}">
      <div class="db-summary-top">
        <span class="db-pill pill-${esc(status)}">${esc(STATUS_LABEL[status] || "判定不能")}</span>
        <span>${esc(r.period_label || "")}</span>
        <span>基準日 ${esc(r.report_date || "-")}</span>
      </div>
      <p class="db-headline">${esc(r.headline || "")}</p>
      <p class="db-reason">${esc(r.status_reason || "")}</p>
    </div>`;
}

function renderKpis(kpis) {
  if (!kpis.length) {
    return section("KPI", 0, `<p class="db-empty">KPIを算出できる資料がまだありません。財務資料をご提供ください。</p>`);
  }
  const cards = kpis.map((k) => `
    <div class="db-kpi ${KPI_STATUS[k.status] || ""}">
      <div class="db-kpi-label">${esc(k.label)}</div>
      <div class="db-kpi-value">${esc(k.value)}</div>
      <div class="db-kpi-meta">${esc(TREND[k.trend] || "—")}　目標: ${esc(k.target || "未設定")}</div>
      <div class="db-kpi-comment">${esc(k.comment)}<br><span class="db-kpi-meta">出典: ${esc(k.source || "不明")}</span></div>
    </div>`).join("");
  return section("KPI", kpis.length, `<div class="db-kpi-grid">${cards}</div>`, "数字は出典つき。「推定」はクロの補完値です");
}

function renderDecisions(r) {
  const decisions = r.decisions || [];
  if (!decisions.length) {
    return section("あなたの判断が必要なもの", 0, `<p class="db-empty">現時点でCEO決裁が必要な案件はありません。</p>`);
  }
  const cards = decisions.map((d) => {
    const decided = d.status && d.status !== "pending";
    const options = (d.options || []).map((o) => `
      <div class="db-option">
        <div class="db-option-label">${esc(o.label)}</div>
        <div class="db-option-row"><b>利点:</b> ${esc(o.pros)}</div>
        <div class="db-option-row"><b>難点:</b> ${esc(o.cons)}</div>
      </div>`).join("");
    const decidedBar = decided
      ? `<div class="db-decide-bar"><span class="db-pill pill-blue">${esc(DECISION_LABEL[d.status])}</span>
           <span class="db-kpi-meta">${esc(d.decided_at)}　${esc(d.decision_note)}</span>
           <button class="db-mini" data-act="pending" data-id="${esc(d.id)}">取り消す</button></div>`
      : `<div class="db-decide-bar">
           <input type="text" placeholder="判断の理由やメモ（任意）" data-note="${esc(d.id)}">
           <button class="db-mini approve" data-act="approved" data-id="${esc(d.id)}">承認</button>
           <button class="db-mini reject" data-act="rejected" data-id="${esc(d.id)}">却下</button>
           <button class="db-mini defer" data-act="deferred" data-id="${esc(d.id)}">保留</button>
         </div>`;
    return `
      <div class="db-card db-decision u-${esc(d.urgency || "high")} ${decided ? "decided" : ""}">
        <div class="db-card-head">
          <span class="db-card-title">${esc(d.title)}</span>
          <span class="db-pill pill-${d.urgency === "high" ? "red" : d.urgency === "medium" ? "yellow" : "gray"}">${esc(URGENCY[d.urgency] || "期限未定")}</span>
        </div>
        <div class="db-field"><div class="db-field-label">背景</div><div class="db-field-body">${esc(d.context)}</div></div>
        <div class="db-field"><div class="db-field-label">選択肢</div><div class="db-options">${options}</div></div>
        <div class="db-reco"><b>クロの推奨:</b> ${esc(d.recommendation)}</div>
        <div class="db-field"><div class="db-field-label">影響</div><div class="db-field-body">${esc(d.impact)}</div></div>
        <div class="db-field"><div class="db-field-label">期限 / CEOにお願いすること</div><div class="db-field-body">${esc(d.deadline)}　／　${esc(d.required_from_ceo)}</div></div>
        ${decidedBar}
      </div>`;
  }).join("");
  const pending = decisions.filter((d) => !d.status || d.status === "pending").length;
  return section("あなたの判断が必要なもの", decisions.length, cards, `未決 ${pending} 件`);
}

function renderImprovements(items) {
  if (!items.length) {
    return section("改善提案", 0, `<p class="db-empty">提案できる改善案がまだありません。</p>`);
  }
  const cards = items.map((i) => `
    <div class="db-card db-improve p-${esc(i.priority || "medium")}">
      <div class="db-card-head">
        <span class="db-card-title">${esc(i.title)}</span>
        <span class="db-pill pill-${i.priority === "high" ? "red" : i.priority === "medium" ? "yellow" : "gray"}">優先度 ${esc(PRIORITY[i.priority] || "-")}</span>
        <span class="db-pill pill-gray">工数 ${esc(EFFORT[i.effort] || "-")}</span>
      </div>
      <div class="db-field"><div class="db-field-label">課題</div><div class="db-field-body">${esc(i.problem)}</div></div>
      <div class="db-field"><div class="db-field-label">打ち手</div><div class="db-field-body">${esc(i.action)}</div></div>
      <div class="db-field"><div class="db-field-label">期待効果</div><div class="db-field-body">${esc(i.expected_effect)}</div></div>
      <div class="db-field"><div class="db-field-label">最初の一歩（担当: ${esc(i.owner)}）</div><div class="db-field-body">${esc(i.first_step)}</div></div>
    </div>`).join("");
  return section("改善提案", items.length, `<div class="db-two-col">${cards}</div>`);
}

function renderRisks(items) {
  if (!items.length) return "";
  const cards = items.map((k) => `
    <div class="db-card db-risk s-${esc(k.severity || "medium")}">
      <div class="db-card-head">
        <span class="db-card-title">${esc(k.title)}</span>
        <span class="db-pill pill-${k.severity === "high" ? "red" : "yellow"}">深刻度 ${esc(SEVERITY[k.severity] || "-")}</span>
      </div>
      <div class="db-field"><div class="db-field-body">${esc(k.detail)}</div></div>
      <div class="db-field"><div class="db-field-label">打てる手</div><div class="db-field-body">${esc(k.mitigation)}</div></div>
    </div>`).join("");
  return section("リスク・注意信号", items.length, `<div class="db-two-col">${cards}</div>`);
}

function renderDataNeeds(report, inbox) {
  const gaps = (report && report.data_gaps) || [];
  const reqs = (inbox && inbox.requirements) || [];
  const gapCards = gaps.map((g) => `
    <div class="db-req-item">
      <span class="db-req-mark">📌</span>
      <div class="db-req-body">
        <div class="db-req-title">${esc(g.title)}<span class="db-pill pill-${g.priority === "high" ? "red" : g.priority === "medium" ? "yellow" : "gray"}" style="margin-left:8px">優先 ${esc(PRIORITY[g.priority] || "-")}</span></div>
        <div class="db-req-why">${esc(g.why)}</div>
        <div class="db-req-how">置き場所・形式: ${esc(g.how_to_provide)}</div>
      </div>
    </div>`).join("");

  const reqCards = reqs.map((r) => `
    <div class="db-req-item ${r.satisfied ? "done" : ""}">
      <span class="db-req-mark">${r.satisfied ? "✅" : "⬜"}</span>
      <div class="db-req-body">
        <div class="db-req-title">${esc(r.title)}<span class="db-pill pill-${r.priority === "A" ? "red" : r.priority === "B" ? "yellow" : "gray"}" style="margin-left:8px">${esc(r.priority)}</span></div>
        <div class="db-req-why">${esc(r.why)}</div>
        <div class="db-req-how">${esc(r.format)}　→　<code>${esc(r.drive || `data/inbox/${r.category}/`)}</code>　（${esc(r.cadence)}）<br>取り出し方: ${esc(r.how_to_export)}</div>
        ${r.satisfied ? `<div class="db-req-how">受領済み: ${r.matched_files.map((f) => `<code>${esc(f)}</code>`).join(" ")}</div>` : ""}
      </div>
    </div>`).join("");

  const progress = inbox
    ? `<p class="db-progress">チェックリスト達成: <b>${inbox.satisfied_count} / ${inbox.requirement_count}</b>　（受領ファイル ${inbox.file_count} 件）</p>`
    : "";

  const gapBlock = gaps.length
    ? `<h3 style="font-size:14px;margin:4px 0 8px">今回のレポートで足りなかったもの</h3><div class="db-req">${gapCards}</div>`
    : "";

  return section(
    "クロが待っている資料",
    reqs.filter((r) => !r.satisfied).length,
    `${progress}${gapBlock}<h3 style="font-size:14px;margin:18px 0 8px">資料チェックリスト</h3><div class="db-req">${reqCards}</div>`,
    "未提供の件数を表示しています"
  );
}

function section(title, count, body, note) {
  return `
    <section class="db-section">
      <div class="db-section-head">
        <h2>${esc(title)}</h2>
        <span class="db-count">${count} 件</span>
        ${note ? `<span class="db-section-note">${esc(note)}</span>` : ""}
      </div>
      ${body}
    </section>`;
}

function renderFooter(r) {
  const meta = r._meta || {};
  const files = (meta.source_files || []).length;
  return `
    <section class="db-section">
      <div class="db-section-head"><h2>クロからの注記</h2></div>
      <div class="db-notes">${esc(r.notes_for_ceo || "特記事項はありません。")}</div>
      <p class="db-meta">
        レポートID: ${esc(r.report_id || "-")}　/　生成: ${esc(r.generated_at || "-")}
        ${meta.model ? `　/　モデル: ${esc(meta.model)}` : ""}　/　参照ファイル: ${files} 件
      </p>
    </section>`;
}

/* ---------- 全体描画 ---------- */

function render() {
  if (!currentReport) {
    main.innerHTML = `<p class="db-empty">レポートがありません。「レポートを更新」を押してください。</p>`;
    return;
  }
  const r = currentReport;
  main.innerHTML = [
    renderSummary(r),
    renderDecisions(r),
    renderKpis(r.kpis || []),
    renderImprovements(r.improvements || []),
    renderRisks(r.risks || []),
    renderDataNeeds(r, inboxSummary),
    renderFooter(r),
  ].join("");
}

function renderReportOptions(reports) {
  if (!reports.length) {
    reportSelect.innerHTML = `<option>レポート未生成</option>`;
    reportSelect.disabled = true;
    return;
  }
  reportSelect.disabled = false;
  reportSelect.innerHTML = reports
    .map((r) => `<option value="${esc(r.report_id)}">${esc(r.report_date)} ${esc(r.headline.slice(0, 22))}</option>`)
    .join("");
  if (currentReport && currentReport.report_id) reportSelect.value = currentReport.report_id;
}

/* ---------- イベント ---------- */

main.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-act]");
  if (!button || !currentReport) return;
  if (currentReport.is_sample) {
    toast("サンプルレポートでは決裁を記録できません。");
    return;
  }
  const decisionId = button.dataset.id;
  const note = main.querySelector(`input[data-note="${CSS.escape(decisionId)}"]`);
  button.disabled = true;
  try {
    await api(`/api/dashboard/decisions/${encodeURIComponent(decisionId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        report_id: currentReport.report_id,
        status: button.dataset.act,
        note: note ? note.value : "",
      }),
    });
    toast(`「${DECISION_LABEL[button.dataset.act]}」として記録しました。`);
    currentReport = await api(`/api/dashboard/reports/${encodeURIComponent(currentReport.report_id)}`);
    render();
  } catch (err) {
    toast(err.message);
    button.disabled = false;
  }
});

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  refreshBtn.textContent = "クロが資料を読んでいます...";
  try {
    currentReport = await api("/api/dashboard/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    inboxSummary = await api("/api/dashboard/inbox");
    renderReportOptions((await api("/api/dashboard/reports")).reports);
    render();
    toast("レポートを更新しました。");
  } catch (err) {
    toast(err.message);
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = "レポートを更新";
  }
});

reportSelect.addEventListener("change", async () => {
  try {
    currentReport = await api(`/api/dashboard/reports/${encodeURIComponent(reportSelect.value)}`);
    render();
  } catch (err) {
    toast(err.message);
  }
});

(async function init() {
  try {
    const [report, inbox, list] = await Promise.all([
      api("/api/dashboard/latest").catch(() => null),
      api("/api/dashboard/inbox").catch(() => null),
      api("/api/dashboard/reports").catch(() => ({ reports: [] })),
    ]);
    currentReport = report;
    inboxSummary = inbox;
    renderReportOptions(list.reports || []);
    render();
  } catch (err) {
    main.innerHTML = `<p class="db-empty">${esc(err.message)}</p>`;
  }
})();
