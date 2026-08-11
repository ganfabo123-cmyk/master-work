# Software incident sample

## Selected sample

- Dataset: RCAEval multi-source telemetry sample
- System: Online Boutique microservices
- Source: https://github.com/phamquiluan/RCAEval/releases/download/0.2.0/multi-source-data.zip
- Documentation: https://github.com/phamquiluan/RCAEval/blob/main/docs/multi-source-rca-demo.ipynb
- Retrieved: 2026-08-10
- License: MIT, as declared by RCAEval for its code and datasets
- Source archive SHA-256: `81D87640EB9E976325D9EF56D423455454D3CB49CA52041651F628A4D010C66A`

The unmodified source archive is `rcaeval_multi_source_sample.zip`. Its extracted
contents are under `rcaeval_multi_source_sample/multi-source-data/`.

## Source files

- `metrics.csv`: service metrics around the incident.
- `logs.csv`: raw service logs.
- `traces.csv`: distributed trace spans.
- `logts.csv`: time series derived from parsed logs.
- `tracets_err.csv`: trace error time series.
- `tracets_lat.csv`: trace latency time series.
- `cluster_info.json`: log-template metadata.
- `inject_time.txt`: fault injection timestamp (`1705354566`).

This directory contains source data only. It has not yet been converted into a
CoWorker State or split into per-expert Observations. The accompanying RCAEval
tutorial reports algorithm rankings for the sample, not an explicit authoritative
ground-truth label; do not silently treat the first ranked metric as ground truth.
