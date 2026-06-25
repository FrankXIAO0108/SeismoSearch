# SeismoSearch



A tool-augmented hybrid RAG system for public earthquake catalog search, seismology QA, evidence-grounded reporting, and safety-bounded risk communication.



SeismoSearch 是一个面向公开地震目录和地震学知识文档的混合 RAG 研究助手项目。项目核心不是“地震预测”，而是围绕已发生地震事件查询、地震目录解释、地震学概念问答、统计分析、报告生成、伪科学纠错和风险沟通，构建一个可评测、可追溯、带安全边界的 RAG Agent 系统。



## 1. 项目定位



SeismoSearch 面向“大模型算法实习生 / RAG Agent / 开发者服务 / 质量智能”相关岗位，重点展示以下能力：



\- 结构化数据查询

\- 文档 RAG

\- Query Router

\- 工具调用

\- Evidence Builder

\- Guardrail

\- 自动评测

\- 科学风险沟通



本项目的目标不是做一个普通聊天机器人，而是构建一个能够基于公开证据回答地震相关问题的工具增强型 RAG 系统。



## 2. 项目边界



SeismoSearch 支持以下任务：



\- 已发生地震事件查询

\- 按时间、震级、深度、地区等条件检索地震目录

\- 地震目录字段解释

\- 地震学概念问答

\- 地震事件统计分析

\- 基于证据生成简要报告

\- 纠正常见地震伪科学说法

\- 对预测诱导和恐慌型问题进行安全边界处理



SeismoSearch 不支持以下任务：



\- 预测未来是否会发生地震

\- 预测未来地震发生的时间、地点、震级

\- 生成无来源支撑的未来地震概率

\- 替代官方地震预警、应急管理或防灾机构建议

\- 给出个人撤离、搬家、买房、卖房、投资等决策建议



## 3. 为什么不是普通 RAG



地震问答并不适合只用普通文档 RAG 解决。



公开地震目录本质上是结构化数据，适合用 SQL 或结构化查询处理，例如：



\- 时间范围过滤

\- 震级过滤

\- 经纬度 / 地区过滤

\- 深度过滤

\- 排序

\- 聚合统计

\- 精确事件引用



地震学知识文档则是非结构化文本，适合用向量检索处理，例如：



\- 解释震级和烈度

\- 解释震源深度

\- 解释 tsunami、alert、mmi、sig 等字段

\- 解释地震风险沟通原则

\- 纠正地震预测相关伪科学



因此，本项目采用混合架构：



\- 结构化地震事件数据放入 DuckDB

\- 地震学知识文档切块后放入向量库

\- Query Router 判断问题类型

\- Planner 决定调用哪些工具

\- Evidence Builder 组织证据

\- Generator 基于证据生成回答

\- Guardrail 检查预测诱导、幻觉和越界表达

\- Evaluator 对不同 baseline 进行评测



## 4. 系统架构



整体流程如下：



```text

User Query

\-> Query Router

\-> Planner

\-> Tools

&#x20;  - event\_search

&#x20;  - event\_statistics

&#x20;  - doc\_retrieval

&#x20;  - safety\_check

\-> Evidence Builder

\-> Answer Generator

\-> Guardrail

\-> Final Answer


