# Earthquake Location and Depth Estimation

## Hypocenter and Epicenter

Hypocenter 是地下破裂起始位置，通常包含纬度、经度和深度；epicenter 是其在地表上的投影。事件目录中的 place 是便于阅读的位置描述，不能替代数值坐标。

## Locating an Event

地震台网记录地震波到达各台站的时间。定位算法从一个初始震源位置和发震时刻出发，利用速度模型计算理论到时，再反复调整位置、深度和时间，使计算到时与观测到时的差异减小。

## Location Uncertainty

定位结果依赖台站分布、到时拾取质量和地下速度模型。台站覆盖不均或事件位于台网之外时，水平误差与深度误差可能增大。目录中的坐标不应被描述成无误差的精确点。

## Zero or Negative Depth

极浅事件有时会显示 0 km 或轻微负深度。这通常与参考面、浅源定位分辨率或特定事件类型的固定深度有关，并不表示地震发生在空气中。深度通常是震源参数中约束较弱的一项，应结合 depthError、事件类型和来源解释。

## References

- Source organization: U.S. Geological Survey
- Location FAQ: https://www.usgs.gov/faqs/how-do-seismologists-locate-earthquake
- Depth FAQ: https://www.usgs.gov/faqs/what-does-it-mean-earthquake-occurred-a-depth-0-km-how-can-earthquake-have-a-negative-depth
- Retrieved: 2026-08-23
