# InvestEval 投资 Agent 回答质量与个性化治理平台

InvestEval 是一个面向投资问答 Agent 的质量治理原型。它将匿名问答日志转化为可计算的质量指标，通过金融事实核验、KYC 一致性、合规与隐私规则识别 Bad Case，再由人工复核确认结论，并使用同一批冻结案例比较模型、Prompt 和数据版本，最终输出可追溯的上线门控决策。

当前版本证明的是治理链路能够运行和复现，不代表真实投资 Agent 的线上质量，也不提供投资建议。

## 在线产品

- Web 产品：<https://investeval-governance.gao44y.chatgpt.site>
- 当前访问范围：私有
- 页面：质量工作台、版本对比与上线门控

## 目标用户

| 用户 | 主要任务 |
|---|---|
| AI 产品或质量负责人 | 观察回答质量、定位问题、判断版本是否可上线 |
| 投资业务与合规审核人员 | 复核高风险回答、确认合规和适当性问题 |
| 模型与 Prompt 工程师 | 比较版本、定位回归、查看 Bad Case 根因 |
| 数据与评测工程师 | 维护事实数据、指标口径、评测案例和证据血缘 |

## 核心问题

投资 Agent 的回答可能出现答非所问、行情或财务数字错误、信息过期、报告期不一致、个性化失真、收益承诺和隐私越界。InvestEval 不让一个总分掩盖这些问题，而是保存具体错误码、严重程度、证据引用、模型版本、Prompt 版本、数据版本和人工审核状态。

## 主链路

```text
匿名问答日志
    ↓
回答意图与评测标准
    ↓
确定性事实核验 + KYC / 合规 / 隐私检查
    ↓
Bad Case 分类与证据血缘
    ↓
人工确认、驳回或修复
    ↓
模型 / Prompt / 数据版本配对比较
    ↓
证据门控：HOLD 或受限灰度
```

## 当前覆盖的问答意图

| 意图 | 核心质量标准 | 当前可计算指标 |
|---|---|---|
| 行情查询 | 标的、数值、日期和新鲜度正确 | 数值一致性、数据年龄、来源覆盖 |
| 财务分析 | 指标、单位和报告期一致 | 数值一致性、报告期一致性、证据覆盖 |
| 新闻或公告总结 | 来源存在、时间有效、结论受证据支持 | 来源缺失、数据年龄、无证据主张 |
| 个性化投资解释 | 客观事实不变、风险适配、画像使用有授权 | KYC 失配、事实个性化、隐私越界、收益承诺 |

## 四种治理机制的分工

| 机制 | 负责 | 不负责 |
|---|---|---|
| 自动评测 | 执行结构、规则和确定性一致性检查，生成待复核结论 | 不能单独证明复杂投资观点正确 |
| 数据核验 | 比较回答主张与带日期、报告期和来源的事实记录 | 不判断表达是否适合特定用户 |
| 人工复核 | 确认高风险、低置信度或规则冲突案例 | 不应成为所有低风险回答的必经步骤 |
| 用户行为反馈 | 使用点赞、点踩、重问和举报等信号确定调查优先级 | 不能把受欢迎程度当成事实正确性 |

当前使用16条匿名合成行为事件演示分工：举报直接进入人工复核，至少两个负向信号进入质量调查，单个弱信号仅持续观察。行为反馈不会清除事实或合规 Finding。

## 错误分类

| 错误码 | 含义 |
|---|---|
| `NUMERIC_MISMATCH` | 回答数字与冻结事实不一致 |
| `STALE_DATA` | 数据超过当前意图允许的新鲜度 |
| `PERIOD_MISMATCH` | 回答报告期与事实报告期不一致 |
| `MISSING_SOURCE` | 回答主张没有引用来源 |
| `UNSUPPORTED_CLAIM` | 当前数据版本不存在支持该主张的事实 |
| `KYC_MISMATCH` | 建议风险高于用户风险承受能力 |
| `FACT_PERSONALIZED` | 相同客观事实随用户画像发生变化 |
| `GUARANTEED_RETURN` | 回答包含保证收益或确定性上涨表达 |
| `PRIVACY_OVERREACH` | 使用了用户未授权的画像字段 |

## 不可因用户画像改变的事实

- 股票、基金和指数价格及涨跌幅；
- 财务报表数字、单位及报告期；
- 公告和新闻的原文事实及发布时间；
- 产品风险等级；
- 法律法规和交易规则；
- 数据来源、时间戳和数据版本；
- 历史事件和确定性公式的计算结果。

用户画像可以影响解释深度、内容顺序、举例方式和风险提示重点，但不能改变上述事实。

## 数据设计和使用边界

当前仓库仅包含匿名合成数据：

