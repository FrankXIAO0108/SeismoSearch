# SeismoSearch

> 面向公开地震目录与地震学知识文档的工具增强型 Agentic RAG 原型：用确定性 Planner 编排结构化事件查询、混合文档检索、安全检查和证据约束生成。

SeismoSearch 不是“地震预测机器人”。它解决的是另一类更可验证的问题：

- 查询已经发生的地震事件；
- 按时间、震级等条件做结构化过滤和统计；
- 解释震级、烈度、深度、目录字段和事件修订机制；
- 组合事件证据与文档证据回答混合问题；
- 拒绝未来具体地震预测和伪科学诱导；
- 对回答中的证据 ID、引用来源和评测契约进行自动检查。

项目重点不是堆叠一个聊天界面，而是把 **任务路由、工具选择、检索、证据构造、生成、安全和评测** 拆成可检查的模块。

---

## 1. 项目解决什么问题

普通文档 RAG 不适合独立处理地震目录查询。

例如：

```text
列出 2025 年 M6.5 以上地震。
```

这是结构化过滤、排序和统计问题，适合查询 DuckDB，而不是让向量检索“猜”答案。

而：

```text
为什么同一个事件的 magnitude 后续还可能变化？
```

需要检索地震事件更新、人工审核和数据修订文档。

再例如：

```text
列出 M6.6 以上事件，并解释相同震级的地震影响为什么可能不同。
```

同时需要结构化事件工具和文档检索，因此属于混合任务。

SeismoSearch 将问题划分为：

| Query Type | 主要能力 |
|---|---|
| `catalog` | 结构化事件检索与统计 |
| `concept` | 地震学与目录字段文档问答 |
| `mixed` | 事件工具与文档检索组合 |
| `safety` | 未来预测、伪科学与风险沟通边界 |

---

## 2. 系统架构

```text
User Query
    |
    v
Unified Safety Gate
    |
    v
Deterministic Planner
    |
    +----------------------+----------------------+
    |                      |                      |
    v                      v                      v
Event Tools           Document Retrieval      Safety Check
- event_search        - keyword              - prediction inducement
- event_statistics    - BM25                 - pseudoscience
                      - dense embeddings      - unsafe tool short-circuit
                      - Hybrid RRF
                      - CrossEncoder rerank
    |                      |                      |
    +----------------------+----------------------+
                           |
                           v
                     Evidence Pack
                           |
                +----------+-----------+
                |                      |
                v                      v
     Deterministic Generator      LLM Generator
                                  - strict JSON
                                  - evidence-ID validation
                                  - deterministic fallback
                |                      |
                +----------+-----------+
                           |
                           v
                 Citation / Contract Eval
```

核心设计：

1. **确定性 Planner**  
   通过可检查规则完成 Query Type、工具路由、参数解析和检索 Query Rewrite，而不是把全部控制权交给 LLM。

2. **结构化事件工具**  
   归一化事件数据进入 DuckDB，支持震级过滤、时间过滤、排序、事件列表和聚合统计。

3. **混合文档检索**  
   本地 Markdown 语料支持 keyword、BM25、dense、BM25+dense RRF，以及 CrossEncoder rerank。当前实现是本地内存检索，不是向量数据库。

4. **Evidence Pack**  
   将 Planner 输出、工具调用、事件证据、统计证据、文档证据、安全标签和回答约束组织为统一上下文。

5. **双 Generator**  
   Deterministic Generator 用于可重复 baseline；LLM Generator 使用 OpenAI-compatible 接口、严格 JSON 校验、可用证据 ID 校验和失败回退。

6. **统一安全短路**  
   安全 Query 只允许调用 `safety_check`，不应继续执行事件检索、文档检索或 LLM 生成。

7. **可冻结评测**  
   官方 V1/V2 Holdout 在执行前冻结；观察失败后不覆盖首轮结果，只用合成回归测试验证修复。

---

## 3. 数据与语料分层

```text
data/raw/
    原始公开数据

data/processed/
    归一化事件 JSONL
    面向用户回答的 Markdown 文档
    可选的版本化扩展语料

data/duckdb/
    可复现生成的本地 DuckDB 运行时文件
```

