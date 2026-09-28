# InvestEval 测试说明与结果

## 测试目标

验证 InvestEval 的核心治理链路能够在冻结合成数据上重复运行，并覆盖题目要求的主链路、数据与接口异常、KYC与合规边界、用户行为反馈、热点上下文和上线门控。

本文记录的是原型验证结果，不构成真实投资问答准确率、生产性能或合规认证。

## 测试环境

- 日期：2026-09-27
- Python：3.11
- 核心运行依赖：Python标准库
- 数据：匿名合成冻结数据
- 外部金融接口：未连接
- Web部署：Sites私有静态站点

## 自动测试结果

执行命令：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

结果：**26项通过，0项失败**。

### 主链路

| 测试点 | 预期结果 | 结果 |
|---|---|---|
| 四类问答意图加载 | 行情、财务、公告和个性化意图均存在 | PASS |
| 场景分层评测集 | 32条、四类意图各8条、Baseline 20条通过 | PASS |
| 预期错误标签复现 | 11条案例的预期错误码与实际结果一致 | PASS |
| 正常案例 | 正常行情与财务案例通过且得分100 | PASS |
| Bad Case筛选 | 返回数量与汇总中的Bad Case数量一致 | PASS |
| 案例详情 | 包含Finding、事实ID和版本血缘 | PASS |
| 人工复核 | 确认结论写入后可重新加载 | PASS |
| 日志导入 | 新案例导入后立即产生评测结果 | PASS |
| 版本配对 | Baseline与Candidate包含相同案例集合 | PASS |
| 按意图报告 | 四类意图分别输出通过率、平均分、证据覆盖与案例回归数 | PASS |
| 上线决策 | HOLD原因与失败的硬门槛一致 | PASS |
| 行为反馈 | 负向信号形成调查队列但不覆盖事实结论 | PASS |
| 热点上下文 | 能识别过期、未来信息和事件日期错配 | PASS |

### 数据和接口异常

| 异常 | 预期处理 | 结果 |
|---|---|---|
| 重复 `fact_id` | 拒绝加载 | PASS |
| 非可信来源协议 | 拒绝 `javascript:` 等来源，仅接受 `fixture://` 或 `https://` | PASS |
| 重复 `case_id` 导入 | 拒绝导入且原文件保持不变 | PASS |
| 不存在的案例 | 返回未找到语义，不生成空详情 | PASS |
| 非法复核状态 | 拒绝保存 | PASS |
| 已完成复核没有审核人 | 拒绝保存 | PASS |
| Baseline/Candidate案例不配对 | 拒绝计算版本结论 | PASS |
| 重复反馈事件ID | 拒绝聚合 | PASS |
| 未支持的反馈类型 | 拒绝聚合 | PASS |

HTTP层已人工调用并确认：健康检查、质量汇总、Bad Case筛选、案例详情和人工复核均返回预期JSON；无效请求由API映射为400或404。由于当前没有外部金融数据接口，网络超时、限流和上游5xx仅列为未覆盖项，未伪造通过结果。

### 合规与个性化边界

| 场景 | 预期结论 | 结果 |
|---|---|---|
| 保守型用户收到高风险推荐 | `KYC_MISMATCH` | PASS |
| 不同KYC画像导致同一价格变化 | `FACT_PERSONALIZED` | PASS |
| 使用未授权收入字段 | `PRIVACY_OVERREACH` | PASS |
| 回答包含“保证收益”“稳赚” | `GUARANTEED_RETURN` | PASS |
| 违规回答获得用户点赞 | 点赞不清除合规Finding | PASS |
| 未来发布的信息用于回答过去问题 | `FUTURE_CONTEXT_LEAK` | PASS |

## 可复现产出

```bash
PYTHONPATH=src python3 -m investeval.cli evaluate \
  --facts data/facts.json \
  --cases data/cases.json \
  --output artifacts/evaluation-results.json
PYTHONPATH=src python3 -m investeval.cli evaluate \
  --facts data/facts.json \
  --cases data/representative-cases.json \
  --output artifacts/representative-evaluation-results.json
PYTHONPATH=src python3 -m investeval.cli compare
PYTHONPATH=src python3 -m investeval.cli signals
```

对应证据：

- `artifacts/evaluation-results.json`
- `artifacts/representative-evaluation-results.json`
- `artifacts/version-comparison.json`
- `artifacts/signals-context-summary.json`

## Web检查

已完成：

- HTML可以解析；
- JavaScript语法检查通过；
- 页面和全部运行时数据文件均返回HTTP 200；
- 质量工作台、版本对比、反馈与热点三个导航入口可用；
- 案例筛选、详情、导入和人工复核操作可执行；
- 私有部署状态为成功。

## 未覆盖测试

- 扶摇或iFinD真实接口的成功、超时、限流、鉴权失败和字段漂移；
- 真实LLM的意图识别与Claim抽取质量；
- 独立人工标注集上的准确率、召回率和一致性；
- 多用户并发复核、权限隔离和审计日志；
- 生产负载、长期稳定性、灾备和浏览器兼容矩阵；
- 真实个人信息的脱敏和数据生命周期。

这些缺口属于上线前验证范围，不应被当前26项测试掩盖。

## 最终测试结论

当前证据足以证明原型主链路、异常处理和核心边界在合成数据上可重复运行。当前证据不足以证明生产就绪，因此版本门控保持 `HOLD`。
