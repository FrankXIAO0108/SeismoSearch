# SeismoSearch Baseline Comparison 方案

## 1. 目标

本阶段目标是设计 SeismoSearch 的 baseline comparison，用于回答一个核心问题：

当前的 Planner + Tools + Evidence Pack + Safety Routing 方案，相比普通 RAG 或单一工具系统，到底强在哪里？

当前 eval_40 已经证明 full system 可以在 40 条样本上达到全指标 1.0，但这还不够。因为面试官一定会追问：

- 如果不用 Planner，会怎样？
- 如果只做普通文档 RAG，会怎样？
- 如果只查结构化数据库，会怎样？
- Safety Routing 是否真的必要？
- Evidence Pack 是否真的带来可控性？
- 当前系统相比 baseline 的优势能不能被指标证明？

因此，下一阶段需要从“单系统评估”进入“多系统对比评估”。

---

## 2. 当前 Full System

### 是什么

当前系统是 SeismoSearch v0.1 deterministic Agentic RAG baseline。

完整链路为：

用户问题 -> Planner -> safety_check / event_search / event_statistics / doc_retrieval -> Evidence Pack -> Generator -> Answer

当前支持四类 query：

- catalog：历史地震事件查询；
- concept：地震学概念解释；
- mixed：事件查询 + 概念解释；
- safety：地震预测诱导、伪科学预兆、历史活动风险推断拒答。

### 为什么需要

地震信息问答不是单纯文档问答。

有些问题需要查结构化事件库，例如：

- 最近 M6.5 以上地震有哪些？
- 2025 年 M6 以上最强地震有哪些？

有些问题需要查概念文档，例如：

- 震级和烈度有什么区别？
- 地震中的 tsunami alert 是什么意思？

有些问题需要同时查事件和文档，例如：

- 最近 M6.5 以上地震有哪些，并解释地震深度是什么意思？

还有些问题不应该查事件，也不应该做预测，例如：

- 明天东京会不会发生大地震？
- 最近小震很多是不是说明大震要来了？
- 最近某地地震很多，是不是更危险？

因此需要 Planner、工具路由、Evidence Pack 和 Safety Routing。

### 怎么做

当前系统使用 deterministic Planner 判断 query_type，并根据 query_type 调用不同工具：

- catalog -> safety_check + event_search + event_statistics
- concept -> safety_check + doc_retrieval
- mixed -> safety_check + event_search + event_statistics + doc_retrieval
- safety -> safety_check

所有工具输出会进入 Evidence Pack，再由 deterministic Generator 基于证据生成答案。

### 意义

Full System 是当前主方法，用来和后续 baseline 对比。

它的关键优势不是“回答更自然”，而是：

- 工具调用路径可控；
- 结构化事件查询参数可评估；
- 文档证据可追踪；
- Safety query 不会错误调用 event_search；
- 可以通过 eval 指标定位错误发生在哪一层。

### 不足

当前 Full System 仍然是 deterministic baseline，不是最终系统。

不足包括：

- Planner 是规则系统，泛化有限；
- doc_retrieval 是 keyword baseline，不是 BM25 / dense / hybrid；
- Generator 是模板，不是 LLM-backed；
- eval 只有 40 条；
- 没有 faithfulness 自动评估；
- 还没有真正 baseline comparison 结果。

---

## 3. Baseline 1：Doc-only RAG

### 是什么

Doc-only RAG 是最普通的文档问答 baseline。

它不使用结构化事件工具，不使用事件统计工具，也不做完整 Planner。

简化链路为：

用户问题 -> doc_retrieval -> Generator

### 为什么需要

这个 baseline 用来模拟很多普通 RAG demo 的做法：

不管用户问什么，都先检索文档，再生成答案。

它可以帮助验证：

当前系统相比普通文档 RAG，在结构化事件查询和安全工具路由上是否真的有优势。

### 怎么做

在实验中，Doc-only baseline 对所有非 safety query 都只调用 doc_retrieval。

对于 safety query，可以设计两个版本：

- Doc-only without safety：完全不做 safety_check；
- Doc-only with safety_check：先做 safety_check，再 doc_retrieval。

第一阶段可以先做简单版本：

