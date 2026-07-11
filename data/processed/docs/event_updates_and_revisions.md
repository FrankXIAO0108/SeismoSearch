# Earthquake Event Updates and Revisions

## Event Time and Update Time

地震事件记录通常同时包含：

```text
time
updated
```

`time` 表示地震事件发生时间。

`updated` 表示事件记录最近一次更新时间。

这两个字段不能混淆。

---

## Preliminary and Reviewed Data

地震事件在刚发生后，可能首先由自动系统快速处理。

后续可能经过：

- 新增台站数据；
- 波形重新处理；
- 人工复核；
- 数据源合并；
- 首选震级或位置结果更新。

因此，同一个事件的记录可能发生变化。

---

## Status

常见状态包括：

```text
automatic
reviewed
```

`automatic` 表示事件主要由自动系统处理。

`reviewed` 表示事件已经经过进一步审核。

但是：

```text
reviewed
```

不等于：

```text
永远不会再变化
```

后续仍可能更新。

---

## Fields That May Change

事件更新后，以下字段可能发生变化：

```text
magnitude
magType
depth
latitude
longitude
place
status
updated
```

部分事件产品也可能更新。

---

## Event ID Stability

同一个地震事件通常通过：

```text
event_id
```

进行追踪。

在更新前后，应优先使用 event_id 判断是否为同一事件，而不是只比较：

```text
place
magnitude
time
```

因为这些字段可能发生调整。

---

## Why Query Results May Change

即使用户使用相同查询条件，在不同时间运行查询，也可能得到不同结果。

原因包括：

- 新事件被加入目录；
- 旧事件被修订；
- 震级发生调整；
- 事件类型发生调整；
- 事件记录被合并或删除；
- 查询的数据时间范围继续增长。

因此，实时目录查询不一定完全可复现。

---

## Reproducible Evaluation

为了保证 SeismoSearch 评测可复现，应固定：

```text
data snapshot
database version
corpus version
evaluation set version
```

本地样例数据库用于固定实验输入。

评测结果只对应当前数据快照。

---

## Snapshot and Live Data

需要区分：

```text
fixed local snapshot
live official catalog
```

固定本地快照适合：

- 单元测试；
- 回归测试；
- baseline 对比；
- badcase 复现。

实时官方目录适合：

- 获取最新事件；
- 查询当前公开数据；
- 展示最新结果。

两者不应混为一谈。

---

## Query Result Wording

对于固定本地样例库，回答应说明：

```text
以下结果来自当前本地样例数据库。
```

对于实时官方目录，应说明：

```text
结果基于查询时的数据状态，后续可能更新。
```

---

## What Reviewed Does Not Mean

`status=reviewed` 不表示：

- 数据绝对无误；
- 所有字段永远不会改变；
- 事件不会被重新处理；
- 可以忽略 uncertainty 字段。

---

## Example Queries

```text
time 和 updated 有什么区别？
```

```text
为什么同一个地震事件的 magnitude 后续可能变化？
```

```text
status=reviewed 后数据还会更新吗？
```

```text
为什么同一个查询过几天可能得到不同结果？
```

```text
为什么评测应该使用固定数据快照？
```

```text
event_id 为什么比 place 更适合追踪同一个事件？
```

---

## Sources

- U.S. Geological Survey, GeoJSON Summary Format:
  https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php

- U.S. Geological Survey, ANSS Comprehensive Earthquake Catalog Documentation:
  https://earthquake.usgs.gov/data/comcat/index.php