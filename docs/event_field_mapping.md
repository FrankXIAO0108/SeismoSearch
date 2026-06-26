# Event Field Mapping

## 1. 文件目的

本文件定义 SeismoSearch 第一阶段地震事件数据的字段映射规则。

SeismoSearch 不直接把原始地震目录字段暴露给下游模块，而是采用三层数据流：

```text
raw data
-> staging layer
-> normalized events table
```

本文件重点说明：

* 原始 USGS 事件字段如何解析；
* staging 层如何暂存原始字段；
* normalized `events` 表如何统一字段命名；
* 哪些字段是必需字段；
* 哪些字段允许为空；
* 字段单位和类型如何转换；
* 哪些字段只保存在 `raw_record_json` 中。

## 2. 数据源范围

第一阶段主事件数据源：

```text
USGS Earthquake Catalog / GeoJSON
```

第一阶段目标：

* 获取约 1000 条公开地震事件样例；
* 支持 catalog / mixed 类问题；
* 支持 event_search 和 event_statistics；
* 支持 Evidence Pack 中的 event_evidence；
* 不用于地震预测。

## 3. 三层数据流

### 3.1 raw data

raw 层保存原始 USGS 响应，不修改字段。

示例目录：

```text
data/raw/events/
```

保存内容可以包括：

```text
usgs_events_raw.geojson
usgs_events_raw.json
```

raw 层原则：

* 不重命名字段；
* 不删除字段；
* 不提前合并字段；
* 保留完整原始记录；
* 用于审计和重新清洗。

### 3.2 staging layer

staging 层用于临时解析 USGS 原始字段。

staging 层字段可以接近 USGS 原始字段，例如：

```text
id
properties.mag
properties.place
properties.time
properties.updated
properties.tz
properties.url
properties.detail
properties.felt
properties.cdi
properties.mmi
properties.alert
properties.status
properties.tsunami
properties.sig
properties.net
properties.code
properties.ids
properties.sources
properties.types
properties.nst
properties.dmin
properties.rms
properties.gap
properties.magType
properties.type
properties.title
geometry.coordinates
```

staging 层作用：

* 检查字段是否存在；
* 检查字段类型；
* 检查缺失值；
* 检查异常值；
* 记录原始字段到标准字段的转换规则；
* 不直接服务问答系统。

### 3.3 normalized events table

normalized 层写入 DuckDB 表：

```text
events
```

对应 schema：

```text
schemas/events_schema.sql
```

该层字段使用 SeismoSearch 内部统一命名，例如：

```text
event_id
source
source_event_id
event_time_utc
updated_time_utc
longitude
latitude
depth_km
magnitude
magnitude_type
place
event_type
status
source_url
detail_url
raw_record_json
```

normalized 层作用：

* 支撑结构化查询；
* 支撑统计分析；
* 支撑 Evidence Pack；
* 支撑 Evaluator；
* 隔离不同数据源之间的字段差异。

## 4. 字段映射表

