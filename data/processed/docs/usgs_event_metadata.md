# USGS Event Metadata

## 文档目的

本文档解释 SeismoSearch 使用的 USGS 地震事件数据及其元数据含义。

SeismoSearch 使用公开地震事件数据构建本地样例库，用于历史事件查询、结构化统计和证据生成。

本文档不用于未来地震预测。

---

## Data Source

SeismoSearch 当前事件数据来自公开地震事件目录。

数据经过以下处理流程：

```text
raw event data
-> processed JSONL
-> DuckDB events table
-> EventStore query layer
-> event_search_tool / event_statistics_tool
```

这种分层设计有助于保证：

- 原始数据可追溯；
- 中间数据可检查；
- 查询接口稳定；
- 评估结果可复现。

---

## Local Sample Database

当前 SeismoSearch 使用的是本地样例数据库。

这意味着：

- 数据规模有限；
- 时间范围有限；
- 不能代表完整全球地震目录；
- 查询结果只反映样例库中的事件；
- 统计结果只对当前样例库有效。

因此，在回答 catalog query 时，系统应明确说明数据范围限制。

---

## Raw Layer

Raw layer 保存原始数据。

它的作用是：

- 保留外部数据源的原始结构；
- 支持后续重新清洗；
- 支持错误追溯；
- 避免直接覆盖原始信息。

Raw layer 不应该直接暴露给最终用户回答。

---

## Processed Layer

Processed layer 将原始事件数据转换为 SeismoSearch 内部统一格式。

典型字段包括：

- event_id；
- time；
- place；
- magnitude；
- depth_km；
- latitude；
- longitude；
- event_type；
- tsunami_flag。

Processed layer 的目标是形成稳定、可查询、可评估的数据格式。

---

## Database Layer

Database layer 使用 DuckDB 保存结构化事件表。

它支持：

- 震级过滤；
- 时间过滤；
- 排序；
- 聚合统计；
- 结构化工具调用；
- 可复现评估。

例如：

```text
min_magnitude = 6.5
sort_by = time
limit = 5
```

这类条件适合数据库查询，而不适合向量相似度检索。

---

## Why Structured Storage Is Needed

地震事件数据是结构化时空事件数据。

它包含明确字段：

- 数值字段：magnitude, depth；
- 时间字段：time；
- 空间字段：latitude, longitude；
- 文本字段：place；
- 类型字段：event_type。

因此，事件查询需要精确过滤和统计。

向量数据库可以用于文档语义检索，但不应该替代结构化事件查询。

---

## Data Quality Considerations

地震事件数据可能存在：

- 缺失震级；
- 缺失深度；
- 地点描述不统一；
- 事件类型混杂；
- 数据更新时间变化；
- 时间范围不完整。

SeismoSearch 当前版本以本地样例库为基础，优先保证评估可复现，而不是覆盖所有实时事件。

---

## Evidence Usage

事件数据进入 Evidence Pack 后，应作为 event_evidence 使用。

事件证据应包括：

- event_id；
- time；
- place；
- magnitude；
- depth_km；
- source or catalog note。

Generator 只能基于 event_evidence 描述已查询到的历史事件，不应基于历史事件推断未来地震。

---

## Safety Limitation

历史地震事件数据不能用于预测未来具体地震。

系统不应回答：

```text
明天某地会不会地震？
最近小震很多是不是大震要来了？
动物异常是不是地震前兆？
```

对于这类问题，系统应优先进入 safety routing。

---

## Difference from Document Retrieval

USGS event data 和地震学概念文档是两类不同的数据。

USGS event data 是结构化事件数据，适合回答：

```text
最近 M6.5 以上地震有哪些？
2025 年最大地震是哪一次？
M6 以上事件平均深度是多少？
```

地震学概念文档是非结构化文本，适合回答：

```text
震级和烈度有什么区别？
地震深度是什么意思？
seismic hazard 和 earthquake prediction 有什么区别？
```

因此，SeismoSearch 将两类数据分开处理：

- structured event query 走 DuckDB / EventStore；
- document QA 走 keyword / BM25 / dense retrieval；
- mixed query 同时使用结构化事件证据和文档证据；
- safety query 优先进入 safety_check_tool。

---

## Relation to Evaluation

USGS event metadata 文档可以支持以下 retrieval evaluation 场景：

- 用户询问数据来源；
- 用户询问样例库限制；
- 用户询问为什么查询结果不代表完整全球统计；
- 用户询问 raw / processed / database 分层；
- 用户询问为什么事件查询不用向量数据库；
- 用户询问 event evidence 的来源和限制。

这些问题不应该由地震概念文档回答，而应由 metadata 文档提供证据。

---

## Limitations

当前 SeismoSearch 使用本地样例库，不是实时完整地震监测系统。

因此，系统回答必须避免以下错误表达：

```text
这是全球完整统计。
这是实时官方结论。
这些历史事件说明未来会发生地震。
这个样例库可以替代官方地震目录。
```

更准确的表达是：

```text
以下结果来自当前本地样例库。
查询结果仅反映样例库中的事件。
如需完整实时信息，应参考官方地震机构。
历史事件查询不能用于未来具体地震预测。
```