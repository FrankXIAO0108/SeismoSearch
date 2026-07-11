# USGS Quality and Uncertainty Fields

## Overview

USGS 地震事件数据中包含多种质量和不确定性字段。

常见字段包括：

```text
nst
gap
dmin
rms
horizontalError
depthError
magError
status
updated
locationSource
magSource
```

这些字段应结合使用，不能依赖单个字段直接判断事件数据是否“准确”或“错误”。

---

## nst

`nst` 表示用于确定地震事件位置的地震台站数量。

一般情况下，更多有效观测可能为事件定位提供更多信息。

但不能简单认为：

```text
nst 越大
-> 定位一定越准确
```

还需要结合：

```text
station geometry
gap
dmin
rms
location uncertainty
```

判断。

---

## gap

`gap` 表示参与事件定位的台站之间最大的方位角空缺，单位通常为度。

一般来说：

```text
较小的 gap
```

意味着台站从更多方向包围事件。

而：

```text
较大的 gap
```

可能表示某些方向缺少观测。

但 gap 不能单独决定定位质量。

---

## dmin

`dmin` 表示震中到最近参与定位台站的水平距离，通常以角度表示。

较小的 dmin 往往意味着：

```text
事件附近存在较近的观测台站
```

但 dmin 的解释还会受到：

- 事件深度；
- 台网密度；
- 区域位置；
- 定位方法；

影响。

因此不能简单设置一个统一阈值判断所有事件。

---

## rms

`rms` 表示观测到时与定位模型计算到时之间残差的均方根。

它反映：

```text
观测数据
与
定位模型
```

之间的拟合程度。

较小的 rms 通常意味着残差较小。

但：

```text
rms 小
```

不等于：

```text
事件位置一定完全准确
```

还需要结合台站分布和位置不确定性。

---

## horizontalError

`horizontalError` 表示事件水平位置的不确定性，通常以千米为单位。

它用于描述震中位置估计的不确定程度。

较大的 horizontalError 表示：

```text
水平位置存在更大的不确定范围
```

它不表示：

- 地震影响半径；
- 受灾范围；
- 震动传播距离。

---

## depthError

`depthError` 表示震源深度估计的不确定性，通常以千米为单位。

例如：

```text
depth = 20 km
depthError = 8 km
```

说明深度估计存在明显不确定性。

因此在比较两个深度非常接近的事件时，应考虑 depthError。

---

## magError

`magError` 表示震级估计的不确定性。

它可以辅助解释：

```text
M5.9
```

和：

```text
M6.0
```

之间非常接近的数值差异。

magError 不表示：

- 地震预测误差；
- 未来地震概率；
- 破坏程度误差。

---

## status

`status` 表示事件处理状态。

常见状态包括：

```text
automatic
reviewed
```

`automatic` 通常表示事件主要由自动系统处理。

`reviewed` 表示事件已经经过进一步审核。

但是：

```text
status = reviewed
```

不表示：

```text
数据以后绝对不会再修改
```

事件仍可能因为：

- 新增观测数据；
- 产品更新；
- 数据源合并；
- 后续重新处理；

发生变化。

---

## updated

`updated` 表示事件记录最近一次更新时间。

它可以用于：

- 判断事件是否发生过后续更新；
- 区分事件发生时间和数据更新时间；
- 追踪同一事件记录的变化。

不要混淆：

```text
time
```

和：

```text
updated
```

`time` 表示事件发生时间。

`updated` 表示事件记录更新时间。

---

## locationSource

`locationSource` 表示提供首选事件位置结果的数据源或网络。

它可以帮助追踪：

```text
事件位置由哪个来源提供
```

但它不表示：

```text
该来源的数据一定比其他来源准确
```

---

## magSource

`magSource` 表示提供首选震级结果的数据源或网络。

它用于追踪震级来源。

不要混淆：

```text
magSource
```

和：

```text
magType
```

`magSource` 关注：

```text
震级结果来自哪里
```

`magType` 关注：

```text
使用了哪种震级类型
```

---

## Combining Quality Fields

判断事件数据质量时，可以组合查看：

```text
nst
gap
dmin
rms
horizontalError
depthError
status
updated
```

例如：

```text
较大的 gap
+ 较大的 horizontalError
+ automatic status
```

可能提示事件位置仍具有较大不确定性。

但系统不应该根据简单规则直接宣布：

```text
这条数据是错误的
```

更准确的表达是：

```text
该事件的部分质量指标显示定位存在较大不确定性。
```

---

## What These Fields Do Not Mean

质量字段不能用于：

- 预测未来地震；
- 判断某地是否即将发生大地震；
- 直接估计人员伤亡；
- 直接判断建筑损失；
- 代替专业地震目录质量控制。

---

## Example Queries

```text
gap、dmin 和 rms 分别表示什么？
```

```text
gap 越小是不是说明定位一定越准确？
```

```text
horizontalError 和 depthError 有什么区别？
```

```text
status=reviewed 是不是表示数据以后绝对不会变化？
```

```text
time 和 updated 有什么区别？
```

```text
magSource 和 magType 是同一个字段吗？
```

```text
如何综合判断一条地震事件记录的不确定性？
```

---

## Sources

- U.S. Geological Survey, GeoJSON Summary Format:
  https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php

- U.S. Geological Survey, ANSS Comprehensive Earthquake Catalog Documentation:
  https://earthquake.usgs.gov/data/comcat/index.php