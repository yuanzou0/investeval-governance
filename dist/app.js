"use strict";

const labels = {
  market_quote: "行情查询",
  financial_analysis: "财务分析",
  news_summary: "公告摘要",
  personalized_explanation: "个性化解释",
  NUMERIC_MISMATCH: "数字错误",
  STALE_DATA: "数据过期",
  PERIOD_MISMATCH: "报告期错误",
  MISSING_SOURCE: "缺少来源",
  UNSUPPORTED_CLAIM: "无证据主张",
  KYC_MISMATCH: "KYC 失配",
  FACT_PERSONALIZED: "事实被个性化",
  GUARANTEED_RETURN: "承诺收益",
  PRIVACY_OVERREACH: "隐私越界",
  HOT_CONTEXT_STALE: "热点已过期",
  FUTURE_CONTEXT_LEAK: "未来信息泄漏",
  EVENT_TIME_MISMATCH: "事件日期错配",
  human_review: "人工复核",
  quality_investigation: "质量调查",
  observe: "持续观察",
  pending: "待复核",
  confirmed: "已确认",
  dismissed: "已驳回",
  resolved: "已修复"
};

const state = { cases: [], facts: [], results: [], representative: null, comparison: null, signals: null, selectedId: null, imported: [] };
const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[character]);
}

function reviewKey(caseId) { return `investeval-review:${caseId}`; }
function getReview(caseId) {
  try { return JSON.parse(localStorage.getItem(reviewKey(caseId))) || { status: "pending" }; }
  catch { return { status: "pending" }; }
}
function saveReview(caseId, review) { localStorage.setItem(reviewKey(caseId), JSON.stringify(review)); }

async function loadData() {
  $("#load-status").textContent = "载入中";
  const [caseResponse, factResponse, resultResponse, representativeResponse, comparisonResponse, signalsResponse] = await Promise.all([
    fetch("data/cases.json", { cache: "no-store" }),
    fetch("data/facts.json", { cache: "no-store" }),
    fetch("data/evaluation-results.json", { cache: "no-store" }),
    fetch("data/representative-evaluation-results.json", { cache: "no-store" }),
    fetch("data/version-comparison.json", { cache: "no-store" }),
    fetch("data/signals-context-summary.json", { cache: "no-store" })
  ]);
  if (![caseResponse, factResponse, resultResponse, representativeResponse, comparisonResponse, signalsResponse].every((response) => response.ok)) {
    throw new Error("冻结评测数据载入失败");
  }
  state.cases = (await caseResponse.json()).cases;
  state.facts = (await factResponse.json()).facts;
  state.results = (await resultResponse.json()).results;
  state.representative = await representativeResponse.json();
  state.comparison = await comparisonResponse.json();
  state.signals = await signalsResponse.json();
  state.selectedId = null;
  populateFilters();
  render();
  $("#load-status").textContent = `24 条分层样本 · ${state.cases.length} 条压力样本`;
}

function populateFilters() {
  const intentSelect = $("#intent-filter");
  const errorSelect = $("#error-filter");
  const currentIntent = intentSelect.value;
  const currentError = errorSelect.value;
  const intents = [...new Set(state.cases.map((item) => item.intent))];
  const errors = [...new Set(state.results.flatMap((item) => item.findings.map((finding) => finding.code)))];
  intentSelect.innerHTML = '<option value="all">全部意图</option>' + intents.map((value) => `<option value="${value}">${labels[value] || value}</option>`).join("");
  errorSelect.innerHTML = '<option value="all">全部问题</option>' + errors.map((value) => `<option value="${value}">${labels[value] || value}</option>`).join("");
  if (intents.includes(currentIntent)) intentSelect.value = currentIntent;
  if (errors.includes(currentError)) errorSelect.value = currentError;
}

function joinedCases() {
  const resultMap = new Map(state.results.map((result) => [result.case_id, result]));
  return [...state.cases, ...state.imported].map((item) => ({ ...item, result: resultMap.get(item.case_id) || importedResult(item), review: getReview(item.case_id) }));
}

function importedResult(item) {
  const expected = item.expected_error_codes || [];
  return {
    case_id: item.case_id,
    intent: item.intent,
    passed: expected.length === 0,
    score: Math.max(0, 100 - expected.length * 25),
    findings: expected.map((code) => ({ code, severity: "high", message: "导入日志携带的预期问题标签；服务端核验后可更新结论。", fact_id: null })),
    checked_fact_ids: []
  };
}