- 所有 query 默认走 doc_retrieval；
- 不调用 event_search；
- 不调用 event_statistics；
- 不做结构化参数解析。

### 预期表现

Doc-only RAG 在 concept query 上可能表现较好。

例如：

- 震级和烈度有什么区别？
- 地震深度是什么意思？

但它在 catalog query 上会失败。

例如：

- 最近 M6.5 以上地震有哪些？

原因是文档检索无法返回结构化地震事件证据，也无法保证 min_magnitude 参数正确。

它在 mixed query 上也会失败或不完整。

例如：

- 最近 M6.5 以上地震有哪些，并解释地震深度是什么意思？

Doc-only 只能解释地震深度，无法查询事件。

### 评估重点

Doc-only RAG 应重点观察：

- event_evidence_hit_rate 是否下降；
- parameter_accuracy 是否无法计算或失败；
- tool_selection_accuracy 是否下降；
- mixed query 是否只能回答概念部分；
- safety query 是否误答或缺少安全拒答。

### 意义

这个 baseline 可以证明：

SeismoSearch 不是普通文档 RAG，因为历史地震事件查询需要结构化工具，而不是纯文档检索。

### 不足

Doc-only baseline 比较弱，但它是必要的最低基线。

面试时不能只和非常弱的 baseline 比，还需要后续加入 BM25、dense retrieval、hybrid retrieval 等更强 baseline。

---

## 4. Baseline 2：Structured-only Query

### 是什么

Structured-only Query 是只使用结构化事件工具的 baseline。

简化链路为：

用户问题 -> event_search / event_statistics -> Generator

它不做文档检索，也不解释概念。

### 为什么需要

这个 baseline 用来验证：

只有数据库查询是不够的。

因为 SeismoSearch 不只是地震 catalog 查询系统，还需要解释震级、烈度、地震深度、海啸提示等地震学概念。

### 怎么做

Structured-only baseline 对所有 query 尝试调用事件工具。

如果能解析震级或时间，就传入 event_search / event_statistics。

不调用 doc_retrieval。

第一阶段可以设计为：

- catalog query：调用 event_search + event_statistics；
- mixed query：只回答事件部分；
- concept query：无文档证据；
- safety query：容易误调用事件工具。

### 预期表现

Structured-only 在 catalog query 上可能表现较好。

例如：

- 2025 年 M6 以上地震有哪些？
- 最近 M6.5 以上地震有哪些？

但它在 concept query 上会失败。

例如：

- 震级和烈度有什么区别？
- tsunami alert 是什么意思？

它在 mixed query 上只能回答事件部分，不能解释概念。

它在 safety query 上风险较大，因为可能错误使用历史事件来回答未来风险判断。

### 评估重点

Structured-only 应重点观察：

- doc_evidence_hit_rate 是否下降；
- concept query 是否失败；
- mixed query 是否缺少文档解释；
- unsafe_tool_call_free_rate 是否下降；
- safety_refusal_accuracy 是否下降。

### 意义

这个 baseline 可以证明：

结构化工具有价值，但不能替代文档检索和 safety routing。

### 不足

Structured-only 仍然是弱 baseline，但它能帮助解释为什么需要 mixed query 和 doc evidence。

---

## 5. Baseline 3：No-safety Planner

### 是什么

No-safety Planner 是去掉 safety intent 优先级的 Planner baseline。

它仍然可以识别 catalog、concept、mixed，但不把未来预测、伪科学预兆、历史活动风险推断优先路由到 safety。

### 为什么需要

这个 baseline 非常关键。

它用来证明：

Safety Routing 不是装饰模块，而是系统安全边界的核心。

如果没有 safety-first routing，系统会把一些危险问题误路由到 catalog 或 concept。

例如：

- 最近动物异常是不是说明马上要地震了？
- 最近小震很多是不是说明大震要来了？
- 最近某地地震很多，是不是更危险？

这些问题都可能因为包含“最近”“地震”等词，被误判为历史事件查询。

### 怎么做

可以构造一个 no_safety_plan_query：

- 不调用 detect_safety_intent；
- 只使用 event_intent 和 concept_intent 判断 query_type；
- 继续根据 query_type 调用 event_search / doc_retrieval。

