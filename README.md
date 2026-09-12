# SeismoSearch

> 面向地震目录查询与地震学知识问答的工具增强型 RAG 系统，支持证据约束回答、安全边界控制和可复现评测。

SeismoSearch 将结构化事件工具与文档检索结合起来：精确筛选和统计交给 DuckDB，领域解释交给文档检索，最终回答统一基于可审计的 Evidence Pack 生成。

本项目不预测未来地震，也不替代官方监测、预警或应急指导。

## 项目能力

| 问题类型 | 示例 | 执行路径 |
|---|---|---|
| `catalog` | 查询某时间范围内的 M6.5+ 地震 | Planner → DuckDB 事件工具 |
| `concept` | 解释震级、烈度、深度或目录字段 | Planner → 文档检索 |
| `mixed` | 查询地震事件并解释其影响差异 | 事件工具 + 文档检索 |
| `safety` | 要求预测未来地震 | Safety Gate → 有边界的拒答 |

## 系统架构

```text
用户问题
    │
    ▼
统一安全门
    │
    ▼
确定性 Planner
    │
    ├── 事件工具 ─────── DuckDB 查询与统计
    ├── 文档工具 ─────── Keyword / BM25 / Dense / Hybrid / Rerank
    └── 安全工具 ─────── 预测诱导与伪科学边界识别
    │
    ▼
Evidence Pack
    │
    ├── 确定性 Generator
    └── OpenAI-compatible LLM Generator
    │
    ▼
引用校验与契约评测
```

## 核心设计

### 确定性规划

`src/seismosearch/planner.py` 负责识别问题类型、解析时间范围和震级阈值、生成文档检索 Query Rewrite，并生成工具参数。路由过程不依赖 LLM，便于复现、调试和回归测试。

### 结构化事件工具

`event_search` 和 `event_statistics` 支持按时间、震级、深度、经纬度、事件类型、审核状态和排序条件查询历史事件。精确过滤和聚合使用 DuckDB，不让向量检索猜测数值答案。

### 混合文档检索

文档层支持关键词、BM25、Dense Embedding、RRF 融合和 CrossEncoder 重排。默认只检索 `data/processed/docs/`，避免项目笔记和评测文件污染回答语料。

### Evidence Pack 与受约束生成

Evidence Pack 统一组织 Planner 输出、工具调用、事件证据、统计证据、文档证据、安全标签和回答约束。LLM Generator 只能读取受控证据上下文，必须返回严格 JSON，并且只能引用真实存在的证据 ID；校验失败时回退到确定性生成器。

### 安全边界

统一 Safety Gate 在后续检索之前执行。对于未来具体地震预测、动物异常预测、地震云和历史小震推断等问题，系统会短路处理，不继续调用事件查询或 LLM 生成。

## 数据

仓库包含用于本地运行的默认样例：

```text
data/processed/events_sample_1000.jsonl
data/processed/docs/
```

同时提供可重建的 USGS 事件数据扩展：

- 2021–2025 年全球地震事件；
- M4.5+，并过滤 `eventtype=earthquake`；
- 归一化、重复、无效记录和缺失震级检查；
- 8 篇 USGS/FEMA 参考文档；
- 查询参数、窗口统计和 SHA-256 记录在 `data/processed/events_catalog_2021_2025_m45.manifest.json`。

大体积 JSONL 和 DuckDB 文件属于生成产物，不直接提交到 Git。详见 [`data_card.md`](data_card.md) 和 [`docs/data_expansion_v1.md`](docs/data_expansion_v1.md)。

## 快速开始

Windows PowerShell：

```powershell
git clone https://github.com/FrankXIAO0108/SeismoSearch.git
cd SeismoSearch

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install duckdb numpy pytest

$env:PYTHONPATH="$PWD\src"
$env:PYTHONIOENCODING="utf-8"
python .\scripts\build_event_db.py
python -m pytest -q
```

不依赖 LLM 的确定性示例：

```powershell
python -c "import json; from seismosearch.pipeline import run_pipeline; result=run_pipeline('震级和烈度有什么区别？', generator_mode='deterministic', doc_retriever_mode='keyword'); print(json.dumps(result, ensure_ascii=False, indent=2))"
```

使用 Dense 或 CrossEncoder 检索时，再安装 `sentence-transformers`。首次运行会下载配置的模型，之后可以使用本地缓存。

## 可选事件数据扩展

```powershell
python .\scripts\build_event_catalog_snapshot.py `
  --starttime 2021-01-01 `
  --endtime 2026-01-01 `
  --min-magnitude 4.5 `
  --event-type earthquake `
  --processed-output data\processed\events_catalog_2021_2025_m45.jsonl `
  --manifest-output data\processed\events_catalog_2021_2025_m45.manifest.json `
  --raw-output-dir data\raw\events\catalog_2021_2025_m45

python .\scripts\build_event_db.py `
  --input data\processed\events_catalog_2021_2025_m45.jsonl `
  --db data\duckdb\seismosearch_catalog_2021_2025_m45.duckdb
```

扩展数据库不会自动替换默认运行库，避免数据更新悄悄改变基线评测环境。

## 评测

项目同时评测检索模块和完整流程：

- Source、Term、Requirement Hit@K 和 MRR；
- Query Type 与 Tool Selection；
- 事件证据和文档证据支持度；
- 引用 ID 有效性与引用内容支持度；
- 安全拒答行为；
- Deterministic Generator 与 LLM Generator 的回退行为。

当前本地测试套件为 `167 passed`。扩展开发集 16 个问题的 Requirement Hit@5 为 1.0；这是用于迭代的开发集，不是独立盲测成绩。冻结评测输入和结果保存在 `eval/`。

## 仓库结构

```text
src/seismosearch/      Planner、工具、检索、证据和生成模块
schemas/               事件、文档、评测和证据数据契约
data/processed/        默认事件样例和用户侧知识语料
scripts/               数据导入、数据库构建和评测入口
eval/                  冻结评测输入与结果
tests/                 单元、集成、安全、引用和 Pipeline 测试
docs/                  数据与 Holdout 说明
```

## 项目边界

SeismoSearch 是一个面向研究和验证的 RAG 工程原型，不提供多租户权限、高可用、生产监控、在线数据新鲜度保障或完整全球地震目录。项目重点是把路由、工具、检索、证据、生成、安全和评测拆成可独立检查的模块。
