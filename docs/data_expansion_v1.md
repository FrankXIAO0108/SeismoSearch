# Data Expansion V1

## 结论

V1 将事件层从 1,000 条样例扩展为 39,320 条真实地震事件，并新增 8 篇权威来源文档。扩展数据目前是可选版本，不直接替换原默认库。

## 事件快照

| 字段 | 值 |
|---|---:|
| 来源 | USGS FDSN Event Web Service |
| 时间范围 | 2021-01-01 至 2025-12-31 |
| 过滤条件 | global, `minmagnitude=4.5`, `eventtype=earthquake` |
| 归一化事件 | 39,320 |
| 重复 / 无效 / 缺失震级 | 0 / 0 / 0 |
| 震级范围 | 4.5–8.8 |
| JSONL 大小 | 79,017,839 bytes |
| JSONL SHA-256 | `7d95954d347f5ae1add17ac080a4260c836652df777271eca361c92b7de94793` |

为避免 USGS 单次查询上限导致静默截断，构建器使用半开时间窗口分片，且在任一窗口命中上限时直接失败。详细窗口、质量统计与 Hash 见 `data/processed/events_catalog_2021_2025_m45.manifest.json`。

重建命令：

```powershell
$env:PYTHONPATH="$PWD\src"
python .\scripts\build_event_catalog_snapshot.py --starttime 2021-01-01 --endtime 2026-01-01 --min-magnitude 4.5 --event-type earthquake --processed-output data\processed\events_catalog_2021_2025_m45.jsonl --manifest-output data\processed\events_catalog_2021_2025_m45.manifest.json --raw-output-dir data\raw\events\catalog_2021_2025_m45
python .\scripts\build_event_db.py --input data\processed\events_catalog_2021_2025_m45.jsonl --db data\duckdb\seismosearch_catalog_2021_2025_m45.duckdb
```

DuckDB 导入已改为 `read_json_auto` 批量插入。本机本次构建耗时 4.50 s；该数字只是本地实测，不是跨环境性能承诺。

在 39,320 条库上各热身 30 次的本机读取结果：M6.5+ 排序查询中位数 1.49 ms，年度聚合 0.74 ms，经纬度框选 0.60 ms。这些只表明本地 DuckDB 对当前数据规模不是瓶颈。

## 文档语料

- 原语料：17 文档、171 chunks、34,281 字符。
- Expansion V1：8 文档、41 chunks、4,078 字符。
- 合计：25 文档、212 chunks、38,359 字符。

新文档覆盖预测/预报/预警边界、动物异常、地震活动率、震级标度、震级与烈度、定位与深度、地震序列及防震安全。来源列表见 `data/processed/doc_corpus_manifest_v1.json`。

## 评测与对抗审阅

- Expansion V1 开发集：16 queries，Requirement Hit@5 = 1.000，MRR = 0.6875，0 失败。这是用于迭代的开发集，不能写成盲测成绩。
- 60-query 开发集 candidate ablation：rerank `candidate_k=10` 已达 Requirement Hit@5 = 1.000，本机平均 3.43 s/query；增至 20/30 未改善该指标。
- 直接合并语料曾使原有冻结集退化，因此扩展文档被放入独立目录，默认检索仍只读取 `data/processed/docs/`。
- 当前环境的原语料复测为 Requirement Hit@5 = 0.8077，低于仓库已冻结结果 0.8846。由于 dense/reranker 模型和本地环境未冻结成完整可复现包，这一差异不能归因为新语料，也不应被隐藏。

## 尚未完成的证据

Expansion V1 还没有独立、未参与调参的新 Holdout，也没有生产流量和线上时延证据。简历中可陈述数据工程、质量门禁、批量建库和开发集结果，不应陈述“生产级”或“盲测 100%”。
