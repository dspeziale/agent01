"""
Test unitari per la suite Pulsar.
Verifica collector, configurazione, buffer SQLite offline e sender.
"""

import os
import unittest
import tempfile
import shutil

from pulsar.config import AgentConfig
from pulsar.collector import SystemMetricsCollector
from pulsar.storage import MetricOfflineBuffer
from pulsar.sender import MetricSender


class TestPulsarCollector(unittest.TestCase):
    def setUp(self):
        self.collector = SystemMetricsCollector(
            include_processes=True,
            top_processes_count=3,
            custom_tags={"env": "testing"},
        )

    def test_system_info(self):
        info = self.collector.get_system_info()
        self.assertIn("hostname", info)
        self.assertIn("os", info)
        self.assertIn("machine_id", info)
        self.assertGreaterEqual(info["uptime_seconds"], 0)

    def test_cpu_metrics(self):
        cpu = self.collector.get_cpu_metrics()
        self.assertIn("percent_total", cpu)
        self.assertIn("count_logical", cpu)
        self.assertGreater(cpu["count_logical"], 0)
        self.assertIsInstance(cpu["percent_per_core"], list)

    def test_memory_metrics(self):
        mem = self.collector.get_memory_metrics()
        self.assertIn("ram", mem)
        self.assertIn("swap", mem)
        self.assertGreater(mem["ram"]["total_bytes"], 0)
        self.assertGreaterEqual(mem["ram"]["percent_used"], 0.0)

    def test_disk_metrics(self):
        disk = self.collector.get_disk_metrics()
        self.assertIn("partitions", disk)
        self.assertIsInstance(disk["partitions"], list)

    def test_network_metrics(self):
        net = self.collector.get_network_metrics()
        self.assertIn("io", net)
        self.assertIn("interfaces", net)

    def test_process_metrics(self):
        procs = self.collector.get_process_metrics()
        self.assertIn("total_count", procs)
        self.assertIn("top_processes", procs)
        self.assertLessEqual(len(procs["top_processes"]), 3)

    def test_full_collection(self):
        snapshot = self.collector.collect()
        expected_keys = {"metadata", "health", "system", "cpu", "memory", "disk", "network", "processes"}
        self.assertTrue(expected_keys.issubset(snapshot.keys()))
        self.assertEqual(snapshot["metadata"]["tags"]["env"], "testing")
        self.assertIn("status", snapshot["health"])


class TestPulsarConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = AgentConfig()
        self.assertEqual(cfg.server_url, "https://localhost:8443/api/v1/metrics")
        self.assertEqual(cfg.interval_seconds, 10.0)
        self.assertTrue(cfg.offline_buffer_enabled)
        self.assertEqual(cfg.offline_buffer_db_path, "pulsar_buffer.db")

    def test_env_override(self):
        os.environ["PULSAR_SERVER_URL"] = "https://custom.pulsar.local/metrics"
        os.environ["PULSAR_INTERVAL"] = "5.5"
        try:
            cfg = AgentConfig.load()
            self.assertEqual(cfg.server_url, "https://custom.pulsar.local/metrics")
            self.assertEqual(cfg.interval_seconds, 5.5)
        finally:
            os.environ.pop("PULSAR_SERVER_URL", None)
            os.environ.pop("PULSAR_INTERVAL", None)


class TestPulsarStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_pulsar_buffer.db")
        self.buffer = MetricOfflineBuffer(db_path=self.db_path, max_records=5)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_enqueue_and_dequeue(self):
        payload1 = {"id": 1, "data": "metric_1"}
        payload2 = {"id": 2, "data": "metric_2"}

        self.buffer.push(payload1)
        self.buffer.push(payload2)

        self.assertEqual(self.buffer.count(), 2)

        records = self.buffer.pop_batch(limit=10)
        self.assertEqual(len(records), 2)
        row_id_1, payload_1 = records[0]
        self.assertEqual(payload_1["id"], 1)

        self.buffer.delete_batch([row_id_1])
        self.assertEqual(self.buffer.count(), 1)


if __name__ == "__main__":
    unittest.main()
