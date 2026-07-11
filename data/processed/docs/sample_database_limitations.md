# SeismoSearch Sample Database Limitations

## Local Sample Database

SeismoSearch 当前使用本地固定地震事件数据快照。

当前查询结果只代表：

```text
当前本地样例数据库中的事件
```

不代表：

```text
完整全球地震目录
```

也不代表：

```text
实时最新地震数据
```

---

## Fixed Snapshot

固定数据快照意味着：

- 数据内容在实验期间保持不变；
- 相同查询可以重复执行；
- baseline 之间可以公平比较；
- badcase 可以稳定复现；
- 回归测试不会因为实时数据变化而随机失败。

---

## Live Catalog

实时官方地震目录会持续变化。

变化可能来自：

- 新事件加入；
- 已有事件修订；
- 震级更新；
- 深度更新；
- 位置更新；
- 事件状态更新；
- 数据源重新处理。

因此，相同查询在不同时间执行，结果可能不同。

---

## Evaluation Data Source

SeismoSearch 的离线评测应使用固定数据快照。

评测时需要固定：

```text
event data snapshot
database version
corpus version
evaluation set version
retriever configuration
```

不能在 baseline A 和 baseline B 之间更换数据源。

---

## Query Result Boundary

当系统查询本地样例数据库时，回答应明确：

```text
以下结果来自当前本地样例数据库。
```

或者：

```text
以下统计仅适用于当前数据快照。
```

不能表达为：

```text
这是全球全部地震。
```

```text
这是当前实时官方统计。
```

---

## Missing Events

如果用户查询的事件不在本地样例库中，不能直接得出：

```text
该事件不存在。
```

更准确的表达是：

```text
当前本地样例数据库中未检索到该事件。
```

可能原因包括：

- 数据快照时间范围不覆盖；
- 样例数据规模有限；
- 查询条件过于严格；
- 事件没有进入当前本地数据集。

---

## Empty Query Results

查询结果为空时，应区分：

```text
当前数据集中没有匹配结果
```

和：

```text
现实世界中不存在该事件
```

这两个结论不同。

---

## Historical Statistics

基于本地样例库计算的：

```text
event count
average magnitude
maximum magnitude
average depth
```

只对当前数据快照有效。

不能直接推广为：

```text
全球长期统计规律
```

或者：

```text
未来地震趋势
```

---

## Prediction Boundary

历史样例数据库不能用于预测未来具体地震。

以下推断不成立：

```text
最近样例库中小震很多
-> 即将发生大地震
```

```text
历史上某地区发生过大地震
-> 下周一定再次发生
```

历史事件数据只能描述已记录事件。

---

## Snapshot and Production Data

项目可以同时保留两种模式：

```text
evaluation mode
live query mode
```

### Evaluation Mode

使用：

```text
固定本地数据快照
```

用于：

- baseline 对比；
- 单元测试；
- 回归测试；
- badcase 复现。

### Live Query Mode

使用：

```text
官方实时数据源
```

用于：

- 查询最新公开事件；
- 获取当前目录数据。

两种模式的结果不能直接混合比较。

---

## Example Queries

```text
为什么样例数据库查不到今天刚发生的地震？
```

```text
查询结果为空是不是表示现实中没有发生过这类地震？
```

```text
为什么评测需要固定数据快照？
```

```text
本地样例库的统计能代表全球完整地震目录吗？
```

```text
为什么实时目录不适合直接做稳定的回归测试？
```

```text
同一个查询为什么过几天可能得到不同结果？
```

---

## Sources

- U.S. Geological Survey, Earthquake Catalog:
  https://earthquake.usgs.gov/fdsnws/event/1/

- SeismoSearch local event data snapshot and DuckDB event store.