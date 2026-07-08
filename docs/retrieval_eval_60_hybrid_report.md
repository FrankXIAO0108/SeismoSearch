# Retrieval Eval 60 and Hybrid Retrieval Report

## 1. Background

This stage extends SeismoSearch document retrieval evaluation from `retrieval_eval_40` to `retrieval_eval_60`.

The previous `retrieval_eval_40` mainly focused on the original seismology concept document. After adding four new domain documents, the retrieval corpus now covers:

- earthquake catalog fields;
- USGS event metadata;
- earthquake safety boundaries;
- seismic hazard vs earthquake prediction.

The goal is to test whether different retrievers can handle a more realistic multi-document domain corpus.

---

## 2. Corpus Expansion

Added four user-facing domain knowledge documents:

```text
data/processed/docs/earthquake_catalog_fields.md
data/processed/docs/usgs_event_metadata.md
data/processed/docs/earthquake_safety_boundaries.md
data/processed/docs/seismic_hazard_vs_prediction.md