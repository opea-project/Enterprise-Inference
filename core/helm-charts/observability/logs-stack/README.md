
# 📘 Observability Log Stack: OpenTelemetry Collector + Loki + AWS S3 (Logs Pipeline)

This repository contains a Helm-based deployment for a Kubernetes-native log collection and storage system using:

- **OpenTelemetry Collector** (as DaemonSet)
- **Grafana Loki** in SimpleScalable mode
- **AWS S3** as the long-term object store
- **OTLP over HTTP** for pushing logs from OTEL to Loki

---

## 🧩 Components Overview

| Component            | Purpose                                                                 |
|----------------------|-------------------------------------------------------------------------|
| `otelcol-logs`       | OpenTelemetry Collector scraping pod logs via `filelog` receiver        |
| `loki`               | Stores, indexes, and compacts log data                                  |
| `compactor`          | Periodically compacts index files and deletes expired log data          |
| `AWS S3`             | Remote object storage backend for logs and indexes                      |

---

## ✅ Features

- Log collection using OpenTelemetry filelog receiver (DaemonSet)
- OTLP/HTTP exporter sending logs to Loki (via native protocol)
- Loki running in **SimpleScalable mode**
- AWS S3-backed TSDB storage for chunks and indexes
- Multi-tenant support via `X-Scope-OrgID` header
- Retention policy: logs automatically purged after `7 days`
- OTEL internal metrics exported via PodMonitor

---

## 🚀 Deployment Instructions

1. **Update Helm `values.yaml`**

Replace placeholders like:

```yaml
<s3 bucket name>
<s3-access-key>
<s3-secret-key>
```

2. **Deploy to Kubernetes**

```bash
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm install logs-stack ./path-to-chart -n observability --create-namespace
```

---

## 📦 S3 Bucket Structure

Loki will store files in S3 as follows:

```plaintext
s3://<bucket>/
  ├── dnvrdev/
  │   └── loki_index_*/       # TSDB index blocks
  ├── chunks/                 # TSDB chunk data (compressed)
  ├── ruler/                  # Rule storage (if enabled)
  └── admin/                  # Admin metadata
```

---

---

## 🧱 Low-Level System Design Architecture

### 1. **Log Collection Flow**

```plaintext
[ Kubernetes Pods ]
        │
        ▼
[ OTEL Collector (DaemonSet) ]
  └── filelog, k8sattributes
  └── Export: otlphttp/loki
```

### 2. **Loki Storage**

```plaintext
[ Loki Write ] ──> [ Ingester ] ──> [ S3: chunks, indexes ]
```

### 3. **Compactor**

- `compaction_interval: 10m`
- `retention_period: 168h`
- Compacts and purges logs > 7 days

### 4. **Query Flow**

```plaintext
[ Grafana ] ──> [ Querier ] ──> [ Backend ] ──> [ S3 ]
```

---

## 📊 Monitoring

- PodMonitor for OTEL Collector `:8888`
- Loki metrics via `serviceMonitor`
- Grafana Dashboards: Loki + OTEL + S3

---

## 🧼 Cleanup

```bash
helm uninstall logs-stack -n observability
```

---

## 📎 References

- https://grafana.com/docs/loki/latest/
- https://opentelemetry.io/docs/collector/
- https://github.com/open-telemetry/opentelemetry-helm-charts
- https://grafana.com/docs/loki/latest/operations/storage/
