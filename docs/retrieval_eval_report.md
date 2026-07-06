# SeismoSearch Retrieval Evaluation Report

## 1. 本阶段目标

本阶段目标是单独评估 SeismoSearch 的文档检索层，而不是只依赖 full pipeline 的整体评估结果。

在此前的 `eval_40` 中，系统已经可以在 concept / mixed query 上命中文档证据，并且 `doc_evidence_hit_rate = 1.0`。但是 full pipeline eval 只能说明最终 Evidence Pack 中存在合格的 doc_evidence，不能回答以下问题：

1. 当前 keyword retriever 的 Top-K 召回是否稳定？
2. 正确文档证据是否排在靠前位置？
3. Planner query rewrite 是否真的提升了检索效果？
4. 当前检索问题主要来自算法，还是来自语料组织？
5. 后续是否有必要引入 BM25 / dense retrieval / hybrid retrieval？

因此，本阶段新增 retrieval-layer evaluation，用来单独观察文档检索质量。

---

## 2. 当前检索模块状态

当前文档检索模块为：

`src/seismosearch/doc_retriever.py`

当前检索方式仍然是 deterministic keyword retrieval baseline，不是 BM25，也不是 dense retrieval。

当前检索流程：

用户问题 / Planner rewrite query
-> extract_query_terms
-> local Markdown chunk loading
-> heading-based chunking
-> weighted keyword overlap scoring
-> top-k chunks
-> doc_evidence

当前检索模块的定位是：

> 可解释、可调试、可评估的第一版 keyword retrieval baseline。

它的作用不是追求最终效果，而是为后续 BM25、dense retrieval 和 hybrid retrieval 提供可对比基线。

---

## 3. Retrieval Eval 数据集

本阶段新增：

`eval/retrieval_eval_20.jsonl`

共 20 条样本，覆盖：

- concept query：10 条
- mixed query 中的文档检索部分：10 条

每条样本包含：

- `query_id`
- `query`
- `expected_source_path_contains`
- `must_contain_terms`
- `expected_behavior`

当前 gold source 主要是：

`data/processed/docs/seismology_concepts.md`

评估目标不是判断最终答案质量，而是判断 retriever 是否能找回合格文档证据。

---

## 4. Retrieval Eval 指标

本阶段新增脚本：

`scripts/run_retrieval_eval.py`

评估指标包括：

### 4.1 source_hit_at_k

判断 Top-K 检索结果中是否包含预期 source path。

例如：

`seismology_concepts.md`

### 4.2 term_hit_at_k

判断 Top-K 检索结果中是否包含 gold terms。

例如：

- 震级
- 烈度
- 深度
- 海啸

### 4.3 requirement_hit_at_k

同时满足 source hit 和 term hit。

这是当前 retrieval eval 的主指标。

### 4.4 MRR

Mean Reciprocal Rank。

用于衡量第一个满足要求的 chunk 排在第几位。

如果正确 chunk 排在 rank 1，则 RR = 1.0。

如果正确 chunk 排在 rank 2，则 RR = 0.5。

如果正确 chunk 排在 rank 3，则 RR = 0.333。

MRR 比 Top-K hit 更敏感，可以暴露排序质量问题。

---

## 5. 初始评估结果

在初始版本中，分别评估两种 query mode：

- `planner`：使用 Planner 生成的 doc_retrieval_queries
- `raw`：只使用用户原始 query

初始结果如下：

| Query Mode | num_samples | source_hit@5 | term_hit@5 | requirement_hit@5 | MRR | failed_records |
|---|---:|---:|---:|---:|---:|---:|
| planner | 20 | 1.00 | 1.00 | 1.00 | 0.7667 | 0 |
| raw | 20 | 1.00 | 1.00 | 1.00 | 0.8000 | 0 |

从 Top-5 命中率看，当前 keyword retriever 能够找回满足要求的文档证据。

但是 MRR 不到 1.0，说明正确证据经常不是 rank 1。

这意味着：

> full pipeline eval 通过，不代表 retrieval ranking 没有问题。Top-K hit 通过，也不代表 rank-level ordering 是好的。

---

## 6. Rank-level Badcase 分析

进一步查看 reciprocal_rank < 1.0 的样本后，发现多个 concept / mixed query 的 rank 1 被非用户知识文档占据。

典型现象：

