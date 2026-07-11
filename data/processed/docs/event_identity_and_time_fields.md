# USGS Event Identity and Time Fields

## Event ID

`event_id` 用于唯一标识一条地震事件记录。

在 SeismoSearch 中，event_id 用于：

- 追踪同一事件；
- 构建事件证据；
- 在 Evidence Pack 中引用具体事件；
- 避免不同事件混淆；
- 支持后续数据更新和记录关联。

event_id 不表示：

- 震级；
- 风险等级；
- 地震类型；
- 事件发生时间。

---

## Event ID and Event Updates

同一个事件的部分字段可能更新，例如：

```text
magnitude
depth
latitude
longitude
place
status
updated
```

因此，追踪同一事件时，应优先使用：

```text
event_id
```

而不是只依赖：

```text
place
magnitude
time
```

---

## Time

`time` 表示地震事件发生时间。

在 SeismoSearch 中可用于：

- 时间范围过滤；
- 最近事件查询；
- 年、月、日范围查询；
- 按时间排序；
- 计算事件之间的时间间隔。

例如：

```text
2026 年 6 月发生的地震
```

需要转换为明确时间范围。

---

## Updated

`updated` 表示事件记录最近一次更新时间。

不要混淆：

```text
time
```

和：

```text
updated
```

### time

表示：

```text
地震什么时候发生
```

### updated

表示：

```text
这条事件记录最近什么时候被修改
```

---

## Time Filtering

常见时间过滤条件：

```text
start_time
end_time
```

示例：

```json
{
  "start_time": "2026-06-01T00:00:00",
  "end_time": "2026-07-01T00:00:00"
}
```

对应：

```text
查询 2026 年 6 月期间发生的事件
```

时间过滤应通过结构化查询执行。

---

## Relative Time Expressions

用户可能使用：

```text
最近
过去 7 天
过去 30 天
本月
今年
最近一个月
```

这些表达需要转换为明确时间范围。

例如：

```text
过去 30 天
```

应转换为：

```text
start_time = 当前时间 - 30 天
end_time = 当前时间
```

---

## Event Type

`event_type` 表示事件类型。

常见事件类型可能包括：

```text
earthquake
quarry blast
explosion
other event types
```

查询普通地震事件时，可以使用：

```text
event_type = earthquake
```

避免将其他事件类型混入统计结果。

---

## Event Type Filtering

以下问题属于结构化查询：

```text
只查询 earthquake 类型事件
```

```text
排除 explosion
```

```text
统计某个时间范围内的 earthquake 数量
```

应通过数据库字段过滤执行。

---

## Place

`place` 是人类可读的位置描述。

它可以帮助用户理解事件大致位置，但不应作为事件唯一标识。

原因：

- place 可能更新；
- place 可能使用不同描述方式；
- 不同事件可能出现相似 place；
- place 不是严格行政区划。

追踪事件时，应优先使用：

```text
event_id
```

---

## Event Identity vs Location

以下字段作用不同：

```text
event_id
place
latitude
longitude
```

### event_id

标识具体事件。

### place

提供人类可读的位置描述。

### latitude / longitude

提供结构化空间坐标。

不能使用：

```text
place
```

替代：

```text
event_id
```

也不能使用：

```text
event_id
```

替代空间查询。

---

## Missing or Changed Fields

事件记录更新后：

```text
place
magnitude
depth
status
```

可能变化。

但系统仍应通过 event_id 追踪同一事件。

如果 event_id 不同，不应仅因为：

```text
时间接近
位置接近
震级接近
```

就直接认定为同一事件。

---

## Example Queries

```text
event_id 有什么作用？
```

```text
time 和 updated 有什么区别？
```

```text
为什么不能用 place 作为事件唯一标识？
```

```text
如何查询过去 30 天的 earthquake 类型事件？
```

```text
同一个事件 magnitude 更新后怎么继续追踪？
```

```text
event_type 为什么需要结构化过滤？
```

---

## Sources

- U.S. Geological Survey, GeoJSON Summary Format:
  https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php

- U.S. Geological Survey, ANSS Comprehensive Earthquake Catalog Documentation:
  https://earthquake.usgs.gov/data/comcat/index.php