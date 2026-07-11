# USGS Impact and Review Fields

## felt

`felt` 表示与该事件相关的公众震感报告数量。

这些报告通常来自公众提交的震感信息。

`felt` 可以用于：

- 了解有多少公众提交了震感报告；
- 辅助判断事件是否被大量公众感知；
- 与其他影响字段一起解释事件影响。

`felt` 不表示：

- 实际感受到地震的总人数；
- 受灾人数；
- 人员伤亡；
- 地震烈度；
- 地震危险性等级。

---

## cdi

`cdi` 表示基于公众报告得到的社区互联网烈度信息。

它来自公众震感反馈。

`cdi` 可以用于：

- 了解公众报告的震动强度；
- 与仪器估计结果进行对比；
- 辅助解释事件的实际感知情况。

`cdi` 不是震级。

---

## mmi

`mmi` 表示事件相关的估计仪器烈度信息。

它与：

```text
magnitude
```

不是同一个概念。

magnitude 描述地震事件规模。

mmi 描述地震产生的震动强度或影响程度。

不同地点的实际震动可能不同。

---

## cdi and mmi

不要混淆：

```text
cdi
mmi
```

`cdi` 更侧重公众报告。

`mmi` 更侧重仪器和模型估计。

两者可能不同。

例如：

```text
公众报告数量有限
```

可能导致 cdi 信息不足。

而仪器估计仍可能存在。

---

## alert

`alert` 表示事件相关的影响提示等级。

可能出现：

```text
green
yellow
orange
red
```

alert 可以用于快速理解事件潜在影响等级。

但 alert 不表示：

- 地震震级；
- 地震烈度；
- 海啸警报；
- 未来地震预测；
- 用户必须采取某个具体行动。

具体应急行动应参考官方机构发布的信息。

---

## tsunami

`tsunami` 是事件记录中的 tsunami flag。

常见值：

```text
0
1
```

该字段用于标记事件是否触发了相关海啸关注条件。

重要：

```text
tsunami = 1
```

不等于：

```text
已经发布正式海啸警报
```

也不等于：

```text
一定已经发生海啸
```

正式海啸警报应以负责海啸预警的官方机构信息为准。

---

## sig

`sig` 表示事件的综合显著性分数。

通常：

```text
sig 越高
```

表示该事件在目录中具有更高的综合显著性。

sig 可能综合考虑多个因素。

它不应该被简单解释为：

```text
风险概率
```

或者：

```text
未来大地震概率
```

sig 也不是单纯的震级字段。

---

## Magnitude and Impact Fields

以下字段不要混淆：

```text
magnitude
felt
cdi
mmi
alert
tsunami
sig
```

### magnitude

描述事件规模。

### felt

描述公众震感报告数量。

### cdi

描述公众报告的震感强度信息。

### mmi

描述估计的仪器烈度信息。

### alert

描述事件影响提示等级。

### tsunami

事件记录中的 tsunami flag。

### sig

事件综合显著性分数。

---

## Missing Values

部分事件可能没有：

```text
felt
cdi
mmi
alert
```

这不一定表示：

```text
事件没有影响
```

可能表示：

- 没有足够公众报告；
- 没有对应产品；
- 数据尚未生成；
- 当前事件不满足产品生成条件。

因此：

```text
null
```

不能直接解释为：

```text
0
```

---

## Structured Filtering

以下条件属于结构化查询：

```text
tsunami = 1
```

```text
alert = red
```

```text
sig >= 600
```

这些查询应通过数据库过滤。

文档检索负责解释：

- 字段是什么意思；
- 字段之间有什么区别；
- 字段不能推出什么结论。

---

## Example Queries

```text
felt 和 cdi 是同一个指标吗？
```

```text
cdi 和 mmi 有什么区别？
```

```text
alert=red 是不是表示海啸警报？
```

```text
tsunami=1 是不是代表已经发布正式海啸预警？
```

```text
sig 是震级吗？
```

```text
felt=null 是不是表示没人感觉到地震？
```

```text
为什么 tsunami flag 不能直接当成正式海啸警报？
```

---

## Sources

- U.S. Geological Survey, GeoJSON Summary Format:
  https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php

- U.S. Geological Survey, ANSS Comprehensive Earthquake Catalog Event Terms:
  https://earthquake.usgs.gov/data/comcat/data-eventterms.php