// Demo payload builder used only when backend is unreachable.
const MOCK_PROFILES = [
  {
    key: "backend",
    tags: ["python", "fastapi", "redis", "docker", "api", "后端", "微服务"],
    name: "Zhang Demo",
    role: "Python 后端工程师",
    phone: "13800000000",
    email: "demo-backend@example.com",
    address: "上海市（Mock）",
    expectedSalary: "25k-35k/月",
    workYears: "3 年",
    education: "计算机科学本科，具备后端系统设计与交付经验",
    skills: ["Python", "FastAPI", "Redis", "Docker", "PostgreSQL", "Linux", "Git", "RESTful API", "CI/CD", "AWS"],
    projects: [
      "简历分析系统：负责 FastAPI 接口、PDF 解析流程与结构化返回",
      "缓存加速模块：引入 Redis 缓存策略，减少重复解析计算开销",
      "岗位匹配服务：实现关键词命中率和多维评分逻辑，支持结果解释",
    ],
    sections: {
      基本信息: "姓名、邮箱、电话等信息完整",
      技术栈: "Python/FastAPI/Redis/Docker/PostgreSQL/Linux",
      项目经历: "后端 API 架构、缓存优化、匹配评分模块",
      教育背景: "计算机相关本科",
    },
  },
  {
    key: "fullstack",
    tags: ["react", "typescript", "node", "frontend", "全栈", "前端", "next"],
    name: "Lin Mock",
    role: "前端/全栈工程师",
    phone: "13900000000",
    email: "demo-fullstack@example.com",
    address: "杭州市（Mock）",
    expectedSalary: "22k-32k/月",
    workYears: "4 年",
    education: "软件工程本科，偏重 Web 平台与业务系统开发",
    skills: ["TypeScript", "React", "Node.js", "Express", "MongoDB", "Docker", "Nginx", "Git", "CI/CD", "Figma"],
    projects: [
      "企业门户系统：负责 React 前端架构与组件库落地，提升迭代效率",
      "运营中台平台：基于 Node.js 构建 BFF 服务层与权限中台接口",
      "多端协作项目：完善 CI/CD 和监控告警，提升发布稳定性",
    ],
    sections: {
      基本信息: "联系方式和在线作品链接完整",
      技术栈: "React/TypeScript/Node.js/MongoDB/Docker",
      项目经历: "Web 平台、BFF 服务、DevOps 工程实践",
      教育背景: "软件工程本科",
    },
  },
  {
    key: "ml",
    tags: ["机器学习", "ml", "pytorch", "llm", "算法", "模型", "ai"],
    name: "Chen Mock",
    role: "机器学习工程师",
    phone: "13700000000",
    email: "demo-ml@example.com",
    address: "深圳市（Mock）",
    expectedSalary: "30k-45k/月",
    workYears: "2.5 年",
    education: "人工智能硕士，具备模型训练和工程化部署经验",
    skills: ["Python", "PyTorch", "scikit-learn", "Pandas", "NumPy", "LLM", "Docker", "Linux", "API", "MLOps"],
    projects: [
      "文本分类系统：构建训练流水线并实现线上推理服务",
      "RAG 智能问答：完成向量检索、Prompt 设计和质量评估",
      "风控模型项目：优化特征工程与模型监控，稳定线上表现",
    ],
    sections: {
      基本信息: "姓名、联系方式、研究方向完整",
      技术栈: "Python/PyTorch/LLM/MLOps/Docker",
      项目经历: "模型训练、推理部署、质量评估",
      教育背景: "人工智能硕士",
    },
  },
];

const STOP_WORDS = new Set([
  "招聘",
  "要求",
  "熟悉",
  "负责",
  "经验",
  "年以上",
  "以上",
  "岗位",
  "具备",
  "优先",
  "相关",
  "工程师",
  "开发",
  "本科",
  "及以上",
  "能够",
  "有",
  "需要",
  "优先考虑",
  "职位",
]);