- `docs/source_list.md` 排在 rank 1
- `docs/progress.md` 排在前列
- `docs/baseline_comparison_plan.md` 排在前列
- 真正应该作为知识来源的 `seismology_concepts.md` 排在 rank 2 / rank 3 / rank 4

例如：

- “地震震级是什么意思？”
- “地震烈度是什么意思？”
- “请解释震级的定义。”
- “最近 M6 以上地震有哪些，并解释震级是什么意思？”

这些 query 都可能被 `docs/source_list.md` 等工程文档干扰。

---

## 7. 根因分析

### 7.1 问题不是简单的算法问题

初始结果中 Top-5 命中率已经达到 1.0，说明 retriever 具备基本召回能力。

真正的问题是 ranking。

### 7.2 语料污染是主要问题

原始 `DEFAULT_DOC_DIRS` 同时包含：

- `data/processed/docs`
- `docs`

其中 `data/processed/docs` 是面向用户回答的领域知识文档。

而 `docs` 中包含大量项目管理文档，例如：

- source list
- progress report
- badcase log
- eval report
- baseline comparison plan

这些文档会包含“地震、震级、烈度、magnitude、intensity”等关键词，但它们并不是适合作为用户答案证据的领域知识文档。

因此，retriever 会把项目文档误排到用户知识文档前面。

这属于典型的 RAG corpus hygiene 问题。

### 7.3 Planner rewrite 并不天然提升检索

初始评估中：

- planner MRR = 0.7667
- raw MRR = 0.8000

Planner rewrite 没有提升 MRR，反而略低。

原因是 Planner rewrite 会增加一些宽泛扩展词，例如：

- earthquake
- magnitude
- intensity
- definition
- seismic

这些词提升了召回，但也让 source_list / progress 等项目文档获得更高分，导致排序被污染。

这说明：

> query rewrite 不能凭直觉判断有效，必须通过 retrieval metrics 验证。

---

## 8. 修复方案

本轮修复重点不是直接引入 BM25，而是先修复 corpus hygiene。

### 8.1 收敛默认检索语料

将默认检索语料从：

`data/processed/docs + docs`

收敛为：

`data/processed/docs`

这样普通用户 query 只检索面向用户回答的领域知识文档，不再默认检索项目管理文档。

### 8.2 保留 deterministic keyword baseline

当前仍然保持 keyword retrieval，不引入 BM25 或 dense retrieval。

原因是：

1. 需要先把基础 corpus hygiene 做干净。
2. 否则即使用 BM25，也可能继续被污染语料干扰。
3. 当前阶段目标是先建立可解释 baseline，而不是直接堆算法。

### 8.3 加入轻量权重调整

对 keyword scoring 做了轻量调整：

- 高价值中文领域词提高权重，例如：震级、烈度、深度、海啸；
- 通用词降低权重，例如：地震、earthquake、definition、meaning；
- 仅在 chunk 有真实 matched_terms 时，才加 corpus-quality prior；
- 防止无关 query 因为 corpus prior 返回任意 chunk。

### 8.4 修复 unrelated query 返回 chunk 的问题

在修复过程中发现一个 bug：

如果 corpus-quality prior 无条件加分，那么无关 query 也会返回 `data/processed/docs` 中的 chunk。

例如：

`completely unrelated cooking recipe`

该问题导致 `tests/test_doc_retriever.py` 中的 unmatched query 测试失败。

修复后：

- 只有 chunk 至少命中一个真实 query term，才允许进入 scored_chunks；
- 如果没有提取到 query terms，返回空 chunks，并给出 warning。

---

## 9. 修复后结果

修复后重新运行：

`python -m pytest tests/test_doc_retriever.py`

结果：

- 4 passed

重新运行全量测试：

`python -m pytest tests`

结果：

- 44 passed

重新运行 retrieval eval：

### 9.1 Planner Query Mode

| Metric | Value |
|---|---:|
| num_samples | 20 |
| source_hit_at_k | 1.00 |
| term_hit_at_k | 1.00 |
| requirement_hit_at_k | 1.00 |
| MRR | 1.00 |
| failed_records | 0 |

### 9.2 Raw Query Mode

| Metric | Value |
|---|---:|
| num_samples | 20 |
| source_hit_at_k | 1.00 |
| term_hit_at_k | 1.00 |
| requirement_hit_at_k | 1.00 |
| MRR | 1.00 |
| failed_records | 0 |