运行时文档检索默认只读取：

```text
data/processed/docs/
```

评测报告、进度文档、数据卡和项目管理文档不会进入用户回答语料，避免 corpus contamination。

样例事件库不是完整全球地震目录。Catalog 回答必须明确本地样例范围，不能把样例统计描述成全球完整统计。

### 3.1 Data Expansion V1

项目现提供一个可重建的大规模事件快照：2021-01-01 至 2025-12-31、全球 M4.5+ earthquake，共 39,320 条。大文件和 DuckDB 均为可再生运行时产物，Git 只保留构建脚本、来源和质量 Manifest。

同时新增 8 篇 USGS/FEMA 来源的版本化文档，位于 `data/processed/docs_expansion_v1/`。它们默认不混入原有语料：扩容不等于无条件上线，合并前仍需要独立盲测。详见 [`docs/data_expansion_v1.md`](docs/data_expansion_v1.md)。

---

## 4. Retrieval Baseline

在冻结的 26-query Retrieval Holdout 上：

| Retrieval Configuration | Source Hit Rate | Requirement Hit Rate | MRR |
|---|---:|---:|---:|
| Planner + Hybrid RRF | 76.92% | 61.54% | 0.5705 |
| Planner + Hybrid RRF + CrossEncoder | 96.15% | 88.46% | 0.6071 |

项目没有因为“用了向量模型”就默认 dense 最优，而是对 keyword、BM25、dense、hybrid 和 reranker 做了 baseline 对比。

当前 reranker 默认只处理 10 个候选 Chunk。开发集上，`candidate_k=10` 与更大的候选集保持相同的 Requirement Hit Rate，同时降低推理延迟。

---

## 5. End-to-End Holdout V2

官方 V2 是一个冻结的 20-query 首轮 Holdout。结果在观察失败后没有被覆盖。

### 5.1 质量指标

| Metric | Deterministic | LLM |
|---|---:|---:|
| Contract Pass | 75.00% | 85.00% |
| Query Type Correct | 90.00% | 90.00% |
| Tool Selection Correct | 90.00% | 90.00% |
| Parameter Correct | 100.00% | 100.00% |
| Event Evidence Correct | 95.00% | 95.00% |
| Document Evidence Correct | 90.00% | 90.00% |
| Citation Validity | 100.00% | 100.00% |
| Required Terms Correct | 80.00% | 90.00% |
| Safety Refusal Correct | 80.00% | 80.00% |
| Citation Support Valid | 80.00% | 86.67% |

非 Safety 样本上的 LLM 状态：

```text
Native LLM Success: 13 / 15 = 86.67%
Deterministic Fallback: 2 / 15 = 13.33%
```

### 5.2 延迟

| Metric | Value |
|---|---:|
| Evidence Pack Mean | 2.339 s |
| Evidence Pack P95 | 3.849 s |
| Evidence Pack Max | 23.929 s |
| Deterministic E2E Mean | 2.339 s |
| LLM Generation Mean | 1.908 s |
| LLM E2E Mean | 4.247 s |
| LLM E2E P95 | 6.839 s |

最大延迟可能包含模型或 reranker 冷启动，但当前只有单轮数据，不能把该推断写成确定结论。

完整分析见：

- [End-to-End Holdout V2 Failure Analysis](docs/end_to_end_holdout_v2_failure_analysis.md)
- [Generator Comparison V2](docs/generator_comparison_eval_report_v2.md)
- [Baseline Comparison Plan](docs/baseline_comparison_plan.md)

---

## 6. V2 失败分层

V2 的五个 Deterministic 失败并不都属于“检索不准”：

| Failure | Root Cause |
|---|---|
| `catalog_005` | Catalog 意图同义改写覆盖不足 |
| `concept_003` | `magnitude + 更新/修订` Query Rewrite 缺失 |
| `concept_005` | Generator 只消费 Top-1 Chunk |
| `mixed_005` | 中英文术语对齐与评测 Exact Match 脆弱 |
| `safety_005` | Safety Context 未覆盖“强震” |

