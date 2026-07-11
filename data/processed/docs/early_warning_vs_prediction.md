# Earthquake Early Warning vs Prediction

## Earthquake Prediction

地震预测通常指提前给出未来地震的：

```text
时间
地点
震级
```

例如：

```text
下周东京会发生 M7 地震
```

属于具体未来地震预测。

当前科学能力不能可靠预测这种具体事件。

---

## Earthquake Early Warning

Earthquake Early Warning，简称：

```text
EEW
```

地震预警不是在地震发生前预测地震。

它是在：

```text
地震已经开始之后
```

利用监测系统快速检测地震，并尽可能在更强震动到达某些地区之前发送通知。

基本流程：

```text
earthquake starts
-> seismic stations detect initial signals
-> system estimates event information
-> warning is distributed
-> stronger shaking may arrive later
```

---

## Early Warning Is Not Prediction

不要混淆：

```text
earthquake early warning
earthquake prediction
```

### Early Warning

```text
地震已经发生
-> 快速检测
-> 提前通知尚未感受到强震动的地区
```

### Prediction

```text
地震尚未发生
-> 提前预测未来的时间、地点和震级
```

因此：

```text
收到地震预警
```

不表示：

```text
系统提前几天预测出了这次地震
```

---

## Warning Time Is Limited

地震预警提供的时间通常有限。

具体可用时间取决于：

- 用户与震源之间的距离；
- 地震检测速度；
- 数据处理速度；
- 信息传输速度；
- 地震波传播情况。

距离震源非常近的区域可能：

```text
在收到预警前已经开始明显震动
```

因此，预警不能保证所有用户都获得相同提前时间。

---

## Earthquake Forecast

Earthquake forecast 通常使用概率表达。

例如：

```text
未来一段时间内，
某区域发生某类地震的概率是多少
```

forecast 不等于：

```text
确定某一天一定会发生地震
```

它表达的是：

```text
概率
不确定性
时间窗口
空间范围
```

---

## Earthquake Probability

Earthquake probability 描述：

```text
在某个时间范围和区域内，
发生某类地震的可能性
```

例如长期 hazard assessment 中可能使用：

```text
未来若干年内的发生概率
```

概率表达不等于确定性预测。

---

## Prediction Requires Specific Claims

具体地震预测通常需要同时说明：

```text
when
where
how large
```

也就是：

```text
时间
地点
震级
```

如果一个说法非常模糊，例如：

```text
未来某个地方会发生地震
```

不能因为之后世界上发生了某次地震，就认为预测成功。

---

## Historical Activity Does Not Become Prediction

以下信息可以用于描述历史活动：

```text
最近地震数量增加
某地区历史上发生过大地震
某段时间出现地震群
```

但不能直接推出：

```text
下周一定发生大地震
```

或者：

```text
某个具体地点马上发生地震
```

---

## SeismoSearch Routing

以下问题属于安全边界：

```text
明天东京会不会发生大地震？
```

```text
下周这里会发生 M7 地震吗？
```

```text
能不能告诉我下一次大地震的具体日期？
```

应进入：

```text
safety_check
```

以下问题属于知识解释：

```text
地震预警和地震预测有什么区别？
```

```text
earthquake forecast 和 prediction 有什么区别？
```

可以进入：

```text
document retrieval
```

---

## Safe Answer Pattern

对于具体未来地震预测问题，应回答：

```text
当前无法可靠预测未来具体地震的时间、地点和震级。
```

可以继续提供：

- 历史事件查询；
- 已公开地震数据；
- earthquake forecast 的概念解释；
- seismic hazard 信息；
- earthquake early warning 的工作方式。

---

## Example Queries

```text
地震预警是不是提前预测地震？
```

```text
early warning 和 earthquake prediction 有什么区别？
```

```text
为什么收到预警时地震其实已经发生了？
```

```text
forecast 和 prediction 是一回事吗？
```

```text
概率预测能不能告诉我下周哪一天会地震？
```

```text
为什么历史活动增加不能直接预测下一次大地震？
```

---

## Sources

- U.S. Geological Survey, Can you predict earthquakes?
  https://www.usgs.gov/faqs/can-you-predict-earthquakes

- U.S. Geological Survey, Earthquake Hazards Program:
  https://www.usgs.gov/programs/earthquake-hazards