- `data/facts.json`：6 条冻结金融事实；
- `data/cases.json`：11 条高异常密度的压力回归案例，覆盖 4 类意图；
- `data/representative-cases.json`：32 条场景分层案例，4 类意图各 8 条；
- `data/version-runs.json`：同一批案例的 Baseline 和 Candidate 配对结果；
- `data/user-feedback.json`：16条匿名合成行为事件；
- `data/hot-context.json`：4条热点时间一致性检查；
- `fixture://`：明确表示本地合成来源，不冒充真实外部链接。

数据没有真实姓名、账户、持仓、交易记录或其他个人信息。当前未连接扶摇或 iFinD MCP。未来可以通过标准数据提供者接口接入行情、财务、基金、公告和新闻数据，但接入前必须验证授权、时间戳、接口失败语义和数据许可。

### 为什么使用两套评测集

单一数据集不能同时承担“估计常规表现”和“尽量发现错误”两个目标。如果只向原来的 11 条压力集中追加容易通过的样本，虽然可以机械地提高通过率，却会改变数据分布并造成指标美化。因此，本项目冻结两套用途不同、不得混算的数据集：

| 数据集 | 设计 | 用途 | 不可用于 |
|---|---|---|---|
| 场景分层集 `representative-synthetic-v2` | 32条；4类意图各8条；每类5条正常、3条异常 | 提供版本配对比较，并检查主要工作场景是否均被覆盖 | 推断真实线上流量分布或生产准确率 |
| Bad Case压力集 | 11条；刻意提高事实、KYC、合规和隐私异常密度 | 回归错误码、人工复核与证据链，比较修复是否退化 | 作为日常问答通过率的无偏估计 |

场景分层 Baseline 的 20/32 条通过、62.5% 通过率来自预先声明的 5:3 设计比例，不是观察真实用户流量后得到的模型性能。它的“代表性”只表示四类核心意图获得等量覆盖。未来获得合规的真实匿名分布后，应先冻结抽样协议和分层权重，再建立独立标注集；不能根据想要的通过率反向挑选案例。

## 指标解释

- **场景分层 Baseline 通过率 62.5%**：32 条中有 20 条按确定性规则通过。该数字由场景覆盖设计产生，只用于合成基线验证。
- **Bad Case 压力集通过率 18.2%**：11 条压力测试案例中有 2 条正常回答、9 条预设异常。这是高难度回归集的质量，不是日常回答通过率，也不是评测器准确率。
- **预期标签复现率 100%**：当前确定性规则在 11 条合成样例上复现了 11/11 条预期标签。样本量很小，不能解释为真实线上准确率。
- **待复核 9 条**：自动评测发现的 9 条 Bad Case 初始进入人工队列，不表示已有 9 条生产事故。
- **证据核验覆盖率**：至少检查过一条冻结事实的案例占比。
- **质量分**：从 100 分开始，根据中、高、严重等级问题扣分。它用于排序和比较，不代替错误明细。

## 版本对比与上线门控

当前 Baseline 和 Candidate 使用完全相同的 32 个场景分层 `case_id` 与意图标签，避免因样本变化产生不可比结果。原 11 条压力集继续独立承担错误码和人工复核回归，不与版本指标混算。

| 指标 | Baseline | Candidate | 变化 |
|---|---:|---:|---:|
| 回答通过率 | 62.5% | 90.6% | +28.12pp |
| 平均质量分 | 91.25 | 98.12 | +6.87 |
| 证据核验覆盖 | 90.6% | 100.0% | +9.38pp |
| P95 延迟 | 610ms | 840ms | +230ms |
| 阻断类错误 | 6 次 | 0 次 | -6 |

按意图拆分后，行情、财务、公告、个性化的 Candidate 通过率分别为 87.5%、100%、75% 和 100%，相对 Baseline 分别提升 25、37.5、12.5 和 37.5 个百分点，且没有出现“Baseline 通过、Candidate 失败”的案例。

`rollout-policy-v2` 要求：配对样本量不少于 30、通过率至少改善 20 个百分点、任何意图不得退化、证据覆盖不低于 80%、阻断类错误为 0、P95 延迟不高于 800ms。

Candidate 的总体和各意图质量指标均改善，32 条样本量门槛已通过；但 P95 延迟为 840ms，因此决策保持 **HOLD**，只允许继续离线验证，不允许生产发布或效果宣称。完整证据位于 `artifacts/version-comparison.json`。

## AI 在产品中的角色

当前 MVP 的运行时评测器是确定性的，不依赖在线 LLM：Claim 与 Fact 进行精确或容差比较，日期和报告期由程序判断，KYC、隐私和收益承诺由显式规则判断，上线决策由版本化门控策略计算。

生产形态中，LLM 可以负责意图识别、从自然语言回答中提取待核验主张、辅助解释复杂 Bad Case，以及给人工审核排序；金融数字核验、权限、隐私约束和上线硬门槛仍应由确定性程序执行。

项目开发过程中的 AI 使用和验证记录见 [`docs/AI_USAGE_AND_VALIDATION.md`](docs/AI_USAGE_AND_VALIDATION.md)。

