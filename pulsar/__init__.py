"""
Pulsar Telemetry Agent (pulsar)
Un modulo Python leggero ed estendibile per la raccolta delle metriche
di sistema e l'invio sicuro a un server remoto via HTTPS.
"""

from .collector import SystemMetricsCollector
from .sender import MetricSender
from .config import AgentConfig
from .agent import MonitoringAgent

__version__ = "1.0.0"
__all__ = [
    "SystemMetricsCollector",
    "MetricSender",
    "AgentConfig",
    "MonitoringAgent",
]
