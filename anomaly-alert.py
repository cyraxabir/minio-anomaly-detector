#!/usr/bin/env python3
"""
MinIO Traffic Anomaly Detection Service with OpenWebUI Integration
Monitors MinIO metrics from Prometheus and sends Discord alerts on anomalies
Uses OpenWebUI API for intelligent incident insights

CONFIGURATION: All settings hardcoded below - edit as needed
"""

import os
import time
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import numpy as np
from dataclasses import dataclass
import logging

# ============================================================================
# ⚙️  CONFIGURATION - EDIT THESE VALUES
# ============================================================================

# Discord Webhook URL - Get from Discord Server Settings > Integrations > Webhooks
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/*********"

# Prometheus Configuration
PROMETHEUS_URL = "http://host-ip:9090"
# Alternative: "http://10.0.0.50:9090" if Prometheus is on different host

# OpenWebUI Configuration (https://url)
OPENWEBUI_URL = "https://<localAI-url>"
OPENWEBUI_API_KEY = "<AI token key>"  # Get from OpenWebUI settings
OPENWEBUI_MODEL = "<model-name>"  # Options: llama2, neural-chat, mistral, openchat

# Service Configuration
CHECK_INTERVAL = 60  # Seconds between anomaly checks
ZSCORE_THRESHOLD = 2.5  # Lower = more alerts (1.5 very sensitive, 3.5 conservative)
ROC_THRESHOLD = 100  # Rate-of-change % to trigger alert
ALERT_COOLDOWN = 300  # 5 minutes - prevent same metric alerting repeatedly
HISTORY_HOURS = 24  # Historical window for baseline

# ============================================================================
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class AnomalyAlert:
    metric_name: str
    current_value: float
    expected_range: Tuple[float, float]
    severity: str  # 'low', 'medium', 'high'
    timestamp: str
    context: str = ""

class PrometheusConnector:
    """Query Prometheus for metrics"""
    
    def __init__(self, prometheus_url: str):
        self.url = prometheus_url.rstrip('/')
    
    def query_range(self, query: str, hours: int = 24) -> List[Dict]:
        """Query Prometheus with time range"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            params = {
                'query': query,
                'start': int(start_time.timestamp()),
                'end': int(end_time.timestamp()),
                'step': '60s'
            }
            
            response = requests.get(f"{self.url}/api/v1/query_range", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'success' and data['data']['result']:
                return data['data']['result']
            return []
        except Exception as e:
            logger.error(f"Prometheus query failed: {e}")
            return []
    
    def query_instant(self, query: str) -> float:
        """Get instant metric value"""
        try:
            params = {'query': query}
            response = requests.get(f"{self.url}/api/v1/query", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'success' and data['data']['result']:
                return float(data['data']['result'][0]['value'][1])
            return 0.0
        except Exception as e:
            logger.error(f"Instant query failed: {e}")
            return 0.0

class AnomalyDetector:
    """Detect anomalies in time series data"""
    
    @staticmethod
    def zscore_anomaly(values: List[float], threshold: float = 3.0) -> Tuple[bool, float, Tuple[float, float]]:
        """
        Detect anomaly using Z-score method
        Returns: (is_anomaly, zscore, (lower_bound, upper_bound))
        """
        if len(values) < 2:
            return False, 0.0, (0.0, 0.0)
        
        values = np.array(values)
        mean = np.mean(values)
        std = np.std(values)
        
        if std == 0:
            return False, 0.0, (mean, mean)
        
        current = values[-1]
        zscore = abs((current - mean) / std)
        lower = mean - (threshold * std)
        upper = mean + (threshold * std)
        
        is_anomaly = zscore > threshold
        return is_anomaly, zscore, (lower, upper)
    
    @staticmethod
    def rate_of_change_anomaly(values: List[float], threshold: float = 2.0) -> Tuple[bool, float]:
        """
        Detect sudden spikes/drops
        Returns: (is_anomaly, rate_of_change_percent)
        """
        if len(values) < 2:
            return False, 0.0
        
        values = np.array(values)
        recent = values[-10:] if len(values) >= 10 else values
        
        if recent[0] == 0:
            return False, 0.0
        
        rate_change = ((recent[-1] - recent[0]) / recent[0]) * 100
        is_anomaly = abs(rate_change) > threshold
        return is_anomaly, rate_change

class OpenWebUIInsight:
    """Generate insights using OpenWebUI API"""
    
    def __init__(self, base_url: str, api_key: str, model: str = "llama2"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout = 15
        logger.info(f"OpenWebUI initialized - URL: {self.base_url}, Model: {self.model}")
    
    def generate_context(self, metric_name: str, current: float, expected: float, 
                        change_percent: float) -> str:
        """Generate insight about anomaly using OpenWebUI API"""
        try:
            prompt = f"""Analyze this MinIO storage anomaly briefly (1-2 sentences max):

Metric: {metric_name}
Current value: {current:.2f}
Expected value: {expected:.2f}
Change: {change_percent:+.1f}%

Provide a brief technical explanation of what this could indicate for object storage operations."""
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "temperature": 0.7
            }
            
            response = requests.post(
                f"{self.base_url}/api/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                insight = result['choices'][0]['message']['content'].strip()
                return insight[:250] if insight else ""
            else:
                logger.warning(f"OpenWebUI API error: {response.status_code}")
                return ""
                
        except requests.Timeout:
            logger.warning(f"OpenWebUI request timeout")
            return ""
        except Exception as e:
            logger.warning(f"OpenWebUI insight generation failed: {e}")
            return ""

class DiscordNotifier:
    """Send alerts to Discord"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_alert(self, alert: AnomalyAlert, insight: str = ""):
        """Send formatted alert to Discord"""
        try:
            colors = {
                'low': 0xFFA500,
                'medium': 0xFF6600,
                'high': 0xFF0000
            }
            
            embed = {
                "title": f"🚨 {alert.metric_name} Anomaly Detected",
                "color": colors.get(alert.severity, 0xFF0000),
                "fields": [
                    {
                        "name": "Severity",
                        "value": alert.severity.upper(),
                        "inline": True
                    },
                    {
                        "name": "Current Value",
                        "value": f"`{alert.current_value:.2f}`",
                        "inline": True
                    },
                    {
                        "name": "Expected Range",
                        "value": f"`{alert.expected_range[0]:.2f} - {alert.expected_range[1]:.2f}`",
                        "inline": False
                    },
                    {
                        "name": "Timestamp",
                        "value": alert.timestamp,
                        "inline": False
                    }
                ],
                "footer": {"text": "MinIO Anomaly Detector"}
            }
            
            if alert.context or insight:
                embed["fields"].append({
                    "name": "Context/Insight",
                    "value": insight or alert.context,
                    "inline": False
                })
            
            payload = {"embeds": [embed]}
            
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            logger.info(f"Alert sent to Discord: {alert.metric_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False

class MinIOAnomalyMonitor:
    """Main monitoring service"""
    
    def __init__(self, prometheus_url: str, discord_webhook: str, 
                 openwebui_url: str = None, openwebui_key: str = None,
                 openwebui_model: str = "llama2", check_interval: int = 60,
                 zscore_threshold: float = 2.5, roc_threshold: float = 100,
                 alert_cooldown: int = 300, history_hours: int = 24):
        
        self.prometheus = PrometheusConnector(prometheus_url)
        self.notifier = DiscordNotifier(discord_webhook)
        self.openwebui = None
        
        if openwebui_url and openwebui_key:
            self.openwebui = OpenWebUIInsight(openwebui_url, openwebui_key, openwebui_model)
        else:
            logger.info("OpenWebUI insight generation DISABLED")
        
        self.detector = AnomalyDetector()
        self.check_interval = check_interval
        self.zscore_threshold = zscore_threshold
        self.roc_threshold = roc_threshold
        self.alert_cooldown = alert_cooldown
        self.history_hours = history_hours
        self.alert_cooldown_dict = {}
        
        logger.info("MinIO Anomaly Monitor initialized")
    
    def get_metric_values(self, query: str) -> List[float]:
        """Fetch metric values from Prometheus"""
        results = self.prometheus.query_range(query, hours=self.history_hours)
        if not results:
            return []
        
        values = [float(v[1]) for v in results[0]['values']]
        return values
    
    def check_storage_space(self):
        """Monitor free disk space"""
        values = self.get_metric_values('minio_disk_storage_bytes_free')
        if not values:
            return None
        
        is_anomaly, zscore, expected_range = self.detector.zscore_anomaly(values, threshold=self.zscore_threshold)
        
        if is_anomaly and self._can_alert('storage_space'):
            current = values[-1]
            severity = 'high' if current < expected_range[0] * 0.5 else 'medium'
            
            alert = AnomalyAlert(
                metric_name="Disk Storage - Free Space",
                current_value=current / 1e9,
                expected_range=(expected_range[0] / 1e9, expected_range[1] / 1e9),
                severity=severity,
                timestamp=datetime.now().isoformat()
            )
            
            insight = ""
            if self.openwebui:
                insight = self.openwebui.generate_context(
                    "minio_disk_storage_bytes_free",
                    current / 1e9,
                    np.mean(values) / 1e9,
                    ((current - np.mean(values)) / np.mean(values)) * 100
                )
            
            self.notifier.send_alert(alert, insight)
            self._record_alert('storage_space')
    
    def check_request_rate(self):
        """Monitor request rate anomalies"""
        values = self.get_metric_values('rate(minio_gateway_requests_total[5m])')
        if not values:
            return None
        
        is_roc_anomaly, roc = self.detector.rate_of_change_anomaly(values, threshold=self.roc_threshold)
        is_zscore_anomaly, zscore, expected = self.detector.zscore_anomaly(values, threshold=2.0)
        
        if (is_roc_anomaly or is_zscore_anomaly) and self._can_alert('request_rate'):
            current = values[-1]
            severity = 'high' if abs(roc) > 200 else 'medium'
            
            alert = AnomalyAlert(
                metric_name="Request Rate (requests/sec)",
                current_value=current,
                expected_range=expected,
                severity=severity,
                context=f"Rate of change: {roc:+.1f}%",
                timestamp=datetime.now().isoformat()
            )
            
            insight = ""
            if self.openwebui:
                insight = self.openwebui.generate_context(
                    "minio_gateway_requests_total",
                    current,
                    np.mean(values),
                    roc
                )
            
            self.notifier.send_alert(alert, insight)
            self._record_alert('request_rate')
    
    def check_network_traffic(self):
        """Monitor network I/O anomalies"""
        send_values = self.get_metric_values('rate(minio_network_send_bytes_total[5m])')
        recv_values = self.get_metric_values('rate(minio_network_receive_bytes_total[5m])')
        
        if not send_values or not recv_values:
            return None
        
        for name, values in [("Network Send", send_values), ("Network Receive", recv_values)]:
            is_anomaly, zscore, expected = self.detector.zscore_anomaly(values, threshold=self.zscore_threshold)
            
            if is_anomaly and self._can_alert(name.lower().replace(' ', '_')):
                current = values[-1]
                severity = 'high' if zscore > 4 else 'medium'
                
                alert = AnomalyAlert(
                    metric_name=f"{name} (bytes/sec)",
                    current_value=current / 1e6,
                    expected_range=(expected[0] / 1e6, expected[1] / 1e6),
                    severity=severity,
                    timestamp=datetime.now().isoformat()
                )
                
                self.notifier.send_alert(alert)
                self._record_alert(name.lower().replace(' ', '_'))
    
    def check_error_rate(self):
        """Monitor error rate anomalies"""
        values = self.get_metric_values('rate(minio_gateway_requests_total{status=~"5.."}[5m])')
        if not values:
            return None
        
        is_anomaly, zscore, expected = self.detector.zscore_anomaly(values, threshold=2.0)
        
        if is_anomaly and self._can_alert('error_rate'):
            current = values[-1]
            severity = 'high' if current > expected[1] * 2 else 'medium'
            
            alert = AnomalyAlert(
                metric_name="Error Rate (5xx errors/sec)",
                current_value=current,
                expected_range=expected,
                severity=severity,
                timestamp=datetime.now().isoformat()
            )
            
            insight = ""
            if self.openwebui:
                insight = self.openwebui.generate_context(
                    "minio_gateway_requests_errors",
                    current,
                    np.mean(values),
                    ((current - np.mean(values)) / np.mean(values)) * 100 if np.mean(values) > 0 else 0
                )
            
            self.notifier.send_alert(alert, insight)
            self._record_alert('error_rate')
    
    def _can_alert(self, alert_key: str) -> bool:
        """Check if enough time has passed since last alert"""
        last_alert = self.alert_cooldown_dict.get(alert_key, 0)
        return (time.time() - last_alert) > self.alert_cooldown
    
    def _record_alert(self, alert_key: str):
        """Record alert timestamp to prevent spam"""
        self.alert_cooldown_dict[alert_key] = time.time()
    
    def run(self):
        """Main loop"""
        logger.info(f"Starting monitoring loop (check every {self.check_interval}s)")
        
        try:
            while True:
                logger.info("Running anomaly checks...")
                self.check_storage_space()
                self.check_request_rate()
                self.check_network_traffic()
                self.check_error_rate()
                
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(self.check_interval)

if __name__ == "__main__":
    # Validate configuration
    if "YOUR_WEBHOOK" in DISCORD_WEBHOOK or not DISCORD_WEBHOOK.startswith("http"):
        logger.error("❌ DISCORD_WEBHOOK not configured! Edit the script at the top.")
        exit(1)
    
    if "sk-" not in OPENWEBUI_API_KEY or "YOUR_" in OPENWEBUI_API_KEY:
        logger.warning("⚠️  OPENWEBUI_API_KEY not configured. Alerts will work without AI insights.")
        use_openwebui = False
    else:
        use_openwebui = True
    
    logger.info("=" * 80)
    logger.info("MinIO Anomaly Detection Service - Starting")
    logger.info("=" * 80)
    logger.info(f"Prometheus: {PROMETHEUS_URL}")
    logger.info(f"Discord Webhook: {DISCORD_WEBHOOK[:50]}...")
    if use_openwebui:
        logger.info(f"OpenWebUI: {OPENWEBUI_URL} (Model: {OPENWEBUI_MODEL})")
    else:
        logger.info("OpenWebUI: DISABLED")
    logger.info(f"Check Interval: {CHECK_INTERVAL}s")
    logger.info(f"Z-Score Threshold: {ZSCORE_THRESHOLD}σ")
    logger.info(f"Alert Cooldown: {ALERT_COOLDOWN}s")
    logger.info("=" * 80)
    
    monitor = MinIOAnomalyMonitor(
        prometheus_url=PROMETHEUS_URL,
        discord_webhook=DISCORD_WEBHOOK,
        openwebui_url=OPENWEBUI_URL if use_openwebui else None,
        openwebui_key=OPENWEBUI_API_KEY if use_openwebui else None,
        openwebui_model=OPENWEBUI_MODEL,
        check_interval=CHECK_INTERVAL,
        zscore_threshold=ZSCORE_THRESHOLD,
        roc_threshold=ROC_THRESHOLD,
        alert_cooldown=ALERT_COOLDOWN,
        history_hours=HISTORY_HOURS
    )
    
    monitor.run()
