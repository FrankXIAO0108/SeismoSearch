# Geographic Query Methods for Earthquake Events

## Structured Geographic Filtering

地震事件的空间位置由以下字段表示：

```text
latitude
longitude
```

空间查询应使用结构化数值过滤，不使用向量相似度进行精确范围判断。

基本流程：

```text
地点或区域名称
-> 经纬度范围或中心点
-> 结构化查询参数
-> DuckDB / EventStore
```

---

## Bounding Box Query

Bounding box 使用四个边界参数：

```text
min_latitude
max_latitude
min_longitude
max_longitude
```

示例：

```json
{
  "min_latitude": 30.0,
  "max_latitude": 46.0,
  "min_longitude": 128.0,
  "max_longitude": 146.0
}
```

对应过滤条件：

```text
latitude >= min_latitude
AND latitude <= max_latitude
AND longitude >= min_longitude
AND longitude <= max_longitude
```

适合：

- 查询矩形地图区域；
- 查询预定义国家或地区范围；
- 地图视窗范围过滤；
- 与时间、震级和深度条件组合。

---

## Radius Query

Radius query 使用中心点和最大半径。

参数：

```text
latitude
longitude
max_radius_km
```

示例：

```json
{
  "latitude": 35.6762,
  "longitude": 139.6503,
  "max_radius_km": 300
}
```

表示查询距离中心点不超过 300 km 的事件。

适合：

- 查询某城市附近的地震；
- 查询某监测站附近的事件；
- 查询某个震中周围的事件；
- 处理“附近多少公里”的自然语言条件。

---

## Bounding Box and Radius Comparison

### Bounding Box

适合：

- 国家或地区范围；
- 地图矩形窗口；
- 直接转换为 SQL 条件。

限制：

- 矩形角落距离中心更远；
- 不能精确表达“距离某点多少公里”。

### Radius Query

适合：

- 城市附近；
- 指定中心点附近；
- 明确距离范围。

限制：

- 需要可靠的中心点坐标；
- 需要执行距离计算；
- 半径大小需要明确。

推荐规则：

```text
区域查询 -> bounding box
城市附近查询 -> radius query
```

---

## Place Is Not a Geographic Filter

`place` 是人类可读的位置描述，不是精确空间边界。

不建议：

```sql
WHERE place LIKE '%Japan%'
```

该方法可能漏掉：

- 使用海域名称描述的事件；
- 使用岛屿名称描述的事件；
- 使用城市距离描述的事件；
- 文本中未直接出现国家名称的事件。

正确流程：

```text
区域名称
-> bounding box 或中心点
-> latitude / longitude 过滤
```

`place` 主要用于结果展示。

---

## Combining Geographic Filters

空间条件可以与时间、震级和深度条件组合。

示例：

```json
{
  "start_time": "2026-06-01T00:00:00",
  "end_time": "2026-07-01T00:00:00",
  "min_magnitude": 5.0,
  "max_depth_km": 70.0,
  "min_latitude": 30.0,
  "max_latitude": 46.0,
  "min_longitude": 128.0,
  "max_longitude": 146.0,
  "order_by": "magnitude",
  "descending": true
}
```

对应查询：

```text
查询指定时间范围内，
位于指定空间范围，
震级不低于 5.0，
深度不超过 70 km 的地震，
并按震级降序排列。
```

---

## International Date Line

跨越国际日期变更线时，经度范围需要特殊处理。

普通经度范围：

```text
-180 到 180
```

跨日期变更线的区域可以：

1. 拆分成两个 bounding box；
2. 使用数据源支持的扩展经度范围；
3. 在数据库中增加专门的经度判断逻辑。

不能直接使用普通的：

```text
min_longitude <= longitude <= max_longitude
```

处理所有跨日期变更线场景。

---

## Recommended Region Mapping

后续可以维护区域配置文件：

```json
{
  "japan": {
    "query_method": "bounding_box",
    "min_latitude": 30.0,
    "max_latitude": 46.0,
    "min_longitude": 128.0,
    "max_longitude": 146.0
  },
  "tokyo": {
    "query_method": "radius",
    "latitude": 35.6762,
    "longitude": 139.6503,
    "max_radius_km": 300
  }
}
```

区域配置应记录：

```text
region_name
query_method
coordinates
radius_or_bounds
source
version
```

---

## Example Queries

```text
bounding box 和 radius query 有什么区别？
```

```text
查询日本附近地震时应该使用 place 还是经纬度？
```

```text
latitude 和 longitude 怎样用于空间过滤？
```

```text
为什么不能通过 embedding similarity 查询经纬度范围？
```

```text
城市附近 300 km 的地震应该使用哪种查询方法？
```

```text
跨越国际日期变更线时 longitude 过滤有什么问题？
```

---

## Sources

- U.S. Geological Survey, API Documentation - Earthquake Catalog:
  https://earthquake.usgs.gov/fdsnws/event/1/

- U.S. Geological Survey, GeoJSON Summary Format:
  https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php