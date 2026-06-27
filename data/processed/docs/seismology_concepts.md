# Seismology Concepts Seed Document

This is a local seed document for SeismoSearch concept retrieval.
It is used for deterministic RAG baseline testing before external document ingestion is implemented.

## 震级和烈度的区别

震级表示一次地震释放能量的大小，通常用 magnitude 表示。常见震级类型包括 Mw、ML、Mb 等。震级通常用于描述地震事件本身的规模。

烈度表示某个地点受到地震影响或破坏的强弱，通常与震源距离、震源深度、场地条件、建筑结构和地震波传播有关。烈度不是地震本身的单一属性，而是不同地点可能不同。

因此，同一次地震通常只有一个主要震级估计，但不同地区可能有不同烈度。震级回答的是“这次地震有多大”，烈度回答的是“某个地方震感或破坏有多强”。

## Magnitude and Intensity

Earthquake magnitude describes the size or energy release of an earthquake source. It is usually reported as a single value for an earthquake event, although different magnitude scales may exist.

Seismic intensity describes the observed shaking effects at a specific location. Intensity can vary from place to place for the same earthquake because distance, depth, local geology, and building vulnerability affect shaking and damage.

In short, magnitude characterizes the earthquake source, while intensity characterizes local effects.

## 地震深度

地震深度表示震源位于地表以下的距离，通常以 km 为单位。浅源地震一般更容易造成明显地表震感，但实际影响还取决于震级、距离、地质条件和建筑抗震能力。

## 海啸提示

并不是所有海底地震都会引发海啸。海啸风险通常与地震震级、震源机制、海底垂直位移、震源深度和海域条件有关。是否存在海啸威胁应以官方机构发布的信息为准。