"""
Test unitari per la suite Sysmon.
Verifica collector, configurazione, buffer SQLite offline e sender.
"""

import os
import unittest
import tempfile
import shutil

from sysmon.config import AgentConfig
from sysmon.collector import SystemMetricsCollector
from sysmon.storage import MetricOfflineBuffer
from sysmon.sender import MetricSender


class TestSysmonCollector(unittest.TestCase):
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

    def test_health_evaluation(self):
        # Simula condizione sana
        healthy_res = self.collector.evaluate_health_and_alerts(
            cpu_metrics={"percent_total": 20.0},
            mem_metrics={"ram": {"percent_used": 40.0}},
            disk_metrics={"partitions": [{"mountpoint": "C:\\", "percent_used": 50.0}]},
        )
        self.assertEqual(healthy_res["status"], "healthy")
        self.assertEqual(healthy_res["alerts_count"], 0)

        # Simula condizione critica
        critical_res = self.collector.evaluate_health_and_alerts(
            cpu_metrics={"percent_total": 95.0},
            mem_metrics={"ram": {"percent_used": 92.0}},
            disk_metrics={"partitions": [{"mountpoint": "C:\\", "percent_used": 95.0}]},
        )
        self.assertEqual(critical_res["status"], "critical")
        self.assertEqual(critical_res["alerts_count"], 3)


class TestOfflineBuffer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_buffer.db")
        self.buffer = MetricOfflineBuffer(db_path=self.db_path, max_records=5)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_push_and_count(self):
        self.assertEqual(self.buffer.count(), 0)
        self.buffer.push({"test": 1})
        self.buffer.push({"test": 2})
        self.assertEqual(self.buffer.count(), 2)

    def test_pop_and_delete(self):
        self.buffer.push({"metric_id": "alpha"})
        self.buffer.push({"metric_id": "beta"})

        records = self.buffer.pop_batch(limit=10)
        self.assertEqual(len(records), 2)
        row_id_1, payload_1 = records[0]
        self.assertEqual(payload_1["metric_id"], "alpha")

        self.buffer.delete_batch([row_id_1])
        self.assertEqual(self.buffer.count(), 1)

    def test_max_records_cap(self):
        for i in range(10):
            self.buffer.push({"index": i})
        self.assertLessEqual(self.buffer.count(), 5)


class TestConfig(unittest.TestCase):
    def test_config_defaults(self):
        cfg = AgentConfig()
        self.assertEqual(cfg.interval_seconds, 10.0)
        self.assertTrue(cfg.verify_ssl)

    def test_config_from_dict(self):
        data = {
            "server_url": "https://example.com/api",
            "interval_seconds": 30.0,
            "non_existent_key": 999,
        }
        cfg = AgentConfig.from_dict(data)
        self.assertEqual(cfg.server_url, "https://example.com/api")
        self.assertEqual(cfg.interval_seconds, 30.0)
        self.assertFalse(hasattr(cfg, "non_existent_key"))


if __name__ == "__main__":
    unittest.main()