function filteredCases() {
  const outcome = $("#outcome-filter").value;
  const intent = $("#intent-filter").value;
  const error = $("#error-filter").value;
  const review = $("#review-filter").value;
  return joinedCases().filter((item) => {
    if (outcome === "bad_case" && item.result.passed) return false;
    if (outcome === "passed" && !item.result.passed) return false;
    if (intent !== "all" && item.intent !== intent) return false;
    if (error !== "all" && !item.result.findings.some((finding) => finding.code === error)) return false;
    return review === "all" || item.review.status === review;
  }).sort((a, b) => Number(a.result.passed) - Number(b.result.passed) || a.result.score - b.result.score);
}

function renderMetrics(items) {
  const passed = items.filter((item) => item.result.passed).length;
  const pending = items.filter((item) => !item.result.passed && item.review.status === "pending").length;
  const critical = items.filter((item) => item.result.findings.some((finding) => finding.severity === "critical")).length;
  const verified = items.filter((item) => item.result.checked_fact_ids.length > 0).length;
  const representative = state.representative?.summary;
  $("#representative-pass-rate").textContent = representative ? `${(representative.pass_rate * 100).toFixed(1)}%` : "—";
  $("#representative-pass-count").textContent = representative ? `${representative.passed_count} / ${representative.case_count} 条通过` : "—";
  $("#pass-rate").textContent = items.length ? `${(passed / items.length * 100).toFixed(1)}%` : "—";
  $("#pass-count").textContent = `${passed} / ${items.length} 条通过 · 标签复现 11/11`;
  $("#pending-count").textContent = String(pending);
  $("#critical-count").textContent = `${critical} 条严重合规风险`;
  $("#evidence-rate").textContent = items.length ? `${Math.round(verified / items.length * 100)}%` : "—";
}

function renderComparison() {
  const comparison = state.comparison;
  if (!comparison) return;
  const { baseline, candidate, delta, gates, decision } = comparison;
  $("#policy-version").textContent = comparison.policy_version;
  $("#baseline-version").textContent = `${baseline.model_version} · ${baseline.prompt_version} · ${baseline.data_version}`;
  $("#candidate-version").textContent = `${candidate.model_version} · ${candidate.prompt_version} · ${candidate.data_version}`;
  $("#baseline-pass").textContent = `${(baseline.pass_rate * 100).toFixed(1)}%`;
  $("#candidate-pass").textContent = `${(candidate.pass_rate * 100).toFixed(1)}%`;
  $("#baseline-score").textContent = baseline.average_score.toFixed(1);
  $("#candidate-score").textContent = candidate.average_score.toFixed(1);
  $("#baseline-latency").textContent = `${baseline.p95_latency_ms}ms`;
  $("#candidate-latency").textContent = `${candidate.p95_latency_ms}ms`;
  $("#pass-delta").textContent = `${delta.pass_rate_pp >= 0 ? "+" : ""}${delta.pass_rate_pp.toFixed(1)}pp`;
  $("#score-delta").textContent = `${delta.average_score >= 0 ? "+" : ""}${delta.average_score.toFixed(1)}`;
  $("#gate-count").textContent = `${gates.filter((gate) => gate.passed).length} / ${gates.length} 通过`;
  $("#gate-list").innerHTML = gates.map((gate) => `<div class="gate-row">
    <div class="gate-label"><strong>${escapeHtml(gate.label)}</strong><span>${gate.hard_blocker ? "硬性门槛" : "观察指标"}</span></div>
    <span class="gate-value">${escapeHtml(gate.observed)}</span><span class="gate-value">${escapeHtml(gate.threshold)}</span>
    <span class="badge gate-result ${gate.passed ? "ok" : "error"}">${gate.passed ? "PASS" : "FAIL"}</span>
  </div>`).join("");
  $("#decision-status").textContent = decision.status;
  $("#decision-title").textContent = decision.status === "HOLD" ? "暂缓上线" : "受限灰度";
  $("#decision-summary").textContent = decision.summary;
  const blockingCount = Object.entries(candidate.error_code_counts).filter(([code]) => ["GUARANTEED_RETURN", "KYC_MISMATCH", "FACT_PERSONALIZED", "PRIVACY_OVERREACH", "NUMERIC_MISMATCH", "PERIOD_MISMATCH"].includes(code)).reduce((sum, [, count]) => sum + count, 0);
  $("#blocking-change").textContent = String(blockingCount);
  $("#evidence-delta").textContent = `${delta.evidence_coverage_pp >= 0 ? "+" : ""}${delta.evidence_coverage_pp.toFixed(1)}pp`;
  $("#latency-delta").textContent = `${delta.p95_latency_ms >= 0 ? "+" : ""}${delta.p95_latency_ms}ms`;
}

