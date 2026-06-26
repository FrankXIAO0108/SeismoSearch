# Data Card

## 1. 文件目的

本文件描述 SeismoSearch 项目中使用的数据来源、数据结构、数据处理流程、适用范围、限制和风险。

SeismoSearch 使用两类数据：

1. 公开地震事件目录数据；
2. 地震学知识文档数据。

本项目不使用私人数据，不使用用户隐私数据，不使用实时预警系统内部数据。

## 2. 数据使用目标

数据用于支持以下任务：

* 已发生地震事件查询；
* 按时间、震级、深度、地区等条件筛选地震事件；
* 地震事件统计分析；
* 地震目录字段解释；
* 地震学概念问答；
* 基于证据生成简要报告；
* 地震预测相关伪科学纠错；
* 风险沟通和安全边界回答。

数据不用于以下任务：

* 预测未来地震；
* 生成未来地震发生概率；
* 替代官方地震预警；
* 替代应急管理或防灾机构建议；
* 做个人撤离、搬家、买房、卖房或投资决策。

## 3. 地震事件数据

### 3.1 数据类型

地震事件数据是结构化目录数据。

每条事件通常包含：

* 事件 ID；
* 来源机构；
* 发生时间；
* 更新时间；
* 经度；
* 纬度；
* 深度；
* 震级；
* 震级类型；
* 地点描述；
* 事件类型；
* 审核状态；
* 震感报告；
* 烈度信息；
* tsunami 标记；
* alert 等级；
* 数据质量字段；
* 原始记录。

### 3.2 目标表

标准化后的事件数据进入 DuckDB 表：

```text
events
```

对应 schema 文件：

```text
schemas/events_schema.sql
```

### 3.3 数据分层

地震事件数据采用三层处理方式：

```text
raw data
-> staging layer
-> normalized events table
```

#### raw data

原始数据原样保存，不改字段、不删字段、不重命名。

示例目录：

```text
data/raw/events/
```

作用：

* 保留原始证据；
* 支持重新清洗；
* 支持字段复查；
* 避免清洗过程造成信息丢失。

#### staging layer

staging 层用于临时解析原始数据。

该层字段可以接近原始数据源字段，例如：

```text
time
updated
mag
magType
depth
place
id
type
status
```

作用：

* 检查字段是否存在；
* 检查数据类型；
* 检查缺失值；
* 检查异常值；
* 建立原始字段到标准字段的映射关系。

#### normalized events table

标准化后的数据写入：

```text
events
```

该层字段使用统一命名，例如：

```text
event_time_utc
updated_time_utc
magnitude
magnitude_type
depth_km
source_event_id
event_type
```

作用：

* 支撑结构化查询；
* 支撑统计分析；
* 支撑 Evidence Pack；
* 支撑自动评测；
* 降低数据源差异对下游模块的影响。

## 4. 地震学知识文档数据

### 4.1 数据类型

地震学知识文档是非结构化或半结构化文本数据。

文档内容包括：

* 地震基础概念；
* 震级和烈度解释；
* 震源深度解释；
* 地震目录字段解释；
* tsunami、alert、mmi、sig 等字段解释；
* 地震风险沟通；
* 防灾准备；
* 地震预测伪科学纠错。

### 4.2 目标表

文档切块后进入：

```text
doc_chunks
```

对应 schema 文件：

```text
schemas/doc_chunks_schema.sql
```

### 4.3 文档处理流程

文档数据采用以下流程：

```text
raw documents
-> parsed documents
-> doc_chunks
-> vector index
```

#### raw documents

原始文档保存在：

```text
data/raw/docs/
```

作用：

* 保留原始来源；
* 支持重新解析；
* 支持人工复查。

#### parsed documents

解析阶段提取：

* 标题；
* 来源；
* URL；
* 作者或机构；
* 发布时间；
* 章节结构；
* 正文内容。

#### doc_chunks

切块阶段将文档转换为检索单元。

每个 chunk 需要保留：

* chunk_id；
* doc_id；
* source_name；
* source_url；
* title；
* section_title；
* section_path；
* content；
* content_hash；
* topic_tags；
* embedding_model；
* vector_id。

## 5. 评测数据

第一版评测集计划包含 80 条问题：

