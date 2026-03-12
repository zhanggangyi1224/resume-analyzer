import { createFallbackMockPayload } from "./mock-data.js";

const apiBaseInput = document.getElementById("apiBase");
const resumeFileInput = document.getElementById("resumeFile");
const filePicker = document.getElementById("filePicker");
const fileNameEl = document.getElementById("fileName");
const jobDescriptionInput = document.getElementById("jobDescription");
const parseBtn = document.getElementById("parseBtn");
const extractBtn = document.getElementById("extractBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusText = document.getElementById("statusText");
const overviewEl = document.getElementById("overview");
const resultGrid = document.getElementById("resultGrid");
const parseCard = document.getElementById("parseCard");
const parseView = document.getElementById("parseView");
const extractCard = document.getElementById("extractCard");
const extractionView = document.getElementById("extractionView");
const matchCard = document.getElementById("matchCard");
const matchView = document.getElementById("matchView");
let selectedFile = null;

const queryApi = new URLSearchParams(window.location.search).get("api");
const storedApi = localStorage.getItem("resumeAnalyzerApiBase");
apiBaseInput.value = normalizeApiBase(queryApi || storedApi || "http://127.0.0.1:8000/api/v1");

apiBaseInput.addEventListener("change", () => {
  apiBaseInput.value = normalizeApiBase(apiBaseInput.value);
  localStorage.setItem("resumeAnalyzerApiBase", apiBaseInput.value);
});

parseBtn.addEventListener("click", () => runWithPdf("/resumes/parse", false, "parse"));
extractBtn.addEventListener("click", () => runWithPdf("/resumes/extract", false, "extract"));
analyzeBtn.addEventListener("click", () => runWithPdf("/resumes/analyze", true, "analyze"));
resumeFileInput.addEventListener("change", onFileSelected);
enableDragAndDropUpload();

function onFileSelected() {
  const file = resumeFileInput.files?.[0];
  applySelectedFile(file);
}

function enableDragAndDropUpload() {
  const prevent = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  ["dragenter", "dragover"].forEach((eventName) => {
    filePicker.addEventListener(eventName, (event) => {
      prevent(event);
      filePicker.classList.add("is-dragging");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    filePicker.addEventListener(eventName, (event) => {
      prevent(event);
      filePicker.classList.remove("is-dragging");
    });
  });

  filePicker.addEventListener("drop", (event) => {
    const droppedFiles = event.dataTransfer?.files;
    if (!droppedFiles || droppedFiles.length === 0) {
      return;
    }

    if (droppedFiles.length > 1) {
      setStatus("loading", "仅支持单个 PDF，已使用第一个文件");
    }

    const file = droppedFiles[0];
    assignFileToInput(file);
    applySelectedFile(file);
  });

  ["dragover", "drop"].forEach((eventName) => {
    window.addEventListener(eventName, prevent);
  });
}

function assignFileToInput(file) {
  try {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    resumeFileInput.files = transfer.files;
  } catch (_error) {
    // ignore: some browsers may block programmatic files assignment
  }
}

function applySelectedFile(file) {
  if (!file) {
    selectedFile = null;
    filePicker.classList.remove("has-file");
    fileNameEl.textContent = "未选择文件";
    return;
  }

  if (!file.name.toLowerCase().endsWith(".pdf")) {
    selectedFile = null;
    resumeFileInput.value = "";
    filePicker.classList.remove("has-file");
    fileNameEl.textContent = "未选择文件";
    setStatus("error", "仅支持 PDF 文件");
    return;
  }

  selectedFile = file;
  filePicker.classList.add("has-file");
  fileNameEl.textContent = `${file.name} (${formatFileSize(file.size)})`;
}

function normalizeApiBase(base) {
  return String(base || "").trim().replace(/\/$/, "");
}

function setStatus(type, message) {
  statusText.className = `status ${type}`;
  statusText.textContent = message;
}

function setButtons(disabled) {
  [parseBtn, extractBtn, analyzeBtn].forEach((btn) => {
    btn.disabled = disabled;
  });
}

async function runWithPdf(endpoint, includeJobDescription, mode) {
  const file = selectedFile || resumeFileInput.files?.[0];
  if (!file) {
    setStatus("error", "请先选择一个 PDF 简历文件");
    return;
  }
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    setStatus("error", "仅支持 PDF 文件");
    return;
  }

  const apiBase = normalizeApiBase(apiBaseInput.value);
  if (!apiBase) {
    setStatus("error", "请填写 Backend API Base");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  const jdText = jobDescriptionInput.value.trim();

  if (includeJobDescription) {
    if (jdText) {
      formData.append("job_description", jdText);
    }
  }

  setStatus("loading", "请求处理中，请稍候...");
  setButtons(true);

  try {
    const response = await fetch(`${apiBase}${endpoint}`, {
      method: "POST",
      body: formData,
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload?.detail || `HTTP ${response.status}`;
      const message = typeof detail === "string" ? detail : JSON.stringify(detail);
      if (shouldUseDemoFallback(response.status, message)) {
        renderDemoFallback(mode, file, jdText, message);
        return;
      }
      throw new Error(message);
    }

    renderPayload(payload, mode);
    setStatus("success", "分析成功");
  } catch (error) {
    if (shouldUseDemoFallback(undefined, error?.message || "")) {
      renderDemoFallback(mode, file, jdText, error?.message || "");
      return;
    }
    setStatus("error", `请求失败：${error.message}`);
  } finally {
    setButtons(false);
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function renderPayload(payload, mode) {
  const parsed = payload.parsed;
  const extraction = payload.extraction;
  const match = payload.match;

  const metrics = [];
  if (payload.resume_id) metrics.push(metric("Resume ID", payload.resume_id));
  if (parsed?.page_count) metrics.push(metric("页数", `${parsed.page_count}`));
  const finalScore = toNumber(match?.score?.final_score);
  if (finalScore !== null) {
    metrics.push(metric("匹配分", `${finalScore.toFixed(2)}`));
  }
  metrics.push(metric("缓存命中", payload.cached ? "是" : "否"));
  if (payload.demo) {
    metrics.push(metric("数据模式", "交互演示"));
  }

  overviewEl.innerHTML = metrics.join("");
  parseView.innerHTML = parsed
    ? renderParsePanel(parsed)
    : "<p class=\"empty-hint\">当前响应未包含 parsed 字段</p>";
  extractionView.innerHTML = extraction
    ? renderExtractionTable(extraction)
    : "<p class=\"empty-hint\">当前响应未包含 extraction 字段</p>";
  matchView.innerHTML = match
    ? renderMatchPanel(match)
    : "<p class=\"empty-hint\">当前响应未包含 match 字段</p>";

  applyResultLayout(mode, { parsed, extraction, match });
}

function metric(label, value) {
  return `<div class="metric"><b>${escapeHtml(label)}</b><span>${escapeHtml(value)}</span></div>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderExtractionTable(extraction) {
  const contact = extraction.contact || {};
  const educationText = compactLongField(extraction.education_background, 5, 84);

  const basicRows = [
    ["姓名", contact.name],
    ["电话", contact.phone],
    ["邮箱", contact.email],
    ["地址", contact.address],
  ];
  const jobRows = [
    ["求职意向", extraction.job_intention],
    ["期望薪资", extraction.expected_salary],
  ];
  const backgroundRows = [
    ["工作年限", extraction.work_years ?? null],
    ["学历背景", educationText],
  ];

  const projects = normalizeProjectItems(extraction.project_experience);
  const skills = Array.isArray(extraction.skills)
    ? extraction.skills.filter(Boolean).slice(0, 24)
    : [];

  return `
    <section class="extract-card">
      <h4>基本信息</h4>
      ${renderKVTable(basicRows)}
    </section>
    <section class="extract-card">
      <h4>求职信息</h4>
      ${renderKVTable(jobRows)}
    </section>
    <section class="extract-card">
      <h4>背景信息</h4>
      ${renderKVTable(backgroundRows)}
      <h4>项目经历</h4>
      ${renderList(projects, "暂无项目信息")}
      <h4>技能关键词</h4>
      ${renderSkillChips(skills)}
    </section>
  `;
}

function renderKVTable(rows) {
  const body = rows
    .map(([label, value]) => {
      const text =
        value === null || value === undefined || value === ""
          ? "<span class=\"empty-hint\">未提取到</span>"
          : escapeHtml(String(value));
      return `<tr><th>${escapeHtml(label)}</th><td>${text}</td></tr>`;
    })
    .join("");
  return `<table class="extract-table">${body}</table>`;
}

function renderList(items, emptyText) {
  if (!items.length) {
    return `<p class="empty-hint">${escapeHtml(emptyText)}</p>`;
  }
  return `<ol class="extract-list">${items
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("")}</ol>`;
}

function renderSkillChips(skills) {
  if (!skills.length) {
    return "<p class=\"empty-hint\">暂无技能关键词</p>";
  }
  return `<div class="skill-chips">${skills
    .map((skill) => `<span class="skill-chip">${escapeHtml(skill)}</span>`)
    .join("")}</div>`;
}

function renderParsePanel(parsed) {
  const sectionEntries =
    parsed?.sections && typeof parsed.sections === "object"
      ? Object.entries(parsed.sections).filter(([, value]) => Boolean(value)).slice(0, 6)
      : [];
  const sectionText = sectionEntries.map(([title]) => title).join("、");
  const cleanedPreview = trimValue(parsed.cleaned_text, 520);

  return `
    <section class="extract-card">
      <h4>解析摘要</h4>
      ${renderKVTable([
        ["页数", parsed.page_count ?? null],
        ["文本长度", parsed.cleaned_text ? `${parsed.cleaned_text.length} 字` : null],
        ["识别章节", sectionText || null],
      ])}
    </section>
    <section class="extract-card">
      <h4>文本预览</h4>
      ${
        cleanedPreview
          ? `<p class="parse-preview">${escapeHtml(cleanedPreview)}</p>`
          : "<p class=\"empty-hint\">暂无解析文本</p>"
      }
    </section>
  `;
}

function renderMatchPanel(match) {
  const score = match?.score || {};

  const finalScore = toNumber(score.final_score);
  const heuristicScore = toNumber(score.heuristic_score);
  const aiScore = toNumber(score.ai_score);
  const aiEnabled = hasEffectiveAiScore(score, finalScore, heuristicScore);

  const scoreLevel =
    finalScore === null ? "待分析" : finalScore >= 80 ? "高匹配" : finalScore >= 60 ? "中匹配" : "低匹配";

  const matchedKeywords = normalizeKeywordList(match?.matched_keywords, 28);
  const missingKeywords = normalizeKeywordList(match?.missing_keywords, 28);
  const strengths = normalizeSentenceList(match?.strengths, 5, 72);
  const gaps = normalizeSentenceList(match?.gaps, 5, 72);
  const summary = trimValue(match?.summary, 260);

  const matchedCount = Number.isFinite(score?.matched_keywords_count)
    ? Number(score.matched_keywords_count)
    : matchedKeywords.length;
  const totalKeywords = Number.isFinite(score?.total_job_keywords)
    ? Number(score.total_job_keywords)
    : Math.max(matchedKeywords.length + missingKeywords.length, 0);

  const componentRows = [
    {
      label: "技能匹配",
      score: toNumber(score.skill_score),
      ratio: toNumber(score.skill_match_rate),
      hint: "JD 关键词命中",
    },
    {
      label: "经验相关",
      score: toNumber(score.experience_score),
      ratio: toNumber(score.experience_relevance),
      hint: "工作年限与职责相关度",
    },
    {
      label: "学历相关",
      score: toNumber(score.education_score),
      ratio: toNumber(score.education_relevance),
      hint: "学历要求匹配度",
    },
    {
      label: "岗位方向",
      score: toNumber(score.role_score),
      ratio: toNumber(score.role_relevance),
      hint: "简历方向与岗位方向",
    },
  ]
    .map((item) => renderComponentScore(item.label, item.score, item.ratio, item.hint))
    .join("");

  return `
    <section class="match-card">
      <div class="match-hero">
        <div class="match-hero-main">
          <span class="match-hero-title">综合匹配分</span>
          <span class="match-hero-score">${finalScore === null ? "--" : finalScore.toFixed(1)}</span>
          <span class="match-hero-tag">${escapeHtml(scoreLevel)}</span>
        </div>
        <div class="match-hero-metrics">
          <div class="metric-chip"><b>规则分</b><span>${heuristicScore === null ? "--" : heuristicScore.toFixed(1)}</span></div>
          <div class="metric-chip"><b>AI 分</b><span>${aiEnabled && aiScore !== null ? aiScore.toFixed(1) : "未启用"}</span></div>
          <div class="metric-chip"><b>关键词命中</b><span>${matchedCount}/${totalKeywords}</span></div>
        </div>
      </div>

      <div class="match-breakdown">
        ${componentRows}
      </div>

      <div class="match-columns">
        <section class="match-subcard">
          <h4>命中关键词</h4>
          ${renderTagList(matchedKeywords, "keyword-hit", "暂无命中关键词")}
        </section>
        <section class="match-subcard">
          <h4>缺失关键词</h4>
          ${renderTagList(missingKeywords, "keyword-miss", "暂无明显缺失关键词")}
        </section>
      </div>

      <div class="match-columns">
        <section class="match-subcard">
          <h4>优势亮点</h4>
          ${renderList(strengths, "暂无优势信息")}
        </section>
        <section class="match-subcard">
          <h4>改进建议</h4>
          ${renderList(gaps, "暂无改进建议")}
        </section>
      </div>

      <p class="match-summary">${summary ? escapeHtml(summary) : "<span class=\"empty-hint\">暂无总结</span>"}</p>
    </section>
  `;
}

function renderComponentScore(label, score, ratio, hint) {
  const numericScore = score === null ? null : clampScore(score);
  const numericRatio = ratio === null ? null : clampRatio(ratio);
  const progress = numericRatio === null ? (numericScore === null ? 0 : numericScore) : numericRatio * 100;
  return `
    <article class="score-row">
      <div class="score-row-head">
        <div>
          <span class="score-label">${escapeHtml(label)}</span>
          <p>${escapeHtml(hint)}</p>
        </div>
        <b>${numericScore === null ? "--" : numericScore.toFixed(1)}</b>
      </div>
      <div class="score-track"><span style="width:${clampPercent(progress)}%"></span></div>
    </article>
  `;
}

function renderTagList(items, className, emptyText) {
  if (!items.length) {
    return `<p class="empty-hint">${escapeHtml(emptyText)}</p>`;
  }
  return `<div class="tag-list">${items
    .map((item) => `<span class="tag-chip ${escapeHtml(className)}">${escapeHtml(item)}</span>`)
    .join("")}</div>`;
}

function compactLongField(value, maxItems, maxLen) {
  const parts = normalizeSentenceList([value], maxItems, maxLen);
  return parts.length ? parts.join("\n") : null;
}

function normalizeProjectItems(rawItems) {
  if (!Array.isArray(rawItems) || !rawItems.length) {
    return [];
  }

  const keywords = /(项目|系统|平台|检测|分类|推荐|分析|前端|后端|工程|scrum|project|platform|system|api|app)/i;
  const cleaned = [];

  rawItems.forEach((item) => {
    normalizeSentenceList([item], 6, 96).forEach((segment) => {
      const line = segment.replace(/^\d+[.)、\s-]*/, "").trim();
      if (line.length < 6) return;
      if (!keywords.test(line)) return;
      cleaned.push(line);
    });
  });

  return dedupeList(cleaned).slice(0, 6);
}

function normalizeKeywordList(value, limit) {
  if (!Array.isArray(value)) {
    return [];
  }
  const cleaned = value
    .map((item) => trimValue(item, 40))
    .filter(Boolean);
  return dedupeList(cleaned).slice(0, limit);
}

function normalizeSentenceList(value, maxItems, maxLen) {
  const raw = Array.isArray(value) ? value : [value];
  const segments = [];

  raw.forEach((item) => {
    const text = String(item || "").trim();
    if (!text) return;
    text
      .split(/[\n；;。]+/)
      .map((part) => part.replace(/^[-•·*\s]+/, "").trim())
      .filter(Boolean)
      .forEach((part) => {
        segments.push(trimValue(part, maxLen));
      });
  });

  return dedupeList(segments).slice(0, maxItems);
}

function dedupeList(items) {
  const result = [];
  const seen = new Set();

  items.forEach((item) => {
    const key = String(item).trim().toLowerCase();
    if (!key || seen.has(key)) return;
    seen.add(key);
    result.push(String(item).trim());
  });

  return result;
}

function trimValue(value, maxLen) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen - 1)}…`;
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function hasEffectiveAiScore(score, finalScore, heuristicScore) {
  const aiScore = toNumber(score?.ai_score);
  if (aiScore === null) {
    return false;
  }

  if (aiScore === 0 && finalScore !== null && heuristicScore !== null) {
    const sameAsHeuristic = Math.abs(finalScore - heuristicScore) < 0.0001;
    if (sameAsHeuristic && finalScore > 0) {
      return false;
    }
  }

  return true;
}

function clampScore(value) {
  return Math.min(Math.max(value, 0), 100);
}

function clampRatio(value) {
  return Math.min(Math.max(value, 0), 1);
}

function clampPercent(value) {
  return Math.min(Math.max(Number(value) || 0, 0), 100);
}

function shouldUseDemoFallback(statusCode, message) {
  const status = Number(statusCode);
  if (status >= 500) {
    return true;
  }

  const normalizedMessage = String(message || "").toLowerCase();
  const networkHints = [
    "failed to fetch",
    "networkerror",
    "network request failed",
    "load failed",
    "timed out",
    "timeout",
    "connection refused",
    "err_connection_refused",
    "econnrefused",
  ];

  return networkHints.some((hint) => normalizedMessage.includes(hint));
}

function renderDemoFallback(mode, file, jobDescription, reason) {
  const payload = createFallbackMockPayload({
    mode,
    fileName: file?.name,
    jobDescription,
    reason,
  });
  renderPayload(payload, mode);
  setStatus("demo", "后端暂不可用，已切换 Mock 演示数据（非真实解析结果）");
}

function applyResultLayout(mode, data) {
  const viewMode = normalizeViewMode(mode, data);

  parseCard.classList.toggle("hidden", viewMode !== "parse");
  extractCard.classList.toggle("hidden", viewMode === "parse" || !data.extraction);
  matchCard.classList.toggle("hidden", viewMode !== "analyze" || !data.match);

  resultGrid.classList.toggle("compact", true);
}

function normalizeViewMode(mode, data) {
  if (mode === "parse" || mode === "extract" || mode === "analyze") {
    return mode;
  }
  if (data.match) return "analyze";
  if (data.extraction) return "extract";
  return "parse";
}
