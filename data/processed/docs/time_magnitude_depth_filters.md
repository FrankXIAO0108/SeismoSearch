# Time, Magnitude, and Depth Filters

## Time Range Filtering

地震事件查询通常需要指定时间范围。

常用参数：

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

适合回答：

```text
过去 30 天发生了哪些地震？
```

```text
2026 年 6 月有哪些 M5 以上地震？
```

时间范围应通过结构化字段过滤。

---

## Open and Closed Time Boundaries

时间区间需要明确边界。

常见逻辑：

```text
event_time >= start_time
AND event_time <= end_time
```

或者：

```text
event_time >= start_time
AND event_time < end_time
```

项目中必须保持统一，避免：

- 重复计数；
- 边界事件遗漏；
- 相邻时间窗口重叠。

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

不能直接把“最近”作为文本传给数据库。

---

## Magnitude Filtering

常见震级参数：

```text
min_magnitude
max_magnitude
```

示例：

```json
{
  "min_magnitude": 5.0,
  "max_magnitude": 6.5
}
```

适合回答：

```text
查询 M5 到 M6.5 的地震
```

```text
查询 M6 以上地震
```

震级条件必须使用数值比较。

---

## Depth Filtering

常见深度参数：

```text
min_depth_km
max_depth_km
```

示例：

```json
{
  "max_depth_km": 70.0
}
```

适合回答：

```text
查询深度不超过 70 km 的地震
```

```text
查询浅源地震
```

如果用户使用：

```text
浅源
深源
```

这类自然语言表达，需要先映射到明确阈值。

---

## Combining Filters

时间、震级和深度通常需要组合。

示例：

```json
{
  "start_time": "2026-06-01T00:00:00",
  "end_time": "2026-07-01T00:00:00",
  "min_magnitude": 5.0,
  "max_depth_km": 70.0
}
```

对应：

```text
查询 2026 年 6 月期间，
震级不低于 5.0，
深度不超过 70 km 的地震。
```

数据库过滤条件：

```text
event_time >= start_time
AND event_time <= end_time
AND magnitude >= min_magnitude
AND depth_km <= max_depth_km
```

---

## Sorting

查询结果可以按不同字段排序。

常见：

```text
event_time
magnitude
depth_km
```

示例：

```json
{
  "order_by": "magnitude",
  "descending": true
}
```

表示：

```text
按震级从高到低排序
```

---

## Limit

`limit` 用于限制返回数量。

示例：

```json
{
  "limit": 10
}
```

适合回答：

```text
最近 10 次地震
```

```text
震级最高的 5 次地震
```

limit 不应该替代过滤条件。

---

## Null Values

结构化字段可能为空。

例如：

```text
magnitude = null
depth_km = null
```

处理时需要明确：

- 是否排除空值；
- 是否允许参与排序；
- 是否允许参与平均值；
- 是否在结果中显示未知。

不能把：

```text
null
```

自动转换为：

```text
0
```

---

## Exact Filtering vs Semantic Retrieval

以下问题应该使用结构化查询：

```text
M6.5 以上
```

```text
深度小于 70 km
```

```text
过去 30 天
```

```text
震级最高的 10 次
```

这些条件需要：

```text
数值比较
时间比较
排序
限制数量
```

向量检索不能保证精确满足这些约束。

---

## Example Queries

```text
过去 30 天应该如何转换成结构化时间条件？
```

```text
M5 到 M6.5 应该如何过滤？
```

```text
深度不超过 70 km 应该用什么参数？
```

```text
为什么 limit 不能替代筛选条件？
```

```text
magnitude 为 null 时应该怎么处理？
```

```text
为什么过去 30 天 M5+ 浅源地震不能直接用向量检索？
```

---

## Sources

- U.S. Geological Survey, API Documentation - Earthquake Catalog:
  https://earthquake.usgs.gov/fdsnws/event/1/