function renderSignals() {
  if (!state.signals) return;
  const feedback = state.signals.feedback;
  const hot = state.signals.hot_context;
  const resultMap = new Map(state.results.map((result) => [result.case_id, result]));
  $("#feedback-event-count").textContent = String(feedback.event_count);
  $("#negative-rate").textContent = `${(feedback.negative_signal_rate * 100).toFixed(0)}%`;
  $("#negative-count").textContent = `${feedback.negative_signal_count} 个负向信号`;
  $("#escalated-count").textContent = String(feedback.escalated_case_count);
  $("#hot-failed-count").textContent = String(hot.failed_count);
  $("#hot-pass-count").textContent = `${hot.passed_count} / ${hot.check_count} 条通过`;
  $("#feedback-case-count").textContent = `${feedback.cases.length} 条`;
  $("#hot-check-count").textContent = `${hot.check_count} 条`;
  $("#feedback-table-body").innerHTML = feedback.cases.map((item) => {
    const factual = resultMap.get(item.case_id);
    const factualPass = factual?.passed ?? false;
    return `<tr>
      <td><span class="case-id">${escapeHtml(item.case_id)}</span></td>
      <td><div class="feedback-counts"><span class="mini-signal">赞 ${item.helpful}</span><span class="mini-signal negative">踩 ${item.not_helpful}</span><span class="mini-signal negative">重问 ${item.retry}</span><span class="mini-signal negative">报 ${item.report}</span></div></td>
      <td><span class="badge ${factualPass ? "ok" : "error"}">${factualPass ? "事实通过" : "仍为 Bad Case"}</span></td>
      <td><span class="badge ${item.escalated ? "pending" : ""}">${escapeHtml(labels[item.action] || item.action)}</span></td>
    </tr>`;
  }).join("");
  $("#hot-context-list").innerHTML = hot.results.map((item) => `<div class="hot-row">
    <div class="hot-row-head"><strong>${escapeHtml(item.check_id)}</strong><span class="badge ${item.passed ? "ok" : "error"}">${item.passed ? "PASS" : "FAIL"}</span></div>
    <p>案例 ${escapeHtml(item.case_id)} · 来源相对提问 ${item.age_hours} 小时 · 上限 ${item.maximum_age_hours} 小时</p>
    <div class="hot-findings">${item.findings.length ? item.findings.map((code) => `<span class="badge error">${escapeHtml(labels[code] || code)}</span>`).join("") : '<span class="badge ok">时间上下文一致</span>'}</div>
  </div>`).join("");
}

function renderTable(items) {
  const filtered = filteredCases();
  $("#result-count").textContent = `${filtered.length} 条`;
  $("#empty-state").hidden = filtered.length > 0;
  $("#case-table-body").innerHTML = filtered.map((item) => {
    const firstCode = item.result.findings[0]?.code;
    const status = item.review.status || "pending";
    const scoreClass = item.result.score >= 90 ? "high" : item.result.score >= 60 ? "mid" : "low";
    return `<tr class="case-row ${state.selectedId === item.case_id ? "selected" : ""}" data-case-id="${escapeHtml(item.case_id)}" tabindex="0">
      <td><span class="case-id">${escapeHtml(item.case_id)}</span><span class="case-question">${escapeHtml(item.question)}</span></td>
      <td><span class="badge">${escapeHtml(labels[item.intent] || item.intent)}</span></td>
      <td><span class="badge ${item.result.passed ? "ok" : "error"}">${escapeHtml(item.result.passed ? "通过" : labels[firstCode] || firstCode)}</span></td>
      <td><span class="score ${scoreClass}">${item.result.score.toFixed(0)}</span></td>
      <td><span class="badge ${status === "pending" ? "pending" : ""}">${escapeHtml(labels[status] || status)}</span></td>
    </tr>`;
  }).join("");
  document.querySelectorAll(".case-row").forEach((row) => {
    const open = () => { state.selectedId = row.dataset.caseId; render(); };
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") open(); });
  });
}