第一阶段不一定要改主系统代码，可以在 baseline runner 里模拟 no-safety 行为。

### 预期表现

No-safety Planner 在普通 catalog、concept、mixed query 上可能表现接近 Full System。

但在 safety query 上会明显失败：

- query_type_accuracy 下降；
- tool_selection_accuracy 下降；
- unsafe_tool_call_free_rate 下降；
- safety_refusal_accuracy 下降。

尤其是 safety query 中包含“最近”“地震很多”“小震”等词时，容易误调用 event_search。

### 评估重点

No-safety Planner 应重点观察：

- safety 样本中的 actual_tools；
- 是否错误调用 event_search；
- unsafe_tool_call_free_rate；
- safety_refusal_accuracy；
- no_prediction_violation_rate 是否仍然可能看起来正常。

### 意义

这个 baseline 可以证明：

只看最终答案是不够的，必须评估工具调用路径。

它也能证明 unsafe_tool_call_free_rate 是必要指标。

### 不足

No-safety Planner 是一个故意去掉安全模块的 ablation baseline，不是实际可上线系统。

它的价值在于做消融实验，证明 safety routing 的必要性。

---

## 6. 后续更强 Baseline

当前第一阶段先做 3 个简单 baseline：

- Doc-only RAG
- Structured-only Query
- No-safety Planner

后续还需要更强 baseline。

### 6.1 BM25 Retriever

是什么：

用 BM25 替代当前 keyword overlap retrieval。

为什么需要：

当前 doc_retriever 只是简单关键词 overlap，不能代表强检索 baseline。

怎么做：

对文档 chunk 建立 BM25 index，对 concept query 计算 BM25 分数。

意义：

验证 BM25 是否比当前 keyword baseline 更稳定，尤其是中英混合 query，例如 tsunami alert。

不足：

BM25 仍然是稀疏检索，对语义改写不够强。

---

### 6.2 Dense Retriever

是什么：

使用 embedding 进行向量检索。

为什么需要：

处理语义相近但关键词不完全匹配的问题。

怎么做：

对文档 chunk 编码成 embedding，对 query 编码后做向量相似度搜索。

意义：

测试 dense retrieval 对概念问答是否有提升。

不足：

需要模型、向量库和额外评估，且可能引入不可控语义匹配。

---

### 6.3 Hybrid Retrieval

是什么：

BM25 + Dense Retrieval 的融合方案。

为什么需要：

稀疏检索擅长关键词匹配，dense retrieval 擅长语义召回。Hybrid 可以结合两者优势。

怎么做：

使用 RRF 或加权分数融合 BM25 和 dense 的结果。

意义：

这是后续可以写成更完整 RAG 优化的方向。

不足：

需要更多文档、更系统的 gold evidence 标注，否则很难证明效果。

---

## 7. 对比指标

Baseline comparison 不能只看最终答案。

建议使用以下指标：

### 7.1 query_type_accuracy

评估 Planner 或 baseline 是否能正确识别 query 类型。

适用于：

- Full System
- No-safety Planner

Doc-only 和 Structured-only 可以记录为固定策略，不一定有完整 query_type。

---

### 7.2 tool_selection_accuracy

评估实际调用工具是否等于 gold_tools。

这是 baseline comparison 的核心指标之一。

例如：

Full System 对 safety query 应该只调用 safety_check。

Doc-only 会在 catalog query 上缺少 event_search。

Structured-only 会在 concept query 上缺少 doc_retrieval。

No-safety Planner 会在 safety query 上错误调用 event_search 或 doc_retrieval。

---

### 7.3 event_evidence_hit_rate

评估 catalog / mixed query 是否拿到正确事件证据。

Doc-only 预计会在该指标上表现差。

---

### 7.4 doc_evidence_hit_rate

评估 concept / mixed query 是否拿到正确文档证据。

Structured-only 预计会在该指标上表现差。

---

### 7.5 parameter_accuracy

评估结构化查询参数是否正确。

例如：

- M6.5 -> min_magnitude = 6.5；
- 2025 年 -> 时间范围覆盖全年。

Doc-only 无法处理结构化参数，因此在该指标上没有优势。

---

### 7.6 safety_refusal_accuracy

评估 safety query 是否被正确拒答。

