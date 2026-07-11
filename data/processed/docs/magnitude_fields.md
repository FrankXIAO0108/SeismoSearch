# USGS Magnitude Fields

## Magnitude

`magnitude` 表示地震事件的震级。

在 USGS 数据中常见字段名：

```text
mag
```

在 SeismoSearch 标准化数据中保存为：

```text
magnitude
```

magnitude 是数值字段，可用于：

- 最小震级过滤；
- 最大震级过滤；
- 按震级排序；
- 统计平均震级；
- 查询最大或最小震级事件；
- 与时间、深度和空间条件组合查询。

例如：

```text
magnitude >= 6.5
```

应该通过 DuckDB 或 EventStore 执行精确数值过滤。

---

## Magnitude Type

`magType` 表示震级类型。

常见类型可能包括：

```text
Mw
Mww
Mwc
Mb
ML
Md
```

不同震级类型：

- 使用的观测数据可能不同；
- 计算方法可能不同；
- 适用震级范围可能不同；
- 不应仅根据字段名称认为所有 magnitude 完全使用同一种计算方法。

因此，在比较不同事件的震级时，可以同时保留：

```text
magnitude
magType
```

---

## Magnitude Is Not Intensity

magnitude 和 intensity 不是同一个概念。

```text
magnitude
```

描述地震事件本身的规模。

```text
intensity
```

描述某个地点实际感受到的震动程度或影响。

一次地震通常有一个主要震级值，但不同地点的烈度可以不同。

因此：

```text
M7.0
```

不能直接推出所有地区都会经历相同的震动或破坏。

---

## Magnitude Error

`magError` 表示震级估计的不确定性信息。

它可以用于辅助判断：

- 震级估计是否稳定；
- 两个非常接近的震级值是否值得过度比较；
- 数据是否可能在后续处理中发生调整。

例如：

```text
M5.9
```

和：

```text
M6.0
```

之间的差异不应该脱离测量和计算不确定性进行过度解释。

`magError` 不是：

- 地震发生概率；
- 地震预测误差；
- 破坏程度误差；
- 风险等级。

---

## Magnitude Station Count

部分 USGS 详细事件数据可能包含：

```text
magNst
```

它表示参与震级计算的台站数量。

一般来说，该字段可以作为理解震级计算信息量的辅助指标。

但不能简单使用：

```text
magNst 越大
```

就推出：

```text
震级一定绝对准确
```

数据质量还需要结合其他字段和处理状态判断。

---

## nst and magNst Are Different

以下两个字段不要混淆：

```text
nst
magNst
```

`nst` 通常与事件定位所使用的地震台站数量有关。

`magNst` 与震级计算所使用的台站数量有关。

因此：

```text
nst
```

不能直接等同于：

```text
magNst
```

---

## Structured Magnitude Filtering

以下问题属于结构化查询：

```text
查询 M6.5 以上地震
```

```text
找出震级最大的 10 次事件
```

```text
统计 M5 到 M6 之间有多少次地震
```

```text
查询过去 30 天 M5 以上浅源地震
```

这些问题需要执行：

```text
数值比较
排序
统计
多条件过滤
```

不应该使用 embedding similarity 代替。

例如：

```text
magnitude >= 6.5
```

和：

```text
与“6.5级地震”语义相似
```

不是同一个查询条件。

---

## Missing Magnitude

部分事件可能没有可用震级。

处理时应注意：

```text
magnitude = null
```

不能自动解释为：

```text
magnitude = 0
```

没有震级值的事件：

- 不应参与普通震级平均值计算；
- 不应被错误归类为零级地震；
- 在排序和统计时需要明确处理空值。

---

## Magnitude Can Be Updated

地震事件数据可能在后续处理中更新。

震级可能因为：

- 新增观测数据；
- 重新处理波形；
- 更换首选震级类型；
- 人工复核；
- 数据源更新；

而发生调整。

因此，事件的：

```text
magnitude
magType
updated
status
```

可以结合查看。

早期发布的震级值不一定是最终结果。

---

## What Magnitude Does Not Mean

magnitude 不直接表示：

- 某个地点的实际烈度；
- 建筑物损失；
- 人员伤亡；
- 海啸一定发生；
- 未来余震一定多强；
- 未来是否会发生更大地震。

同样震级的两个事件，实际影响可能因为以下因素不同：

```text
depth
distance
ground motion
local geology
building vulnerability
population exposure
```

---

## Example Queries

```text
magnitude >= 6.5 为什么必须使用结构化查询？
```

```text
mag 和 magType 有什么区别？
```

```text
magError 表示什么？
```

```text
nst 和 magNst 是同一个字段吗？
```

```text
没有 magnitude 的事件是不是等于零级地震？
```

```text
为什么 USGS 事件的 magnitude 后续可能发生变化？
```

```text
相同震级的地震为什么影响可能不同？
```

---

## Sources

- U.S. Geological Survey, GeoJSON Summary Format:
  https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php

- U.S. Geological Survey, ANSS Comprehensive Earthquake Catalog Documentation:
  https://earthquake.usgs.gov/data/comcat/index.php