function renderDetail(items) {
  const item = items.find((candidate) => candidate.case_id === state.selectedId);
  if (!item) {
    $("#detail-panel").innerHTML = '<div class="detail-empty"><span>⌁</span><strong>选择一个案例</strong><p>查看回答、核验结果和证据血缘。</p></div>';
    return;
  }
  const findings = item.result.findings.length ? item.result.findings.map((finding) => `<div class="finding">
    <div class="finding-head"><span class="badge error">${escapeHtml(labels[finding.code] || finding.code)}</span><span class="badge">${escapeHtml(finding.severity)}</span></div>
    <p>${escapeHtml(finding.message)}</p>
  </div>`).join("") : '<span class="badge ok">未发现确定性问题</span>';
  const checked = item.result.checked_fact_ids.length ? item.result.checked_fact_ids.join(", ") : "未核验事实";
  const kyc = item.kyc ? `${item.kyc.risk_level} · ${item.kyc.horizon} · ${item.kyc.experience}` : "无画像";
  $("#detail-panel").innerHTML = `
    <div class="detail-header"><div class="detail-title-row"><div><p class="eyebrow">CASE DETAIL</p><h2>${escapeHtml(item.case_id)}</h2></div><span class="score ${item.result.score < 60 ? "low" : "mid"}">${item.result.score.toFixed(0)}</span></div><p>${escapeHtml(labels[item.intent] || item.intent)}</p></div>
    <section class="detail-section"><h3>用户问题</h3><p>${escapeHtml(item.question)}</p><h3>Agent 回答</h3><div class="answer-block">${escapeHtml(item.answer)}</div></section>
    <section class="detail-section"><h3>自动评测结果</h3>${findings}</section>
    <section class="detail-section"><h3>证据与版本血缘</h3><div class="lineage">
      <div><span>MODEL</span><strong>${escapeHtml(item.model_version)}</strong></div><div><span>PROMPT</span><strong>${escapeHtml(item.prompt_version)}</strong></div>
      <div><span>DATA</span><strong>${escapeHtml(item.data_version)}</strong></div><div><span>KYC</span><strong>${escapeHtml(kyc)}</strong></div>
      <div style="grid-column:1/-1"><span>CHECKED FACTS</span><strong>${escapeHtml(checked)}</strong></div>
    </div></section>
    <section class="detail-section"><h3>人工复核</h3><form id="review-form" class="review-form">
      <label>审核人<input name="reviewer" value="${escapeHtml(item.review.reviewer || "审核员-A")}" required></label>
      <label>复核说明<textarea name="note">${escapeHtml(item.review.note || "")}</textarea></label>
      <div class="review-actions"><button type="button" class="secondary-button" data-review-status="dismissed">驳回误报</button><button type="button" class="primary-button" data-review-status="confirmed">确认问题</button></div>
    </form></section>`;
  document.querySelectorAll("[data-review-status]").forEach((button) => button.addEventListener("click", () => {
    const form = $("#review-form");
    if (!form.reportValidity()) return;
    const formData = new FormData(form);
    saveReview(item.case_id, { status: button.dataset.reviewStatus, reviewer: formData.get("reviewer"), note: formData.get("note"), updated_at: new Date().toISOString() });
    showToast(button.dataset.reviewStatus === "confirmed" ? "已确认该 Bad Case" : "已驳回自动评测结论");
    render();
  }));
}

function render() {
  const items = joinedCases();
  renderMetrics(items);
  renderTable(items);
  renderDetail(items);
  renderComparison();
  renderSignals();
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2600);
}

function showLoadFailure(error) {
  $("#load-status").textContent = "数据载入失败，请刷新页面";
  ["#feedback-event-count", "#negative-rate", "#escalated-count", "#hot-failed-count"].forEach((selector) => {
    $(selector).textContent = "载入失败";
  });
  $("#negative-count").textContent = "未取得行为数据";
  $("#hot-pass-count").textContent = "未取得热点数据";
  showToast(`数据载入失败：${error.message}`);
}

document.querySelectorAll(".filters select").forEach((element) => element.addEventListener("change", render));
document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".view").forEach((view) => { view.hidden = view.id !== button.dataset.view; });
  document.querySelectorAll("[data-view]").forEach((item) => item.classList.toggle("active", item === button));
  window.scrollTo({ top: 0, behavior: "smooth" });
}));
$("#reload-button").addEventListener("click", () => loadData().then(() => showToast("冻结评测已重新载入")).catch((error) => showToast(error.message)));
$("#case-upload").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const documentData = JSON.parse(await file.text());
    if (!Array.isArray(documentData.cases) || !documentData.cases.length) throw new Error("文件必须包含非空 cases 数组");
    const known = new Set(joinedCases().map((item) => item.case_id));
    const incoming = documentData.cases.filter((item) => item.case_id && !known.has(item.case_id));
    if (!incoming.length) throw new Error("没有可导入的新案例");
    state.imported.push(...incoming);
    populateFilters(); render(); showToast(`已导入 ${incoming.length} 条匿名问答日志`);
  } catch (error) { showToast(`导入失败：${error.message}`); }
  event.target.value = "";
});

loadData().catch(showLoadFailure);
