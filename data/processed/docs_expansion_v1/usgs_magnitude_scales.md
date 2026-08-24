# Earthquake Magnitude Scales

## Local Magnitude

Local magnitude，记作 ML，是 Richter 最初为特定距离、频率范围和仪器条件设计的局地震级。媒体常把各种震级统称为“里氏震级”，但现代地震目录可能使用多种不同计算方法。

## Body-wave and Surface-wave Magnitudes

Mb 主要利用体波，Ms 主要利用面波。不同震级类型针对不同信号频段和距离范围，在适用条件之外可能出现饱和或偏差，因此不能假设所有 magnitude type 完全等价。

## Moment Magnitude

Moment magnitude，记作 Mw，以地震矩为基础。地震矩与断层滑动面积、平均滑动量和介质刚度有关。Mw 对大地震通常比传统振幅震级更稳定，因而常用于描述大型远震。

## Catalog Interpretation

同一事件在初报和复核阶段可能出现不同震级值或震级类型。这可能来自新增台站数据、算法变化或人工复核，不应简单解释为地震本身“再次变强”。比较事件时应同时保留 magnitude、magnitude_type、status 和 updated 字段。

## References

- Source organization: U.S. Geological Survey
- FAQ: https://www.usgs.gov/faqs/moment-magnitude-richter-scale-what-are-different-magnitude-scales-and-why-are-there-so-many
- Technical overview: https://www.usgs.gov/programs/earthquake-hazards/earthquake-magnitude-energy-release-and-shaking-intensity
- Retrieved: 2026-08-23