| USGS raw field                | staging field            | normalized field         | required | conversion rule                             | notes                                   |
| ----------------------------- | ------------------------ | ------------------------ | -------- | ------------------------------------------- | --------------------------------------- |
| `id`                          | `id`                     | `source_event_id`        | yes      | keep as string                              | USGS 原始事件 ID                            |
| `id`                          | `id`                     | `event_id`               | yes      | prefix with source, e.g. `usgs_{id}`        | SeismoSearch 内部稳定 ID                    |
| constant                      | `source`                 | `source`                 | yes      | set to `USGS`                               | 数据来源                                    |
| `properties.url`              | `url`                    | `source_url`             | no       | keep as string                              | 事件页面 URL                                |
| `properties.detail`           | `detail`                 | `detail_url`             | no       | keep as string                              | 事件详情 GeoJSON URL                        |
| `properties.type`             | `type`                   | `event_type`             | no       | keep as string                              | earthquake / quarry blast / explosion 等 |
| `properties.status`           | `status`                 | `status`                 | no       | keep as string                              | reviewed / automatic 等                  |
| `properties.time`             | `time`                   | `event_time_utc`         | yes      | Unix milliseconds -> UTC timestamp          | 事件发生时间                                  |
| `properties.updated`          | `updated`                | `updated_time_utc`       | no       | Unix milliseconds -> UTC timestamp          | 来源数据更新时间                                |
| `properties.time`             | `time`                   | `event_date_utc`         | no       | extract UTC date from event_time_utc        | 便于按日聚合                                  |
| `geometry.coordinates[0]`     | `longitude`              | `longitude`              | yes      | cast to DOUBLE                              | 经度                                      |
| `geometry.coordinates[1]`     | `latitude`               | `latitude`               | yes      | cast to DOUBLE                              | 纬度                                      |
| `geometry.coordinates[2]`     | `depth`                  | `depth_km`               | no       | cast to DOUBLE                              | 深度，单位 km                                |
| `properties.place`            | `place`                  | `place`                  | no       | keep as string                              | 原始地点描述                                  |
| derived                       | `region`                 | `region`                 | no       | optional geocoding or text parsing          | 第一阶段可为空                                 |
| derived                       | `country`                | `country`                | no       | optional geocoding or text parsing          | 海域事件不能强行归属国家                            |
| `properties.mag`              | `mag`                    | `magnitude`              | no       | cast to DOUBLE                              | 震级                                      |
| `properties.magType`          | `magType`                | `magnitude_type`         | no       | lowercase or keep source value consistently | 震级类型                                    |
| unavailable or product detail | `magError`               | `magnitude_error`        | no       | cast to DOUBLE if available                 | 第一阶段可为空                                 |
| unavailable or product detail | `magNst`                 | `magnitude_nst`          | no       | cast to INTEGER if available                | 第一阶段可为空                                 |
| derived/source                | `magSource`              | `magnitude_source`       | no       | keep as string                              | 第一阶段可为空                                 |
| unavailable or product detail | `horizontalError`        | `horizontal_error_km`    | no       | cast to DOUBLE if available                 | 第一阶段可为空                                 |
| unavailable or product detail | `depthError`             | `depth_error_km`         | no       | cast to DOUBLE if available                 | 第一阶段可为空                                 |
| `properties.nst`              | `nst`                    | `nst`                    | no       | cast to INTEGER                             | 定位台站数                                   |
| `properties.gap`              | `gap`                    | `gap_deg`                | no       | cast to DOUBLE                              | 方位角间隙                                   |
| `properties.dmin`             | `dmin`                   | `dmin_deg`               | no       | cast to DOUBLE                              | 最近台站距离，单位 degree                        |
| `properties.rms`              | `rms`                    | `rms_sec`                | no       | cast to DOUBLE                              | 走时残差 RMS                                |
| derived/source                | `locationSource`         | `location_source`        | no       | keep as string                              | 第一阶段可为空                                 |
| `properties.felt`             | `felt`                   | `felt`                   | no       | cast to INTEGER                             | 震感报告数                                   |
| `properties.cdi`              | `cdi`                    | `cdi`                    | no       | cast to DOUBLE                              | Community Decimal Intensity             |
| `properties.mmi`              | `mmi`                    | `mmi`                    | no       | cast to DOUBLE                              | Modified Mercalli Intensity             |
| `properties.alert`            | `alert`                  | `alert`                  | no       | keep as string or null                      | green / yellow / orange / red           |
| `properties.tsunami`          | `tsunami`                | `tsunami`                | no       | cast to INTEGER                             | 通常为 0 或 1                               |
| `properties.sig`              | `sig`                    | `significance`           | no       | cast to INTEGER                             | USGS significance score                 |
| `properties.net`              | `net`                    | `net`                    | no       | keep as string                              | 网络代码                                    |
| `properties.code`             | `code`                   | `code`                   | no       | keep as string                              | 事件代码                                    |
| `properties.ids`              | `ids`                    | `ids`                    | no       | keep as string                              | 相关事件 ID                                 |
| `properties.sources`          | `sources`                | `sources`                | no       | keep as string                              | 贡献来源                                    |
| `properties.types`            | `types`                  | `product_types`          | no       | keep as string                              | 产品类型列表                                  |
| ingestion time                | `ingest_time_utc`        | `ingest_time_utc`        | yes      | current UTC timestamp                       | 入库时间                                    |
| constant                      | `raw_format`             | `raw_format`             | yes      | set to `geojson`                            | 原始数据格式                                  |
| full feature object           | `raw_record_json`        | `raw_record_json`        | yes      | serialize full feature as JSON              | 保留原始记录                                  |
| `properties.status`           | `status`                 | `is_reviewed`            | no       | true if status equals `reviewed`            | 审核状态派生                                  |
| derived                       | `is_duplicate_candidate` | `is_duplicate_candidate` | no       | default false                               | 后续去重用                                   |
| derived                       | `data_quality_note`      | `data_quality_note`      | no       | generated during validation                 | 数据质量说明                                  |

