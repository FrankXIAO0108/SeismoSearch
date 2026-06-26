# Source List

## 1. 文件目的

本文件记录 SeismoSearch 第一阶段计划使用的数据来源和文档来源。

本文件不是最终数据清单，而是第一版 source registry。后续每新增、删除或替换一个数据源，都必须更新本文件。

SeismoSearch 使用两类来源：

1. 地震事件目录数据源；
2. 地震学知识文档来源。

所有来源必须满足以下要求：

* 公开可访问；
* 来源机构相对可信；
* 能支持证据追溯；
* 能服务 catalog / concept / mixed / safety 四类评测问题；
* 不把历史统计包装成地震预测。

## 2. 数据源选择原则

### 2.1 优先使用权威公开来源

优先选择：

* 官方地震机构；
* 科研或教育机构；
* 防灾减灾官方机构；
* 可公开引用的技术文档或科普资料。

暂不使用：

* 自媒体文章；
* 未标明来源的二手资料；
* 论坛传言；
* 地震预测类网站；
* 伪科学内容作为正向知识来源。

伪科学材料只允许作为 safety / misinformation 测试样本的诱导问题来源，不作为事实知识来源。

### 2.2 数据必须可追溯

事件数据至少需要保留：

* source；
* source_event_id；
* source_url；
* detail_url；
* event_time_utc；
* latitude；
* longitude；
* magnitude；
* depth_km；
* raw_record_json。

文档数据至少需要保留：

* source_name；
* source_url；
* title；
* author_or_org；
* fetched_time_utc；
* section_title；
* section_path；
* content_hash。

### 2.3 先小规模闭环，不追求大而全

第一阶段只需要：

* 1000 条地震事件样例；
* 10 篇地震学知识文档；
* 80 条评测问题。

目标是验证：

* 结构化查询是否有效；
* 文档检索是否有效；
* Evidence Pack 是否能约束生成；
* Guardrail 是否能处理预测诱导；
* baseline 对比是否能跑通。

第一阶段不追求覆盖所有地震目录和所有地震学知识。

## 3. 地震事件目录来源

### 3.1 USGS Earthquake Catalog API

用途：

* 第一阶段主事件目录来源；
* 构造 1000 条地震事件样例；
* 支持 catalog 类问题；
* 支持 mixed 类问题中的事件查询部分；
* 支持 event_statistics 统计分析。

计划使用字段：

* id；
* time；
* updated；
* latitude；
* longitude；
* depth；
* mag；
* magType；
* place；
* type；
* status；
* tsunami；
* alert；
* sig；
* felt；
* cdi；
* mmi；
* nst；
* gap；
* dmin；
* rms；
* net；
* code；
* ids；
* sources；
* types；
* detail。

映射目标：

* 写入 raw data；
* 解析到 staging layer；
* 映射到 normalized events table；
* 保留 raw_record_json。

对应标准表：

```text
events
```

对应 schema：

```text
schemas/events_schema.sql
```

第一阶段使用方式：

* 先采样 1000 条事件；
* 优先覆盖不同震级、深度、地区、alert、tsunami 情况；
* 不做实时预警；
* 不把目录统计解释成未来预测。

质量注意事项：

* automatic 与 reviewed 事件质量不同；
* 事件信息可能后续更新；
* 海域地震地点描述不等于国家归属；
* 不同震级类型不能简单混为完全等价；
* 需要保留 source_event_id 和 raw_record_json。

## 4. 地震学知识文档来源

### 4.1 USGS Earthquake Hazards FAQ

用途：

* 地震基础概念解释；
* 地震预测边界；
* 常见误解纠正；
* safety 类问题回答依据；
* risk_boundary.md 的知识支撑。

适用问题：

* 能不能预测地震？
* 地震概率和地震预测有什么区别？
* 地震发生前有没有可靠前兆？
* 地震目录中的字段如何理解？

处理方式：

* 抓取或人工整理 FAQ 页面；
* 按问题主题切分；
* 写入 doc_chunks；
* topic_tags 包含 concept、safety、misinformation。

### 4.2 USGS Earthquake Magnitude, Energy Release, and Shaking Intensity

用途：

* 解释 magnitude；
* 解释 intensity；
* 解释 energy release；
* 区分震级和烈度；
* 支持 concept 与 mixed 问题。

适用问题：

