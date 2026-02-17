# minio-anomaly-detector
## 📊 **Complete Answer: How Anomaly Detection Works**

Your system detects anomalies using **2 statistical methods**:

---

## 🔬 **Method 1: Z-Score (Primary)**

Measures how far current value is from 24-hour average:

`Z = (Current Value - Average) / Standard Deviation

If Z > 2.5 → ANOMALY! 🚨`

**Example:**

`Normal Request Rate (24h): 100 ± 20 req/s
Current: 180 req/s

Z = (180 - 100) / 20 = 4.0σ
4.0 > 2.5 threshold → ALERT!`

---

## ⚡ **Method 2: Rate of Change (Secondary)**

Detects sudden spikes/drops:

`% Change = (Current - Avg of Last 10) / (Avg of Last 10) × 100

If % Change > 100% → ANOMALY! 🚨`

**Example:**

`Average of last 10: 100 req/s
Current: 250 req/s

% Change = (250 - 100) / 100 = 150%
150% > 100% threshold → ALERT!`

---

## 📈 **What Gets Monitored**

| Metric | Checks Every | Baseline | Alerts When |
| --- | --- | --- | --- |
| **Free Disk** | 60s | 24h average | Drops <2.5σ |
| **Request Rate** | 60s | 24h average | Spikes >2.0σ or >100% change |
| **Network Send** | 60s | 24h average | Deviates >2.5σ |
| **Network Receive** | 60s | 24h average | Deviates >2.5σ |
| **Error Rate** | 60s | 24h average | Jumps >2.0σ |

---

## ⏱️ **Timeline to First Alert**

`Hour 0-24:     Building baseline (NO ALERTS - learning phase)
Hour 24+:      ✅ Baseline complete, detection active
Hour 24-25:    🚨 First alerts possible when anomalies detected`

---

## 🎯 **Real-World Examples**

### Will Alert? ✅

- Free disk drops from 150GB to 20GB
- Request rate jumps from 100 to 300 req/s
- Network bandwidth 10x normal
- Error rate suddenly spikes 5x

### Won't Alert? ✓

- Free disk: 150GB → 145GB (normal fluctuation)
- Requests: 100 → 110 req/s (small increase)
- Error rate: 0.5 → 0.6 errors/s (normal)
- Network: 50 → 55 MB/s (within variance)

---

## 🎚️ **Current Sensitivity**

python

`ZSCORE_THRESHOLD = 2.5  # 98.7% confidence

Interpretation:
- Only 1 in 200 normal values trigger false alarm
- Balanced: catches real issues, minimizes false positives`

**Adjust sensitivity:**

python

`# More strict (fewer alerts):
ZSCORE_THRESHOLD = 3.0  # 99.9% confidence

# More sensitive (more alerts):
ZSCORE_THRESHOLD = 2.0  # 95% confidence
```

---

## 🚦 **Alert Cooldown**

Prevents Discord spam from same metric:
```
11:10 → Alert sent
11:11-11:14 → Cooldown active (no new alert even if still anomalous)
11:15 → Cooldown expires, can alert again`

Default: **5 minutes** (can change with `ALERT_COOLDOWN`)

---

## 🧪 **How to Test Detection**

**Step 1: Wait 24 hours** (or manually trigger spike)

**Step 2: Generate traffic spike**

bash

`mc cp /path/to/large/file minio/mybucket/`

**Step 3: Check Prometheus**

bash

`curl "http://<prometheus-host-ip>:9090/api/v1/query?query=rate(minio_gateway_requests_total[5m])"`

**Step 4: Wait 60 seconds** (check interval)

**Step 5: See Discord alert** with:

- Metric name
- Current value
- Expected range
- AI-generated insight

---

## 📋 **Quick Summary**

| Aspect | Details |
| --- | --- |
| **Detection Method** | Z-Score (statistical deviation) |
| **Data Window** | Last 24 hours (baseline) |
| **Check Frequency** | Every 60 seconds |
| **Alert Threshold** | >2.5σ deviation (98.7% confidence) |
| **Cooldown** | 5 minutes per metric (prevent spam) |
| **Metrics** | 5 (disk, requests, network, errors) |
| **First Alerts** | After 24 hours baseline established |

---

## 🎉 **Your System Is Ready!**

Once 24 hours pass:
✅ Automatically detects traffic anomalies
✅ Sends Discord alerts with AI insights
✅ No manual configuration needed
✅ Runs 24/7 monitoring

**Check back in 24 hours to see alerts start flowing!** 🚀
