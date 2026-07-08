# retrieval_eval_60 与 Hybrid Retrieval 阶段报告

## 1. 阶段背景

本阶段的目标，是把 SeismoSearch 的文档检索评估从 `retrieval_eval_40` 扩展到 `retrieval_eval_60`。

之前的 `retrieval_eval_40` 主要围绕原始的地震学概念文档进行评估，检索场景相对集中。后续新增了 4 份领域文档后，RAG 语料库变得更接近真实项目场景，包含：

- 地震目录字段解释；
- USGS 地震事件元数据说明；
- 地震安全边界说明；
- 地震危险性与地震预测的区别。

因此，本阶段重点不是继续追求旧测试集满分，而是观察不同检索器在多文档、多主题、语义重叠的语料库中是否仍然稳定。

---

## 2. 语料库扩展

本阶段新增了 4 份面向用户问答的领域知识文档：

```text
data/processed/docs/earthquake_catalog_fields.md
data/processed/docs/usgs_event_metadata.md
data/processed/docs/earthquake_safety_boundaries.md
data/processed/docs/seismic_hazard_vs_prediction.md