* 震级和烈度有什么区别？
* 为什么同一震级在不同地区破坏不同？
* magnitude、energy release、shaking intensity 是什么关系？

处理方式：

* 按概念段落切块；
* 保留 section_title 和 section_path；
* topic_tags 包含 magnitude、intensity、concept。

### 4.3 IRIS / SAGE Educational Resources

用途：

* 地震学教育材料；
* 震级、震源机制、地震波等基础概念；
* 支持面向普通用户的解释；
* 作为 USGS 文档之外的补充来源。

适用问题：

* Moment magnitude 和 Richter scale 有什么区别？
* 地震波是什么？
* 地震仪如何记录地震？

处理方式：

* 优先选择文字说明清晰、可引用的教育页面；
* 不优先使用纯视频资源；
* 如果使用动画资源，需要额外记录页面标题和文字说明。

### 4.4 Ready.gov / FEMA Earthquake Preparedness

用途：

* 一般性防灾准备；
* safety 类问题拒绝后的替代信息；
* 风险沟通；
* 不作为地震预测依据。

适用问题：

* 地震前平时应该准备什么？
* 如果担心地震风险，可以做哪些一般性准备？
* 为什么应该关注官方应急信息？

处理方式：

* 只提取一般性 preparedness 信息；
* 不生成个人化撤离、搬家、买卖房建议；
* topic_tags 包含 preparedness、risk_communication、safety。

## 5. 第一阶段计划收集的 10 篇文档

第一版知识文档计划如下：

| doc_id  | source_name      | document_topic                          | purpose                              | status  |
| ------- | ---------------- | --------------------------------------- | ------------------------------------ | ------- |
| doc_001 | USGS             | earthquake prediction FAQ               | safety boundary / prediction refusal | planned |
| doc_002 | USGS             | magnitude vs intensity                  | concept QA                           | planned |
| doc_003 | USGS             | earthquake magnitude and energy release | concept QA                           | planned |
| doc_004 | USGS             | earthquake catalog field explanation    | catalog interpretation               | planned |
| doc_005 | USGS             | tsunami and earthquake relation         | mixed QA / safety                    | planned |
| doc_006 | IRIS/SAGE        | moment magnitude explanation            | concept QA                           | planned |
| doc_007 | IRIS/SAGE        | seismic waves basics                    | concept QA                           | planned |
| doc_008 | IRIS/SAGE        | earthquake location basics              | concept QA                           | planned |
| doc_009 | Ready.gov / FEMA | earthquake preparedness                 | risk communication                   | planned |
| doc_010 | Ready.gov / FEMA | emergency alerts and safety actions     | safety alternative response          | planned |

注意：

* 第一阶段可以先手工整理文档；
* 后续再写 `scripts/ingest_docs.py` 自动化处理；
* 每篇文档必须进入 `doc_chunks`；
* 每个 chunk 必须保留 source_url、title、section_path、content_hash。

## 6. 不使用的数据来源

第一阶段不使用以下来源作为事实知识来源：

* 地震预测网站；
* 星座、动物异常、地震云相关伪科学文章；
* 未标明来源的短视频文案；
* 社交媒体传言；
* 未经核验的新闻评论；
* 没有清晰来源的百科搬运内容。

这些内容可以被用于构造 safety 问题，但不能作为事实证据进入 doc_chunks。

## 7. 后续需要补充

后续需要补充以下文件：

* `docs/event_field_mapping.md`
* `docs/chunking_policy.md`
* `scripts/ingest_events.py`
* `scripts/ingest_docs.py`
* `data/processed/events_sample_1000.jsonl`
* `data/processed/doc_chunks_sample.jsonl`

每次实际采集数据后，需要更新：

* 数据来源；
* 抓取时间；
* 字段映射；
* 数据规模；
* 数据质量问题；
* 是否进入 eval 或 retrieval index。

## 8. 当前状态

当前版本：0.1.0

当前阶段：source planning

已确定：

* USGS Earthquake Catalog API 作为第一阶段主事件目录来源；
* USGS FAQ、USGS magnitude/intensity 文档、IRIS/SAGE 教育资源、Ready.gov/FEMA 防灾材料作为第一阶段知识文档候选来源。

待完成：

* 确认 10 篇具体文档 URL；
* 完成 event field mapping；
* 下载或整理 1000 条事件样例；
* 完成文档切块策略；
* 构造 doc_chunks 样例。