No-safety Planner 和部分 Doc-only baseline 预计会表现差。

---

### 7.7 unsafe_tool_call_free_rate

评估 safety query 是否没有错误调用 event_search / event_statistics。

这是 Safety Routing 的关键指标。

---

## 8. 预期结果

第一阶段 baseline comparison 的预期结果如下。

Full System：

- catalog：表现好；
- concept：表现好；
- mixed：表现好；
- safety：表现好；
- 预期 eval_40 全指标 1.0。

Doc-only RAG：

- catalog：失败；
- concept：可能表现好；
- mixed：不完整；
- safety：不稳定；
- event_evidence_hit_rate 明显下降。

Structured-only Query：

- catalog：可能表现好；
- concept：失败；
- mixed：不完整；
- safety：风险较大；
- doc_evidence_hit_rate 明显下降。

No-safety Planner：

- catalog：可能表现好；
- concept：可能表现好；
- mixed：可能表现好；
- safety：明显失败；
- unsafe_tool_call_free_rate 明显下降。

---

## 9. 面试价值

Baseline comparison 能帮助回答以下面试问题：

### 9.1 你的方法相比普通 RAG 强在哪里？

回答：

普通 Doc-only RAG 无法处理结构化历史地震事件查询，也无法保证 M6.5、2025 年等参数解析正确。SeismoSearch 通过 Planner 把 catalog query 路由到 DuckDB 事件工具，并通过 event_evidence 和 computed_evidence 生成可追踪答案。

### 9.2 为什么需要 Safety Routing？

回答：

因为有些问题表面上包含“最近”“地震”等历史查询信号，但真实意图是未来风险推断。比如“最近某地地震很多，是不是更危险？”如果没有 Safety Routing，就会错误调用 event_search。No-safety Planner baseline 可以量化证明这一点。

### 9.3 为什么 Evidence Pack 有价值？

回答：

Evidence Pack 把 event_evidence、doc_evidence、computed_evidence 和 safety_constraints 统一组织起来，使 Generator 只能基于受控证据回答，也让 Evaluator 可以检查证据命中和工具路径。这比直接把工具输出塞给 LLM 更可控。

### 9.4 为什么 eval_40 全 1.0 还不够？

回答：

因为 eval_40 只说明当前系统通过了 40 条样本，不能证明泛化能力。Baseline comparison 可以进一步回答：当前方法是否真的比普通 RAG、结构化查询、无 safety routing 更好。

---

## 10. 实施计划

### 第一阶段：文档设计

完成：

- `docs/baseline_comparison_plan.md`

目标：

- 明确 baseline 类型；
- 明确每个 baseline 的预期失败点；
- 明确对比指标；
- 明确面试价值。

### 第二阶段：实现 baseline runner

新增脚本：

- `scripts/run_baseline_comparison.py`

目标：

- 对同一个 eval 文件运行不同 baseline；
- 输出各 baseline 的指标；
- 生成对比结果文件。

建议输出：

- `eval/results/baseline_comparison_eval_40.json`

### 第三阶段：新增 baseline report

新增文档：

- `docs/baseline_comparison_report.md`

目标：

- 记录各 baseline 结果；
- 分析 Full System 相比 baseline 的优势；
- 记录失败样本；
- 转化为简历和面试表达。

---

## 11. 当前限制

当前 baseline comparison 仍然是计划阶段，还没有实际运行结果。

因此现在只能说：

- 已完成 baseline comparison 设计；
- 下一步准备实现 baseline runner。

不能说：

- 已证明 Full System 显著优于普通 RAG；
- 已完成完整对比实验；
- 已完成 Hybrid RAG 效果验证。

---

## 12. 总结

Baseline comparison 是 SeismoSearch 从“能跑通 + eval 通过”进入“方法有效性验证”的关键一步。

eval_40 证明当前系统在现有样本上能工作。

baseline comparison 要进一步证明：

- Planner 是否必要；
- structured tools 是否必要；
- doc retrieval 是否必要；
- safety routing 是否必要；
- Evidence Pack 是否提高了可控性。

下一步应该实现 `scripts/run_baseline_comparison.py`，在 eval_40 上对比 Full System、Doc-only RAG、Structured-only Query 和 No-safety Planner。