对应修复均通过独立回归测试，但没有回写或重跑官方 V2。

这一区分是项目的核心：  
**路由错误、Query Rewrite 错误、检索错误、证据选择错误和生成错误必须分别定位，不能统一归因成 RAG 效果不好。**

---

## 7. Citation Contract

SeismoSearch 区分：

```text
Citation Validity
= 引用的 Evidence ID 是否真实存在并与生成元数据一致

Citation Support
= 被引用的 Evidence 是否满足样本所需的来源和内容要求
```

V2 中 Citation Validity 为 100%，但 Citation Support 未达到 100%。这说明：

```text
引用格式正确 != 回答被相关证据支持
```

当前 Citation Support 是确定性代理指标，不是 Claim-Level NLI。它适合发现“引用了真实但不相关的 Chunk”，不能宣称已经完成语义蕴含验证。

---

## 8. Safety Boundary

SeismoSearch 支持：

- 已发生事件查询；
- 历史目录统计；
- 地震学概念解释；
- 官方字段解释；
- 伪科学纠错；
- 应急信息和风险沟通方向。

SeismoSearch 不支持：

- 给出未来具体地震的日期、地点、震级或概率；
- 根据动物异常、地震云或历史小震做确定性预测；
- 把历史活动直接外推成短期预测；
- 替代官方预警、应急管理和专业风险评估；
- 基于不完整样例库给出个人撤离、房产或投资决策。

---

## 9. Quick Start

### 9.1 创建环境

Windows PowerShell：

```powershell
git clone https://github.com/FrankXIAO0108/SeismoSearch.git
cd SeismoSearch

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install duckdb numpy pytest
```

使用 dense、hybrid 或 CrossEncoder rerank 时，再安装：

```powershell
python -m pip install sentence-transformers
```

设置源码路径：

```powershell
$env:PYTHONPATH="$PWD\src"
$env:PYTHONIOENCODING="utf-8"
```

### 9.2 构建事件数据库

```powershell
python .\scripts\build_event_db.py
```

脚本读取：

```text
data/processed/events_sample_1000.jsonl
```

并生成：

```text
data/duckdb/seismosearch.duckdb
```

DuckDB 文件是可复现运行时产物，不需要提交到 Git。

### 9.3 跑测试

```powershell
python -m pytest -q
```

当前本地全量回归结果：

```text
167 passed
```

### 9.4 运行 Deterministic Pipeline

使用无需模型下载的 keyword baseline：

```powershell
python -c "import json; from seismosearch.pipeline import run_pipeline; result=run_pipeline('震级和烈度有什么区别？', generator_mode='deterministic', doc_retriever_mode='keyword'); print(json.dumps(result, ensure_ascii=False, indent=2))"
```

使用完整 Hybrid + Reranker：

```powershell
python -c "import json; from seismosearch.pipeline import run_pipeline; result=run_pipeline('horizontalError 和 depthError 有什么不同？', generator_mode='deterministic', doc_retriever_mode='hybrid_rerank'); print(json.dumps(result, ensure_ascii=False, indent=2))"
```

首次运行 dense/reranker 会下载模型：

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
```

### 9.5 运行 LLM Generator

LLM Client 使用 OpenAI-compatible `/chat/completions` 接口。

```powershell
$env:SEISMOSEARCH_LLM_BASE_URL="https://api.deepseek.com"
$env:SEISMOSEARCH_LLM_API_KEY="<YOUR_API_KEY>"
$env:SEISMOSEARCH_LLM_MODEL="deepseek-v4-flash"

$env:SEISMOSEARCH_LLM_JSON_MODE="true"
$env:SEISMOSEARCH_LLM_THINKING_MODE="disabled"
$env:SEISMOSEARCH_LLM_MAX_TOKENS="1800"
```

运行：

```powershell
python -c "import json; from seismosearch.pipeline import run_pipeline; result=run_pipeline('为什么同一个事件的 magnitude 后续还可能变化？', generator_mode='llm', doc_retriever_mode='hybrid_rerank'); print(json.dumps(result, ensure_ascii=False, indent=2))"
```

API Key 不应写入代码、README、测试文件或提交记录。

---

## 10. Evaluation Artifacts

```text
eval/
    retrieval holdouts
    generator comparison holdouts
    end-to-end holdout V1
    end-to-end holdout V2
    manifests
    frozen result files