```text
catalog：20 条
concept：20 条
mixed：20 条
safety：20 条
```

对应文件：

```text
eval/catalog_20.jsonl
eval/concept_20.jsonl
eval/mixed_20.jsonl
eval/safety_20.jsonl
eval/eval_80.jsonl
```

每条评测样本需要符合：

```text
schemas/eval_schema.json
```

评测样本不应只是问题文本，还必须包含：

* query_id；
* query；
* query_type；
* language；
* gold_tools；
* expected_behavior；
* metrics；
* gold_event_constraints；
* gold_doc_requirements；
* safety_labels。

## 6. 数据质量注意事项

### 6.1 地震目录限制

地震事件目录可能存在以下问题：

* 不同机构字段命名不同；
* 自动事件和人工审核事件质量不同；
* 震级类型可能不同；
* 地点描述不一定等同于国家归属；
* 海域地震的 country 字段可能不可靠；
* 事件可能后续更新；
* 不同目录之间可能存在重复事件；
* 震级、深度、位置可能存在误差。

因此，SeismoSearch 必须保留：

* source；
* source_event_id；
* source_url；
* detail_url；
* status；
* is_reviewed；
* raw_record_json；
* data_quality_note。

### 6.2 文档数据限制

地震学文档可能存在以下问题：

* 文档更新时间不同；
* 文档面向读者不同；
* 科普文档可能简化概念；
* 同一概念在不同来源中表述不完全一致；
* PDF 解析可能丢失结构；
* 网页抓取可能包含导航栏或无关文本；
* chunk 切分可能破坏上下文。

因此，SeismoSearch 必须保留：

* source_name；
* source_url；
* title；
* section_title；
* section_path；
* content_hash；
* fetched_time_utc；
* topic_tags；
* notes。

## 7. 数据不确定性处理

系统回答时应该说明以下不确定性：

* 数据来源；
* 查询时间范围；
* 统计口径；
* 事件是否 reviewed；
* 震级类型；
* 是否存在缺失字段；
* 是否使用了派生字段；
* 文档解释是否来自检索到的 chunk。

系统不应该：

* 把历史统计直接表达成未来预测；
* 把自动事件当作最终审核结果；
* 把 country 字段当作绝对地理事实；
* 把单一文档解释当作唯一权威结论；
* 隐藏数据缺失或不确定性。

## 8. 数据合规与隐私

本项目仅使用公开数据。

本项目不收集：

* 用户个人身份信息；
* 精确个人位置；
* 私人通信内容；
* 非公开灾害数据；
* 官方内部预警数据。

如果后续加入用户查询日志，必须默认脱敏，并且不能上传到公开仓库。

## 9. GitHub 数据提交规则

可以提交到 GitHub 的内容：

* schema 文件；
* 小规模样例数据；
* 评测集；
* 数据说明文档；
* 数据处理脚本；
* source list；
* chunking policy。

不应该提交到 GitHub 的内容：

* 大规模原始数据；
* DuckDB 数据库文件；
* 大型向量索引；
* 模型权重；
* checkpoint；
* 日志文件；
* 临时缓存；
* 私人数据。

`.gitignore` 应该排除：

```text
data/raw/
data/duckdb/
*.duckdb
*.duckdb.wal
*.parquet
*.csv
models/
checkpoints/
outputs/
runs/
logs/
```

## 10. 当前阶段数据状态

当前阶段：项目定义与数据骨架。

已完成：

* 项目目录骨架；
* README 初版；
* events schema；
* doc_chunks schema；
* evidence_pack schema；
* eval schema；
* risk_boundary 文档。

待完成：

* 1000 条地震事件样例；
* 10 篇地震学知识文档；
* doc_chunks 样例；
* eval_80.jsonl；
* 数据来源清单；
* 字段映射文档；
* 数据导入脚本。

## 11. 后续计划

后续需要补充：

* `docs/source_list.md`；
* `docs/event_field_mapping.md`；
* `docs/chunking_policy.md`；
* `scripts/ingest_events.py`；
* `scripts/ingest_docs.py`；
* `scripts/build_vector_index.py`；
* `eval/eval_80.jsonl`。

每次新增数据源，都必须更新本文件。