### 9.3 对比结果

| Query Mode | Before MRR | After MRR |
|---|---:|---:|
| planner | 0.7667 | 1.0000 |
| raw | 0.8000 | 1.0000 |

修复后，planner 和 raw 两组在 retrieval_eval_20 上都达到了 MRR = 1.0。

这说明当前主要问题不是 keyword baseline 无法召回，而是默认检索语料中混入了不适合作为用户答案证据的项目文档。

---

## 10. 工程启示

### 10.1 RAG 不是把所有文档扔进检索器

项目文档、来源说明、评估报告、badcase 记录都可能包含大量领域关键词。

如果直接把它们和领域知识文档混在一起，会污染用户回答证据。

因此，RAG 系统需要区分：

- user-facing knowledge corpus
- engineering/project documents
- evaluation documents
- data source metadata
- safety/boundary documents

不同 corpus 应该有不同用途，不能默认全部作为 answer evidence。

### 10.2 Top-K 命中不等于排序质量好

初始版本中，Top-5 requirement hit 已经是 1.0，但 MRR 明显低于 1.0。

这说明正确 chunk 虽然被找回，但排序不稳定。

因此 retrieval eval 不能只看 Recall@K，还要看：

- MRR
- NDCG
- rank-level badcase
- source distribution
- corpus contamination

### 10.3 Query rewrite 需要被评估

Planner rewrite 不是天然有效。

如果 rewrite 引入了过多泛化词，可能提高召回，但降低排序质量。

本阶段初始结果中 planner MRR 低于 raw MRR，说明 query rewrite 必须通过 retrieval eval 验证，而不是凭直觉认为它一定有效。

### 10.4 先修 corpus hygiene，再上更强算法

BM25 / dense retrieval / hybrid retrieval 都不是万能药。

如果语料本身混乱，强检索器也可能把错误类型文档排到前面。

因此本阶段优先修复 corpus filtering，这是更底层的数据工程问题。

---

## 11. 当前限制

本阶段结果不能过度解读。

当前 retrieval_eval_20 只有 20 条样本，且 gold source 主要集中在 `seismology_concepts.md`。

当前 keyword scoring 仍然是规则系统，不是 BM25，也不是 dense retrieval。

当前 MRR = 1.0 只能说明在 retrieval_eval_20 上表现良好，不能证明泛化到更复杂文档库。

当前 query type 主要覆盖：

- 震级
- 烈度
- 地震深度
- 海啸提示
- tsunami alert

还没有覆盖更多地震学概念、长文档、多来源冲突、跨文档综合、真实网页语料等情况。

---

## 12. 后续计划

下一步不应继续手工堆 keyword 权重，而应进入更正式的 retrieval baseline comparison。

计划包括：

1. 扩展 retrieval_eval_40。
2. 引入 BM25 retriever。
3. 对比 keyword vs BM25。
4. 增加 Recall@1、Recall@3、Recall@5、MRR、NDCG。
5. 分析 BM25 是否在更复杂 query 和更大 corpus 下优于当前 keyword baseline。
6. 后续再引入 dense retrieval 和 hybrid retrieval。
7. 对 query rewrite 单独做 ablation，比较 raw query vs planner rewrite vs manual expansion。

---

## 13. 面试表达

可以这样描述本阶段工作：

我没有直接把所有 Markdown 文档都扔进 RAG 检索器，而是先构建了 retrieval_eval_20，单独评估 concept 和 mixed query 的文档检索质量。初始结果中 Top-5 requirement hit 是 1.0，但 MRR 只有 0.77 到 0.8。通过 rank-level inspection，我发现 source_list.md、progress.md 这类项目文档经常排在真正的 seismology_concepts.md 前面。

这说明问题首先不是 BM25 或 dense retrieval，而是 corpus hygiene。于是我把默认用户问答检索语料收敛到 data/processed/docs，只保留面向用户回答的领域知识文档，并对 keyword scoring 做了轻量权重调整。修复后 retrieval_eval_20 中 planner/raw 两组 source_hit@5、term_hit@5、requirement_hit@5 和 MRR 都达到 1.0，同时全量 pytest 44 条通过。

这个过程让我意识到，RAG 检索优化不能只看算法，还要先保证语料分层和检索语料边界清晰。