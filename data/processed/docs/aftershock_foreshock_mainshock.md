# Aftershock, Foreshock, and Mainshock

## Mainshock

`mainshock` 指一个地震序列中作为主要事件讨论的较大地震。

一个地震序列可能包括：

```text
foreshock
mainshock
aftershock
```

这些名称描述的是事件之间的关系，不是独立的地震类型字段。

---

## Foreshock

`foreshock` 指发生在较大地震之前，并且后来被认为与该较大事件属于同一地震序列的地震。

重要限制：

```text
一个地震刚发生时，
通常不能仅凭它自身确定它一定是 foreshock。
```

只有后续发生更大的相关事件后，较早事件才可能被回溯性地称为 foreshock。

因此：

```text
small earthquake
```

不等于：

```text
foreshock
```

也不能根据一次小地震直接推出：

```text
后面一定会发生更大的地震
```

---

## Aftershock

`aftershock` 指发生在较大地震之后、与主事件相关的后续地震活动。

余震通常发生在主震附近的区域。

余震活动可能持续：

```text
days
weeks
months
or longer
```

具体持续时间和活动水平取决于地震序列本身。

---

## Mainshock Classification Can Change

事件序列的命名可能随着后续事件发生而变化。

例如：

```text
Event A occurs
-> initially treated as the largest event

Event B occurs later
-> Event B is larger and related to the same sequence
```

此时，Event A 可能重新被解释为：

```text
foreshock
```

而 Event B 成为：

```text
mainshock
```

因此，foreshock 和 mainshock 的关系具有回溯性。

---

## A Small Earthquake Is Not Automatically a Foreshock

以下推理不成立：

```text
发生了一次小地震
-> 它一定是前震
-> 很快一定发生大地震
```

原因是：

```text
大多数单独的小地震不能在发生时被确定为未来大地震的前震。
```

只有后续地震序列提供更多信息后，某些事件才可能被重新分类。

---

## Aftershock Does Not Mean Prediction

识别余震序列不等于能够预测未来具体地震。

可以讨论：

```text
aftershock activity
aftershock probability
historical sequence behavior
```

但不能据此确定：

```text
下一次余震的精确时间
下一次余震的精确地点
下一次余震的精确震级
```

---

## Sequence Relationships

三个概念可以表示为：

```text
foreshock
-> occurs before a larger related event

mainshock
-> principal larger event in the sequence

aftershock
-> related seismic activity after the main event
```

但实际地震序列可能比这个简单模型复杂。

---

## Catalog Interpretation

在地震目录中看到多个时间和空间接近的事件时，不能仅根据：

```text
time proximity
location proximity
magnitude similarity
```

就自动认定：

```text
foreshock
mainshock
aftershock
```

正式的地震序列分析可能需要：

- 时间关系；
- 空间关系；
- 震级关系；
- 构造背景；
- 专业目录或官方分析。

---

## Safety Boundary

以下问题属于知识解释：

```text
foreshock 和 aftershock 有什么区别？
```

```text
为什么一个地震后来可能被称为前震？
```

以下推断不能直接支持：

```text
刚发生一个小地震，所以马上一定会发生大地震。
```

对于具体未来地震预测，应进入 SeismoSearch 的安全处理路径。

---

## Sources

- U.S. Geological Survey, Earthquake Glossary - Aftershock:
  https://earthquake.usgs.gov/learn/glossary/?term=aftershock

- U.S. Geological Survey, Earthquake Glossary - Foreshock:
  https://earthquake.usgs.gov/learn/glossary/?term=foreshock

- U.S. Geological Survey, Earthquake Glossary - Mainshock:
  https://earthquake.usgs.gov/learn/glossary/?term=mainshock

- U.S. Geological Survey, Can you predict earthquakes?:
  https://www.usgs.gov/faqs/can-you-predict-earthquakes