export function createFallbackMockPayload({ mode, fileName, jobDescription, reason }) {
  // Use role-aware mock profile so UI still demonstrates realistic score differences.
  const profile = pickMockProfile(jobDescription);
  const displayName = inferNameFromFileName(fileName) || profile.name;
  const selectedFile = trimValue(fileName || "mock-resume.pdf", 56);
  const parsed = buildParsedSection(profile, displayName, selectedFile, reason);
  const extraction = buildExtractionSection(profile, displayName);
  const match = buildMatchSection(profile, jobDescription);
  const idSuffix = Date.now().toString(36).slice(-8);

  const payload = {
    resume_id: `mock-${profile.key}-${idSuffix}`,
    cached: false,
    demo: true,
    mock: true,
    parsed,
    extraction,
    match,
  };

  if (mode === "parse") {
    payload.extraction = null;
    payload.match = null;
  } else if (mode === "extract") {
    payload.match = null;
  }

  return payload;
}

function pickMockProfile(jobDescription) {
  // Select the profile with highest JD tag overlap.
  const text = normalizeToken(jobDescription || "");
  if (!text) {
    return MOCK_PROFILES[0];
  }

  let best = MOCK_PROFILES[0];
  let bestScore = -1;

  MOCK_PROFILES.forEach((profile) => {
    const score = profile.tags.reduce((total, tag) => {
      return total + (text.includes(normalizeToken(tag)) ? 1 : 0);
    }, 0);

    if (score > bestScore) {
      bestScore = score;
      best = profile;
    }
  });

  return best;
}

function buildParsedSection(profile, displayName, fileName, reason) {
  // Mock parsed block mirrors backend fields so UI rendering path stays identical.
  return {
    page_count: 2,
    raw_text: [
      `${displayName} | ${profile.role}`,
      `电话：${profile.phone} | 邮箱：${profile.email}`,
      `技能：${profile.skills.join("/")}`,
      `项目：${profile.projects.join("；")}`,
      "说明：当前为后端不可用时自动启用的 Mock 数据，仅用于展示前端交互。",
    ].join("\n"),
    cleaned_text: [
      `${displayName} ${profile.role}`,
      `核心能力：${profile.skills.slice(0, 7).join("、")}`,
      `项目经历：${profile.projects.slice(0, 2).join("；")}`,
      `当前演示文件：${fileName}`,
      reason ? `不可用原因：${trimValue(reason, 120)}` : "不可用原因：后端服务暂不可访问",
    ].join("\n"),
    sections: { ...profile.sections },
  };
}

function buildExtractionSection(profile, displayName) {
  // Keep extraction schema identical to backend API contract.
  return {
    contact: {
      name: displayName,
      phone: profile.phone,
      email: profile.email,
      address: profile.address,
    },
    job_intention: profile.role,
    expected_salary: profile.expectedSalary,
    work_years: profile.workYears,
    education_background: profile.education,
    project_experience: [...profile.projects],
    skills: [...profile.skills],
  };
}

