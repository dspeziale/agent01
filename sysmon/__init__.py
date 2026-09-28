"""
Pulsar - Sysmon Backwards Compatibility Wrapper
"""
try:
    from pulsar.collector import SystemMetricsCollector
    from pulsar.sender import MetricSender
    from pulsar.config import AgentConfig
    from pulsar.agent import MonitoringAgent
except ImportError:
    from .collector import SystemMetricsCollector
    from .sender import MetricSender
    from .config import AgentConfig
    from .agent import MonitoringAgent

__version__ = "2.0.0"
__all__ = [
    "SystemMetricsCollector",
    "MetricSender",
    "AgentConfig",
    "MonitoringAgent",
]
