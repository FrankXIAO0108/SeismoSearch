# SeismoSearch Progress

当前总进度：7%

```text
[██----------------------------] 7 / 100
```

## 进度规则

本项目进度只按可验收交付物计算，不按投入时间计算。

一个模块只有满足以下条件，才算完成：

1. 文件已经落地；
2. 内容不是空壳；
3. 已经通过基本检查；
4. 已经 git commit；
5. 已经 push 到 GitHub；
6. 能解释这个模块解决什么问题、为什么需要、怎么评估有效。

## 里程碑总览

| 模块                              |  权重 | 状态  | 得分 |
| ------------------------------- | --: | --- | -: |
| 仓库与项目定义                         | 10% | 进行中 |  7 |
| 数据契约                            | 15% | 未开始 |  0 |
| 证据与评测契约                         | 20% | 未开始 |  0 |
| 数据采集与入库                         | 15% | 未开始 |  0 |
| 检索与工具模块                         | 15% | 未开始 |  0 |
| Evidence + Guardrail + Pipeline | 15% | 未开始 |  0 |
| Baseline 评测与项目包装                | 10% | 未开始 |  0 |

当前总分：7 / 100

## Week 1：项目定义与数据骨架

目标进度：0% -> 30%

### 必须完成

* [x] GitHub 仓库创建
* [x] 本地 Git 初始化
* [x] 项目目录骨架
* [x] README 初版
* [ ] `schemas/events_schema.sql`
* [ ] `schemas/doc_chunks_schema.sql`
* [ ] `schemas/evidence_pack_schema.json`
* [ ] `schemas/eval_schema.json`
* [ ] `docs/risk_boundary.md`
* [ ] `data_card.md`
* [ ] `eval/eval_80.jsonl` 结构设计

### Week 1 验收标准

* 能解释为什么 SeismoSearch 不是普通 RAG demo；
* 能解释为什么地震事件需要结构化查询；
* 能解释 Evidence Pack 如何约束生成；
* 能解释 80 条评测集如何覆盖 catalog / concept / mixed / safety；
* 所有 schema 文件可被程序读取或校验。

## 当前待办

下一步任务：

1. 完成 `schemas/events_schema.sql`
2. 完成 `schemas/doc_chunks_schema.sql`
3. 提交 commit：`add event and document chunk schemas`

## 当前风险

* Git / Markdown / 编码基础还不稳定；
* 容易把 README 做成包装文档，而不是工程说明；
* 还没有真正进入数据、评测和 baseline；
* 如果 eval 没有 gold evidence，项目会被面试官打穿；
* 如果 safety 只做关键词拦截，Guardrail 没有说服力。
