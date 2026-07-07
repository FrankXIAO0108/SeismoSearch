# Retrieval Eval 40 Report

## 1. 背景

SeismoSearch 当前是一个 deterministic Agentic RAG baseline，系统需要同时处理：

- catalog query：结构化地震事件查询；
- concept query：地震学概念解释；
- mixed query：事件查询 + 概念解释；
- safety query：地震预测诱导、伪科学前兆、历史活动风险推断等安全问题。

在完整 pipeline eval 中，doc_evidence_hit_rate 可以反映系统是否返回了文档证据，但它无法单独判断 retrieval 层的质量。

因此，本阶段单独构建 retrieval evaluation，用于评估文档检索模块本身。

---

## 2. 评估目标

本阶段 retrieval evaluation 主要回答以下问题：

1. retriever 是否能找回预期来源文档；
2. retriever 是否能找回包含关键概念的 evidence chunk；
3. 正确 evidence 出现在第几位；
4. planner rewrite 是否比 raw query 更有效；
5. keyword retriever 和 BM25 retriever 是否存在明显差异；
6. 当 MRR 下降时，问题来自 retriever、corpus、query rewrite，还是 evaluator 本身。

---

## 3. Retriever 设置

本阶段对比两个 sparse retrieval baseline：

### 3.1 Keyword Retriever

文件：

```text
src/seismosearch/doc_retriever.py