# Earthquake Safety Boundaries

## 文档目的

本文档定义 SeismoSearch 在地震信息问答中的安全边界。

SeismoSearch 可以回答历史地震事件查询、地震学概念解释和公开事件统计，但不能预测未来具体地震，也不能强化伪科学预测说法。

本文档用于支持 safety query 的文档证据和系统边界说明。

---

## Supported Questions

SeismoSearch 可以回答：

```text
最近 M6.5 以上地震有哪些？
2025 年震级最高的地震是哪一次？
震级和烈度有什么区别？
地震深度是什么意思？
tsunami alert 是什么意思？
```

这些问题属于：

- 历史事件查询；
- 地震学概念解释；
- 结构化统计；
- 官方信息解释；
- 一般性风险沟通。

这些问题可以通过结构化事件库、文档检索或两者结合来回答。

---

## Unsupported Questions

SeismoSearch 不支持回答：

```text
明天东京会不会发生大地震？
下周某地会不会地震？
最近小震很多是不是说明大震要来了？
动物异常是不是地震前兆？
地震云是不是地震前兆？
能不能根据历史地震预测下周风险？
```

这些问题涉及：

- 未来具体地震预测；
- 伪科学预兆；
- 根据短期历史活动推断未来大震；
- 将历史事件误用为预测依据；
- 可能造成用户恐慌或误导。

对于这些问题，系统应优先进入 safety routing。

---

## Future Specific Earthquake Prediction

未来具体地震预测指试图判断某地在某个具体未来时间是否会发生地震。

例如：

```text
明天东京会不会地震？
下周日本会不会发生大地震？
三天内会不会有 M7 地震？
```

这类问题通常包含：

- 明确未来时间；
- 明确地点；
- 明确或隐含震级；
- 要求系统给出确定性判断。

SeismoSearch 不应回答这类问题。

正确做法是：

- 明确说明不能预测未来具体地震；
- 避免调用 event_search 生成误导；
- 建议关注官方地震机构信息；
- 可提供一般性防灾准备建议。

---

## Pseudoscience Prediction Claims

伪科学预测说法包括：

- 动物异常；
- 地震云；
- 天气异常；
- 鱼群异常；
- 狗叫；
- 其他未经科学验证的所谓前兆。

例如：

```text
我家狗一直叫是不是地震前兆？
鱼群异常是不是要地震了？
天上有地震云是不是说明快地震？
```

SeismoSearch 应说明：

- 这些现象不能作为可靠地震预测依据；
- 不能据此判断未来地震；
- 不应制造确定性恐慌；
- 应参考官方监测和预警信息。

系统不应把伪科学现象和历史地震事件强行关联。

---

## Historical Activity Prediction Claims

历史活动预测诱导指用户试图根据最近地震活动推断未来大震风险。

例如：

```text
最近小震很多是不是说明大震要来了？
最近某地地震很多，是不是更危险？
能不能根据历史地震预测下周风险？
```

这些问题看似在问历史事件，但真实意图是推断未来风险。

SeismoSearch 应避免用历史事件查询结果暗示未来风险。

正确做法是：

- 说明短期小震频繁不能直接用于预测未来大震；
- 不调用 event_search 生成误导性事件列表；
- 给出风险沟通边界；
- 引导关注官方机构。

---

## Safety Routing Rule

当 query 涉及未来预测、伪科学前兆或历史活动预测诱导时，Planner 应优先输出：

```text
query_type = safety
```

并且不应生成：

```text
event_search_params
event_statistics_params
doc_retrieval_queries
```

对于 safety query，系统应只调用 safety_check_tool。

这条规则的目的不是减少回答内容，而是避免系统错误地把历史事件数据用于未来预测。

---

## Why Event Search Should Be Avoided

对于预测诱导问题，调用 event_search 可能造成误导。

例如用户问：

```text
最近小震很多是不是大震要来了？
```

如果系统返回最近地震列表，用户可能误以为这些事件能够作为未来大震预测依据。

因此，safety query 应避免调用事件查询工具。

正确行为是：

```text
safety_check_tool
-> safety evidence
-> safe refusal / safe explanation
```

而不是：

```text
event_search_tool
-> recent earthquakes
-> implied future risk
```

---

## Safe Response Style

安全回答应包括：

1. 明确不能预测未来具体地震；
2. 否定伪科学或不可靠推断；
3. 避免恐慌性表述；
4. 建议关注官方机构；
5. 可提供一般防灾准备建议；
6. 不给出确定性风险判断。

例如，用户问：

```text
最近小震很多是不是大震要来了？
```

更安全的回答是：

```text
不能仅根据最近小震频繁判断未来是否会发生大震。
短期地震活动不能作为可靠的具体地震预测依据。
如需了解当地地震风险和官方预警信息，应关注官方地震机构和应急管理部门。
```

---

## Unsafe Response Examples

以下回答是不安全的：

```text
最近小震很多，所以大震概率明显升高。
狗一直叫可能说明附近快地震了。
根据历史地震活动，下周风险很高。
三天内可能会发生强震。
```

这些回答的问题在于：

- 暗示未来具体地震；
- 把非科学现象当作预测依据；
- 夸大历史事件和未来风险之间的关系；
- 可能引发用户恐慌。

---

## Not a Replacement for Official Sources

SeismoSearch 不替代：

- 官方地震监测机构；
- 官方地震预警；
- 应急管理部门；
- 专业地震风险评估。

系统回答应保持解释性和辅助性，而不是权威预警。

当用户询问灾害风险或应急行动时，系统应建议用户参考官方发布的信息。

---

## Relation to SeismoSearch

在 SeismoSearch 中：

- catalog query 可以调用 event_search_tool；
- concept query 可以调用 doc_retriever；
- mixed query 可以同时调用事件工具和文档工具；
- safety query 应优先调用 safety_check_tool。

Safety routing 是系统边界控制的一部分。

它的目标是防止模型或工具链把历史事件、伪科学前兆和未来风险错误关联起来。

---

## Relation to Evaluation

本文档可以支持以下 retrieval evaluation 场景：

- 用户询问为什么不能预测地震；
- 用户询问动物异常是否可靠；
- 用户询问地震云是否可信；
- 用户询问小震频繁是否说明大震；
- 用户询问为什么 safety query 不能调用事件查询；
- 用户询问 SeismoSearch 和官方预警的关系。

这些问题应命中 safety boundary 文档，而不是只命中普通地震概念文档。