## 5. 必需字段

第一阶段写入 `events` 表时，以下字段必须存在：

```text
event_id
source
event_time_utc
longitude
latitude
ingest_time_utc
raw_format
raw_record_json
```

如果以下字段缺失，该事件仍可保留，但需要记录 `data_quality_note`：

```text
magnitude
depth_km
place
magnitude_type
status
source_url
detail_url
```

如果 `event_time_utc`、`longitude` 或 `latitude` 缺失，该事件不应进入 normalized `events` 表。

## 6. 类型转换规则

### 6.1 时间转换

USGS `properties.time` 和 `properties.updated` 通常是 Unix milliseconds。

转换规则：

```text
Unix milliseconds -> UTC timestamp
```

示例：

```text
properties.time -> event_time_utc
properties.updated -> updated_time_utc
```

注意：

* 不要把 milliseconds 当成 seconds；
* 所有时间统一为 UTC；
* `event_date_utc` 从 `event_time_utc` 派生。

### 6.2 经纬度和深度转换

USGS GeoJSON 的 `geometry.coordinates` 通常按以下顺序存储：

```text
[longitude, latitude, depth]
```

映射规则：

```text
coordinates[0] -> longitude
coordinates[1] -> latitude
coordinates[2] -> depth_km
```

注意：

* 不要把 latitude 和 longitude 反过来；
* depth 单位为 km；
* 深度允许为空，但如果存在应转为 DOUBLE。

### 6.3 震级转换

映射规则：

```text
properties.mag -> magnitude
properties.magType -> magnitude_type
```

注意：

* `magnitude` 允许为空；
* 不同 `magnitude_type` 不能简单理解为完全等价；
* 回答中如果需要解释震级，应保留 magnitude_type。

### 6.4 状态转换

映射规则：

```text
properties.status -> status
status == reviewed -> is_reviewed = true
otherwise -> is_reviewed = false or null
```

注意：

* automatic 事件不应被表述为最终审核结果；
* 回答中涉及数据可信度时，应说明事件状态。

### 6.5 tsunami 和 alert 转换

映射规则：

```text
properties.tsunami -> tsunami
properties.alert -> alert
```

注意：

* `tsunami = 1` 不应被直接解释为“已经发生海啸”；
* `alert` 需要结合文档解释，不能单独过度解读；
* mixed 问题中应结合 doc_evidence 解释这些字段。

## 7. 数据质量检查

导入前需要检查：

* `event_id` 是否唯一；
* `event_time_utc` 是否为空；
* `longitude` 是否在 [-180, 180]；
* `latitude` 是否在 [-90, 90]；
* `depth_km` 是否为数值；
* `magnitude` 是否为数值或 null；
* `status` 是否存在；
* `source_event_id` 是否为空；
* `raw_record_json` 是否完整保留。

如果发现异常，应写入：

```text
data_quality_note
```

## 8. 不进入标准字段但保留的内容

以下内容第一阶段可以不进入标准字段，但必须保存在 `raw_record_json`：

* `properties.title`
* 未解析的 product details；
* 未使用的扩展字段；
* 未来新增的 USGS 字段；
* 暂时不确定含义的字段。

原则：

```text
不确定含义的字段先保留，不急着进入主 schema。
```

## 9. 对下游模块的影响

### 9.1 event_store.py

`event_store.py` 只依赖 normalized `events` 表，不直接依赖 USGS 原始字段。

这样可以避免下游代码写成：

```text
properties.mag
properties.time
properties.place
```

而应该统一使用：

```text
magnitude
event_time_utc
place
```

### 9.2 evidence_builder.py

`evidence_builder.py` 使用 normalized 字段构造 `event_evidence`。

例如：

```text
event_id
event_time_utc
longitude
latitude
depth_km
magnitude
magnitude_type
source_url
detail_url
```

### 9.3 evaluator.py

`evaluator.py` 使用 normalized 字段判断：

* 查询条件是否匹配；
* event_id 是否正确；
* magnitude 是否满足条件；
* 时间范围是否正确；
* 统计结果是否正确。

## 10. 当前版本

当前版本：0.1.0

当前状态：第一阶段字段映射设计。

后续拿到真实 USGS 样例数据后，需要根据实际字段 profiling 更新本文件。
