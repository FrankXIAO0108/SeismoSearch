# Seismic Hazard vs Earthquake Prediction

## 文档目的

本文档解释 seismic hazard、seismic risk、earthquake forecast 和 earthquake prediction 的区别。

这些概念容易被混淆。SeismoSearch 应避免把长期概率性风险评估误表述为未来具体地震预测。

本文档用于支持风险解释、预测拒答和 safety query 的证据生成。

---

## Seismic Hazard

Seismic hazard 通常指某一区域在较长时间尺度上可能遭受地震动影响的可能性。

它通常基于：

- 历史地震活动；
- 活动断层；
- 板块构造；
- 地震动模型；
- 区域地质条件；
- 长期概率统计。

Seismic hazard 是长期、概率性、区域性的概念。

它不是对某一天、某一小时、某一个具体地点是否发生地震的确定预测。

例如：

```text
某区域具有较高地震危险性。
```

这类表达一般是在较长时间尺度和区域尺度上讨论地震动可能性。

它不等于：

```text
明天这个地方一定会地震。
```

---

## Seismic Risk

Seismic risk 通常不仅考虑地震危险性，还考虑暴露度和脆弱性。

它可能涉及：

- 人口密度；
- 建筑物抗震能力；
- 基础设施脆弱性；
- 应急能力；
- 社会经济损失；
- 地区防灾能力。

因此，seismic risk 不只取决于地震本身，也取决于人类社会系统的暴露和脆弱程度。

两个地区即使 seismic hazard 相近，也可能因为建筑质量、人口密度和应急能力不同，导致 seismic risk 不同。

---

## Earthquake Forecast

Earthquake forecast 通常指概率性预测或趋势性判断。

它可能表达为：

```text
某区域在未来较长时间尺度内发生某类地震的概率较高。
```

Forecast 通常具有：

- 时间窗口较宽；
- 空间范围较大；
- 概率表达；
- 不确定性说明；
- 科学模型假设；
- 统计意义而非确定结论。

Forecast 不等于确定性预测。

在系统回答中，应避免把 forecast 解释成“某日某地一定会发生地震”。

---

## Earthquake Prediction

Earthquake prediction 通常指预测具体时间、地点和震级的地震事件。

例如：

```text
明天东京会发生 M7 地震。
下周某地会发生大地震。
三天内会有强震。
今晚某地会不会地震？
```

这类问题要求系统给出未来具体地震判断。

当前科学条件下，可靠预测未来具体地震仍不可行。

SeismoSearch 不应提供这类预测。

---

## Common Confusion

用户常常会把以下问题混淆：

```text
这个地区地震危险性高吗？
```

和：

```text
这个地区明天会不会地震？
```

前者可能属于长期 seismic hazard 解释。

后者属于未来具体地震预测，系统应拒绝。

SeismoSearch 可以解释长期危险性、风险因素和历史事件背景，但不能回答未来某个具体时间是否会发生地震。

---

## Historical Earthquakes Do Not Directly Predict Future Earthquakes

历史地震目录可以用于了解过去活动情况，也可以作为长期风险研究的参考数据之一。

但它不能直接推出：

```text
最近小震很多，所以马上会有大震。
```

也不能直接推出：

```text
过去这里发生过强震，所以下周还会发生强震。
```

历史事件和未来风险之间需要复杂的地震学模型和长期统计分析，不能由简单事件列表直接推断。

SeismoSearch 应避免把历史 catalog query 结果用于未来具体地震预测。

---

## Difference Between Hazard Explanation and Prediction

下面是安全回答与不安全回答的区别。

### 安全回答

```text
该地区历史上有地震活动，长期地震危险性需要结合断层、板块构造和官方危险性评估来判断。
但不能根据最近几次地震直接预测明天是否会发生大震。
```

### 不安全回答

```text
最近这里地震变多，所以明天发生大震的概率很高。
```

前者是在解释长期风险背景。

后者是在暗示未来具体地震预测，应避免。

---

## Relation to Catalog Query

Catalog query 可以回答历史事件问题，例如：

```text
最近 M6.5 以上地震有哪些？
2025 年最大地震是哪一次？
```

这些问题是历史事实查询。

但如果用户继续追问：

```text
所以接下来是不是更危险？
是不是快要大震了？
```

系统应进入 safety routing，而不是继续调用 event_search 暗示未来风险。

---

## Safe Explanation

当用户询问风险或预测时，SeismoSearch 应区分：

- 可以解释长期 seismic hazard；
- 可以解释历史地震活动；
- 可以说明地震预测的科学限制；
- 不能给出未来具体地震判断；
- 不能用伪科学前兆进行预测；
- 不能制造确定性恐慌。

---

## Example Safe Answer

用户问：

```text
最近某地地震很多，是不是更危险？
```

安全回答应表达：

```text
不能仅根据最近地震次数直接判断未来是否会发生更大地震。
短期地震活动不能作为可靠的具体地震预测依据。
如果需要了解长期地震危险性，应参考官方机构发布的地震危险性评估和应急信息。
```

---

## Example Unsafe Answer

以下回答不应出现：

```text
最近地震很多，说明大震可能快来了。
这个地区下周发生强震的概率很高。
根据历史地震，最近几天需要特别警惕大地震。
```

这些回答的问题在于：

- 将历史事件直接推断为未来地震；
- 暗示具体时间窗口；
- 制造恐慌；
- 缺乏科学依据；
- 超出了 SeismoSearch 的系统边界。

---

## Relation to SeismoSearch

SeismoSearch 中：

- catalog query 用于查询历史地震；
- concept query 用于解释地震学概念；
- safety query 用于处理预测诱导；
- mixed query 可以同时提供历史事件和概念解释。

但任何 query 都不应输出未来具体地震预测。

---

## Relation to Evidence Pack

当用户询问 hazard、risk、forecast 或 prediction 的区别时，本文档可以进入 doc_evidence。

当用户询问未来具体地震预测时，系统应优先进入 safety_evidence，而不是调用事件查询工具。

Evidence Pack 应明确区分：

- event_evidence：历史地震事件；
- doc_evidence：概念解释；
- safety_evidence：拒答和边界说明。

---

## Relation to Evaluation

本文档可以支持以下 retrieval evaluation 场景：

- seismic hazard 和 earthquake prediction 有什么区别；
- seismic risk 是不是地震预测；
- forecast 和 prediction 有什么区别；
- 为什么历史地震不能直接预测未来；
- 为什么最近小震很多不能说明大震要来了；
- 为什么系统不能回答明天是否地震。

这些问题应优先命中本文档或 safety boundary 文档。