function buildMatchSection(profile, jobDescription) {
  // Reuse same score dimensions as backend for consistent front-end presentation.
  const jdKeywords = extractKeywords(jobDescription);
  const baselineKeywords = profile.skills.slice(0, 6);
  const targetKeywords = jdKeywords.length ? jdKeywords : baselineKeywords;

  const matchedKeywords = targetKeywords.filter((keyword) => keywordCovered(keyword, profile.skills));
  const missingKeywords = targetKeywords.filter(
    (keyword) => !matchedKeywords.some((item) => normalizeToken(item) === normalizeToken(keyword))
  );

  const matched = dedupeList(matchedKeywords).slice(0, 12);
  const missing = dedupeList(missingKeywords).slice(0, 12);
  const total = Math.max(targetKeywords.length, 1);
  const hit = matched.length;

  const skillRate = clampRatio(hit / total);
  const expRel = /([5-9]\s*年|五年|senior|lead)/i.test(jobDescription || "") ? 0.72 : 0.86;
  const eduRel = /(本科|学士|bachelor|硕士|master)/i.test(jobDescription || "") ? 0.9 : 0.84;
  const roleRel = roleRelevance(profile.role, jobDescription);

  const skillScore = clampScore(skillRate * 100);
  const expScore = clampScore(expRel * 100);
  const eduScore = clampScore(eduRel * 100);
  const roleScore = clampScore(roleRel * 100);
  const heuristic = clampScore(skillScore * 0.48 + expScore * 0.2 + eduScore * 0.12 + roleScore * 0.2);
  const aiScore = clampScore(heuristic + (hit >= Math.min(3, total) ? 3.5 : -2));
  const finalScore = clampScore(heuristic * 0.6 + aiScore * 0.4);

  return {
    score: {
      final_score: toFixedNumber(finalScore, 2),
      heuristic_score: toFixedNumber(heuristic, 2),
      ai_score: toFixedNumber(aiScore, 2),
      skill_score: toFixedNumber(skillScore, 2),
      skill_match_rate: toFixedNumber(skillRate, 3),
      experience_score: toFixedNumber(expScore, 2),
      experience_relevance: toFixedNumber(expRel, 3),
      education_score: toFixedNumber(eduScore, 2),
      education_relevance: toFixedNumber(eduRel, 3),
      role_score: toFixedNumber(roleScore, 2),
      role_relevance: toFixedNumber(roleRel, 3),
      matched_keywords_count: hit,
      total_job_keywords: total,
    },
    matched_keywords: matched,
    missing_keywords: missing,
    strengths: [
      `${profile.role}方向与岗位描述具备较高一致性`,
      `技能栈覆盖 ${hit}/${total} 个关键字，基础匹配较稳定`,
      "项目描述包含工程化实践，可进一步补充量化结果提升说服力",
    ],
    gaps: [
      missing.length ? `建议补充 ${missing.slice(0, 3).join("、")} 相关项目证据` : "关键词缺口较少，建议强化亮点表达",
      "建议增加与业务结果相关的数据指标（性能、成本、效率）",
      "建议补充线上问题排查和稳定性保障相关案例",
    ],
    summary:
      "当前结果来自 Mock 数据，仅在后端不可用时展示交互流程。恢复后端后将自动返回真实解析与评分结果。",
  };
}

function roleRelevance(role, jobDescription) {
  const normalizedRole = normalizeToken(role);
  const normalizedJd = normalizeToken(jobDescription || "");
  if (!normalizedJd) {
    return 0.85;
  }
  return normalizedJd.includes(normalizedRole.slice(0, 4)) ? 0.92 : 0.8;
}

function keywordCovered(keyword, skills) {
  const needle = normalizeToken(keyword);
  if (!needle) {
    return false;
  }

  return skills.some((skill) => {
    const haystack = normalizeToken(skill);
    return haystack.includes(needle) || needle.includes(haystack);
  });
}

function extractKeywords(text) {
  const source = String(text || "").trim();
  if (!source) {
    return [];
  }

  const parts = source
    .split(/[\s,，。；;、|/()（）:：]+/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 2 && item.length <= 24)
    .filter((item) => !STOP_WORDS.has(item.toLowerCase()) && !STOP_WORDS.has(item));

  return dedupeList(parts).slice(0, 12);
}

function inferNameFromFileName(fileName) {
  const base = String(fileName || "").replace(/\.[^/.]+$/, "").trim();
  if (!base) {
    return "";
  }

  const parts = base.split(/[_-]/).map((part) => part.trim()).filter(Boolean);
  return trimValue(parts[0] || "", 24);
}

function normalizeToken(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5+#/.]/g, "");
}

function dedupeList(items) {
  const result = [];
  const seen = new Set();
  items.forEach((item) => {
    const key = normalizeToken(item);
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

function clampScore(value) {
  const number = Number(value) || 0;
  return Math.min(Math.max(number, 0), 100);
}

function clampRatio(value) {
  const number = Number(value) || 0;
  return Math.min(Math.max(number, 0), 1);
}

function toFixedNumber(value, digits) {
  return Number((Number(value) || 0).toFixed(digits));
}