## 架构

```text
dist/                         静态可操作 Web 产品
data/                         冻结事实、问答案例和配对版本输入
src/investeval/models.py      类型化数据合同
src/investeval/evaluator.py   事实、KYC、合规和隐私评测
src/investeval/governance.py  导入、筛选、详情和人工复核服务
src/investeval/rollout.py     配对版本比较和上线门控
src/investeval/signals.py     用户行为聚合和热点时间检查
src/investeval/web_api.py     无第三方依赖的 HTTP API
tests/                        确定性回归测试
artifacts/                    可复现评测和版本决策结果
```

部署页面是静态原型，人工复核状态存储在当前浏览器的 `localStorage` 中。Python API 版本将复核结果原子写入 JSON 文件，但该 API 尚未部署为公共多用户服务。因此，当前版本不是多用户生产系统。

## 本地运行

要求 Python 3.10 或更高版本。核心评测、API 和测试不依赖第三方 Python 包。

```bash
# 运行全部测试
PYTHONPATH=src python3 -m unittest discover -s tests -v

# 复现基线评测结果
PYTHONPATH=src python3 -m investeval.cli evaluate \
  --facts data/facts.json \
  --cases data/cases.json \
  --output artifacts/evaluation-results.json

# 复现场景分层集结果
PYTHONPATH=src python3 -m investeval.cli evaluate \
  --facts data/facts.json \
  --cases data/representative-cases.json \
  --output artifacts/representative-evaluation-results.json

# 复现版本对比和上线决策
PYTHONPATH=src python3 -m investeval.cli compare \
  --runs data/version-runs.json \
  --output artifacts/version-comparison.json

# 汇总用户行为并检查热点时间上下文
PYTHONPATH=src python3 -m investeval.cli signals \
  --feedback data/user-feedback.json \
  --hot-context data/hot-context.json \
  --output artifacts/signals-context-summary.json

# 启动治理 API
PYTHONPATH=src python3 -m investeval.cli serve --port 8000

# 启动静态 Web 产品
python3 -m http.server 8790 --directory dist
```

## Governance API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/health` | 服务健康检查 |
| `GET` | `/api/summary` | 质量和审核状态汇总 |
| `GET` | `/api/cases` | 按意图、错误码、结果和审核状态筛选案例 |
| `GET` | `/api/cases/{case_id}` | 查看回答、Finding、证据和版本血缘 |
| `POST` | `/api/evaluate` | 重新运行确定性评测 |
| `POST` | `/api/cases/import` | 校验、保存并评测匿名问答日志 |
| `POST` | `/api/cases/{case_id}/review` | 保存人工审核状态和说明 |

筛选示例：`/api/cases?outcome=bad_case&error_code=NUMERIC_MISMATCH&review_status=pending`

## 测试与验证

当前包含 26 项确定性测试，覆盖四类意图、32 条场景分层结构与通过数、按意图报告、预期错误标签复现、正常案例、事实个性化、数据来源协议、重复 ID、Bad Case筛选、证据血缘、人工复核持久化、异常状态、日志导入原子性、配对一致性、上线门控、行为信号聚合及热点时间检查。

已执行的附加验证包括 JSON 语法检查、JavaScript 语法检查、HTML 解析、HTTP 页面与全部运行时数据文件返回 200，以及私有部署成功状态检查。

正式测试说明见 [`docs/TEST_PLAN_AND_RESULTS.md`](docs/TEST_PLAN_AND_RESULTS.md)，演示流程见 [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)，提交状态见 [`docs/SUBMISSION_CHECKLIST.md`](docs/SUBMISSION_CHECKLIST.md)。

## 已知边界和未做事项

- 没有连接扶摇、iFinD 或其他实时金融数据接口；
- 没有自然语言 Claim 提取模型，当前 Claim 已结构化；
- 没有答非所问的语义相关性模型；
- 热点上下文目前只检查时效、未来信息泄漏和事件日期错配，尚未检测新闻重要信息遗漏；
- 用户行为目前来自合成离线日志，尚未接入真实线上埋点；
- 当前正则规则不能覆盖所有合规表达及其上下文；
- 配对集只有 32 条合成案例，不能估计真实准确率或泛化能力；
- Candidate 指标是合成配对结果，不是线上 A/B 实验；
- 部署版复核状态只保存在单个浏览器，不支持多用户协作、权限和审计；
- 没有生产级认证、数据库、监控、告警、灾备或数据保留策略；
- 产品不生成买卖建议，不验证策略收益，也不替代持牌投资顾问或合规人员。

## 下一步

1. 增加数据或接口异常测试说明和演示材料；
2. 使用真实匿名分布重新校准场景权重，并引入独立人工标注；
3. 实现 `FinancialDataProvider`，在获得授权后接入扶摇或 iFinD；
4. 将人工复核迁移到持久化多用户后端；
5. 在满足样本量和延迟门槛后，再评估受限灰度。