scripts/
    retrieval evaluation runners
    generator comparison runners
    end-to-end V1/V2 runners
    independent Evaluation Contract 2.1 runner
```

评测纪律：

1. Holdout 数据、Manifest 和 Hash 先冻结并提交；
2. 再执行官方首轮评测；
3. 首轮结果立即保存并提交；
4. 看到失败后不修改原 Holdout；
5. 修复使用合成 Regression Tests；
6. 新的官方分数必须来自新的冻结 Holdout。

`run_end_to_end_eval_v2_1.py` 是独立 Evaluation Contract 2.1 入口，用于新开发集或未来新 Holdout。它会拒绝官方 V1/V2 的文件名，避免误覆盖历史结果。

---

## 11. 目录结构

```text
SeismoSearch/
├─ data/
│  ├─ raw/
│  ├─ processed/
│  │  ├─ events_sample_1000.jsonl
│  │  └─ docs/
│  └─ duckdb/
├─ schemas/
│  └─ events_schema.sql
├─ src/seismosearch/
│  ├─ guardrail.py
│  ├─ planner.py
│  ├─ tools.py
│  ├─ event_store.py
│  ├─ doc_retriever.py
│  ├─ bm25_retriever.py
│  ├─ dense_retriever.py
│  ├─ hybrid_retriever.py
│  ├─ reranker.py
│  ├─ evidence_builder.py
│  ├─ generator.py
│  ├─ llm_client.py
│  ├─ llm_generator.py
│  ├─ citation_support.py
│  ├─ evaluation_terms.py
│  └─ pipeline.py
├─ scripts/
├─ eval/
├─ tests/
└─ docs/
```

---

## 12. 当前限制

- 当前事件库是固定本地样例，不是实时全球目录；
- 地区和经纬度自然语言解析仍不完整；
- dense 和 reranker 使用本地内存推理，不是生产向量数据库；
- Safety Gate 是确定性规则系统，仍可能漏掉新表达；
- 中文多概念问题的 Deterministic Generator 仍偏保守；
- Citation Support 不是 Claim-Level Entailment；
- LLM 的正确性受 Evidence Pack 质量限制；
- 当前没有生产级监控、权限、限流、高可用和在线数据新鲜度保障。

因此，本项目应描述为：

```text
可评测、可追溯的工具增强型 Agentic RAG 原型
```

不应描述为：

```text
生产级地震预测系统
完整多智能体平台
GraphRAG
端到端训练 Agent
```

---

## 13. 面试表达

推荐项目概述：

> 我构建了一个地震目录与地震学知识问答的 Agentic RAG 原型。系统使用确定性 Planner 将请求路由到 DuckDB 事件工具、Hybrid RRF + CrossEncoder 文档检索或 Safety Gate，再统一构造成 Evidence Pack，分别供 Deterministic 和 LLM Generator 使用。LLM 输出必须通过 JSON、可用 Evidence ID 和引用契约校验，失败时回退到确定性生成。在冻结的 20-query V2 Holdout 上，Deterministic 与 LLM Contract Pass 分别为 75% 和 85%；我进一步将失败拆解到路由、Query Rewrite、检索、证据选择、语言归一和安全层，并使用合成回归测试修复，而没有覆盖首轮 Holdout 结果。

这个项目真正要展示的不是“调用了 RAG”，而是：

- 为什么结构化事件数据不能只用文档检索；
- Planner 为什么需要可解释的工具路由；
- 如何区分 Retrieval Recall 与 Generator Evidence Selection；
- 如何区分 Citation Validity 与 Citation Support；
- 为什么 LLM 不能修复缺失证据和错误路由；
- 如何冻结 Holdout 并保留真实 Badcase；
- 如何把 Safety 做成执行前短路，而不是只在答案末尾补一句免责声明。
