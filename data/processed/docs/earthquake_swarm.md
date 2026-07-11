# Earthquake Swarm

## Earthquake Swarm

`earthquake swarm` 指某一局部区域在一段时间内连续发生较多地震的现象。

与典型的：

```text
mainshock
-> aftershock sequence
```

不同，地震群中通常没有一个明显占主导地位的主震。

---

## Swarm vs Mainshock-Aftershock Sequence

### Mainshock-Aftershock Sequence

通常表现为：

```text
一个较大的主震
-> 后续发生一系列较小余震
```

### Earthquake Swarm

通常表现为：

```text
同一区域
-> 一段时间内发生多个地震
-> 没有明显单一主震控制整个序列
```

两者不能仅根据：

```text
地震数量很多
```

进行区分。

---

## Swarm Duration

地震群可能持续：

```text
hours
days
weeks
months
or longer
```

持续时间没有一个适用于所有地震群的固定标准。

因此：

```text
持续三天地震很多
```

不能单独作为地震群的唯一判定条件。

---

## Swarm Magnitudes

地震群中的事件震级可能：

- 较小；
- 相互接近；
- 偶尔包含较大的事件。

不能简单认为：

```text
earthquake swarm
```

就一定意味着：

```text
所有事件震级都很小
```

---

## Possible Causes

地震群可能与不同地质过程有关，例如：

```text
fault activity
volcanic processes
fluid movement
geothermal activity
human-induced processes
```

具体原因需要结合：

- 地质背景；
- 空间分布；
- 时间演化；
- 震源机制；
- 其他地球物理观测。

不能仅根据：

```text
发生了地震群
```

直接判断具体成因。

---

## Swarm Does Not Automatically Mean Volcanic Eruption

以下推理不成立：

```text
发生地震群
-> 一定有火山喷发
```

地震群可能发生在：

- 火山地区；
- 构造活动区；
- 流体活动区域；
- 诱发地震区域；
- 其他地质环境。

因此需要结合区域背景解释。

---

## Swarm Does Not Automatically Predict a Larger Earthquake

以下推理不成立：

```text
最近发生很多小地震
-> 一定正在形成 earthquake swarm
-> 马上一定发生大地震
```

地震活动增加本身不能可靠确定未来具体地震的：

```text
time
location
magnitude
```

---

## Catalog Analysis

在地震目录中分析可能的地震群时，可以观察：

```text
event count
time concentration
spatial concentration
magnitude distribution
depth distribution
```

例如：

```text
某个区域
+ 某个时间窗口
+ 多个空间接近的事件
```

可以作为进一步分析的候选。

但仅靠简单 SQL 查询结果，不应该直接宣布：

```text
这是一个已经确认的 earthquake swarm
```

更准确的表达是：

```text
当前目录中观察到一组时间和空间上集中的地震事件。
```

---

## Swarm and SeismoSearch

SeismoSearch 可以：

- 查询指定区域和时间范围内的事件；
- 统计事件数量；
- 比较震级和深度分布；
- 展示时间和空间集中现象；
- 检索地震群概念说明。

SeismoSearch 不应仅根据简单规则自动宣布：

```text
某地区已经确认发生地震群
```

也不应根据地震群直接预测未来具体大地震。

---

## Safe Interpretation

对于：

```text
最近这个地区地震很多，是不是马上要发生大地震？
```

系统应区分两个问题：

```text
历史活动是否增加
```

和：

```text
能否预测未来具体大地震
```

可以基于目录描述历史活动。

不能将历史活动直接转换为确定性未来预测。

---

## Sources

- U.S. Geological Survey, Earthquake Hazards Program:
  https://www.usgs.gov/programs/earthquake-hazards

- U.S. Geological Survey, Earthquake Glossary:
  https://earthquake.usgs.gov/learn/glossary/