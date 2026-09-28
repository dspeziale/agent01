"""
Modulo di persistenza dati su PostgreSQL per Sysmon Telemetry Server.
Gestisce il connection pool (psycopg), l'inizializzazione del database (DDL)
e le query di inserimento ed estrazione dei dati di telemetria.
"""

from __future__ import annotations

import os
import json
import logging
import datetime
from typing import Dict, Any, List, Optional
import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("sysmon.server.db")

SCHEMA_DDL = """
-- Tabella anagrafica delle macchine monitorate
CREATE TABLE IF NOT EXISTS machines (
    machine_id VARCHAR(128) PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    fqdn VARCHAR(255),
    os VARCHAR(64),
    os_release VARCHAR(64),
    os_version VARCHAR(128),
    architecture VARCHAR(64),
    processor TEXT,
    python_version VARCHAR(32),
    timezone VARCHAR(64),
    tags JSONB DEFAULT '{}'::jsonb,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tabella serie temporale degli snapshot di telemetria
CREATE TABLE IF NOT EXISTS telemetry_snapshots (
    id BIGSERIAL PRIMARY KEY,
    machine_id VARCHAR(128) NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    timestamp_epoch DOUBLE PRECISION NOT NULL,
    uptime_seconds DOUBLE PRECISION,
    health_status VARCHAR(32) DEFAULT 'healthy',
    health_alerts JSONB DEFAULT '[]'::jsonb,
    cpu_percent_total REAL,
    cpu_count_logical INT,
    cpu_count_physical INT,
    ram_percent REAL,
    ram_used_mb REAL,
    ram_total_mb REAL,
    swap_percent REAL,
    net_bytes_sent BIGINT,
    net_bytes_recv BIGINT,
    process_count INT,
    battery_percent REAL,
    battery_plugged BOOLEAN,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Dettaglio per partizione/disco associato allo snapshot
CREATE TABLE IF NOT EXISTS telemetry_disks (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    machine_id VARCHAR(128) NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    device TEXT,
    mountpoint TEXT,
    fstype VARCHAR(64),
    total_gb REAL,
    used_gb REAL,
    free_gb REAL,
    percent_used REAL
);

-- Dettaglio top processi attivi associati allo snapshot
CREATE TABLE IF NOT EXISTS telemetry_top_processes (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    machine_id VARCHAR(128) NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    pid INT,
    ppid INT,
    name TEXT,
    status VARCHAR(32),
    username TEXT,
    cpu_percent REAL,
    memory_percent REAL,
    memory_rss_mb REAL,
    threads INT
);

-- Indici per query analitiche ad alte prestazioni
CREATE INDEX IF NOT EXISTS idx_snapshots_machine_time ON telemetry_snapshots (machine_id, timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_time ON telemetry_snapshots (timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_health ON telemetry_snapshots (health_status);
CREATE INDEX IF NOT EXISTS idx_snapshots_raw_payload ON telemetry_snapshots USING GIN (raw_payload);
CREATE INDEX IF NOT EXISTS idx_disks_machine_time ON telemetry_disks (machine_id, timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_top_procs_machine_time ON telemetry_top_processes (machine_id, timestamp_utc DESC);
"""


class DatabaseManager:
    """Gestisce la connessione a PostgreSQL e le operazioni CRUD."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or self._build_dsn_from_env()

    @staticmethod
    def _build_dsn_from_env() -> str:
        """Costruisce il DSN di connessione partendo da DATABASE_URL o singole variabili d'ambiente."""
        if os.environ.get("DATABASE_URL"):
            return os.environ["DATABASE_URL"]

        user = os.environ.get("POSTGRES_USER", "postgres")
        password = os.environ.get("POSTGRES_PASSWORD", "postgres")
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        db = os.environ.get("POSTGRES_DB", "sysmon_db")

        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    def get_connection(self) -> psycopg.Connection:
        """Apre una connessione al database PostgreSQL."""
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def init_db(self) -> None:
        """Inizializza le tabelle e gli indici se non esistono."""
        logger.info("Verifica e inizializzazione schema PostgreSQL...")
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_DDL)
            conn.commit()
        logger.info("Schema PostgreSQL inizializzato con successo.")

    def check_health(self) -> bool:
        """Verifica che PostgreSQL sia raggiungibile ed eseguibile."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Controllo salute PostgreSQL fallito: {e}")
            return False

    def save_telemetry(self, payload: Dict[str, Any]) -> int:
        """
        Salva atomicamente uno snapshot completo di telemetria su PostgreSQL:
        1. Aggiorna l'anagrafica della macchina (machines)
        2. Inserisce lo snapshot con metriche aggregate e JSONB completo (telemetry_snapshots)
        3. Inserisce le partizioni disco (telemetry_disks)
        4. Inserisce i processi top (telemetry_top_processes)
        """
        metadata = payload.get("metadata", {})
        system = payload.get("system", {})
        cpu = payload.get("cpu", {})
        mem = payload.get("memory", {}).get("ram", {})
        swap = payload.get("memory", {}).get("swap", {})
        disk = payload.get("disk", {})
        net = payload.get("network", {})
        procs = payload.get("processes", {})
        health = payload.get("health", {})
        sensors = payload.get("sensors", {})
        battery = sensors.get("battery", {}) if sensors else {}

        machine_id = metadata.get("machine_id") or system.get("machine_id") or system.get("hostname", "unknown")
        hostname = system.get("hostname") or metadata.get("hostname", "unknown")

        timestamp_str = metadata.get("timestamp_utc") or datetime.datetime.now(datetime.timezone.utc).isoformat()
        timestamp_epoch = metadata.get("timestamp_epoch") or time.time()

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Upsert Anagrafica Macchina
                cur.execute(
                    """
                    INSERT INTO machines (
                        machine_id, hostname, fqdn, os, os_release, os_version,
                        architecture, processor, python_version, timezone, tags, last_seen_at
                    ) VALUES (
                        %(machine_id)s, %(hostname)s, %(fqdn)s, %(os)s, %(os_release)s, %(os_version)s,
                        %(architecture)s, %(processor)s, %(python_version)s, %(timezone)s, %(tags)s, NOW()
                    )
                    ON CONFLICT (machine_id) DO UPDATE SET
                        hostname = EXCLUDED.hostname,
                        fqdn = EXCLUDED.fqdn,
                        os = EXCLUDED.os,
                        os_release = EXCLUDED.os_release,
                        os_version = EXCLUDED.os_version,
                        architecture = EXCLUDED.architecture,
                        processor = EXCLUDED.processor,
                        python_version = EXCLUDED.python_version,
                        timezone = EXCLUDED.timezone,
                        tags = EXCLUDED.tags,
                        last_seen_at = NOW();
                    """,
                    {
                        "machine_id": machine_id,
                        "hostname": hostname,
                        "fqdn": system.get("fqdn"),
                        "os": system.get("os"),
                        "os_release": system.get("os_release"),
                        "os_version": system.get("os_version"),
                        "architecture": system.get("architecture"),
                        "processor": system.get("processor"),
                        "python_version": system.get("python_version"),
                        "timezone": system.get("timezone"),
                        "tags": json.dumps(metadata.get("tags", {})),
                    },
                )

                # 2. Inserimento Snapshot
                net_io = net.get("io_total", {})
                cur.execute(
                    """
                    INSERT INTO telemetry_snapshots (
                        machine_id, timestamp_utc, timestamp_epoch, uptime_seconds,
                        health_status, health_alerts, cpu_percent_total, cpu_count_logical,
                        cpu_count_physical, ram_percent, ram_used_mb, ram_total_mb,
                        swap_percent, net_bytes_sent, net_bytes_recv, process_count,
                        battery_percent, battery_plugged, raw_payload
                    ) VALUES (
                        %(machine_id)s, %(timestamp_utc)s, %(timestamp_epoch)s, %(uptime_seconds)s,
                        %(health_status)s, %(health_alerts)s, %(cpu_percent_total)s, %(cpu_count_logical)s,
                        %(cpu_count_physical)s, %(ram_percent)s, %(ram_used_mb)s, %(ram_total_mb)s,
                        %(swap_percent)s, %(net_bytes_sent)s, %(net_bytes_recv)s, %(process_count)s,
                        %(battery_percent)s, %(battery_plugged)s, %(raw_payload)s
                    ) RETURNING id;
                    """,
                    {
                        "machine_id": machine_id,
                        "timestamp_utc": timestamp_str,
                        "timestamp_epoch": timestamp_epoch,
                        "uptime_seconds": system.get("uptime_seconds"),
                        "health_status": health.get("status", "healthy"),
                        "health_alerts": json.dumps(health.get("alerts", [])),
                        "cpu_percent_total": cpu.get("percent_total"),
                        "cpu_count_logical": cpu.get("count_logical"),
                        "cpu_count_physical": cpu.get("count_physical"),
                        "ram_percent": mem.get("percent_used"),
                        "ram_used_mb": mem.get("used_mb"),
                        "ram_total_mb": mem.get("total_mb"),
                        "swap_percent": swap.get("percent_used"),
                        "net_bytes_sent": net_io.get("bytes_sent"),
                        "net_bytes_recv": net_io.get("bytes_recv"),
                        "process_count": procs.get("total_count"),
                        "battery_percent": battery.get("percent"),
                        "battery_plugged": battery.get("power_plugged"),
                        "raw_payload": json.dumps(payload),
                    },
                )
                snapshot_id = cur.fetchone()["id"]

                # 3. Inserimento partizioni dischi
                for part in disk.get("partitions", []):
                    cur.execute(
                        """
                        INSERT INTO telemetry_disks (
                            snapshot_id, machine_id, timestamp_utc, device, mountpoint,
                            fstype, total_gb, used_gb, free_gb, percent_used
                        ) VALUES (
                            %(snapshot_id)s, %(machine_id)s, %(timestamp_utc)s, %(device)s, %(mountpoint)s,
                            %(fstype)s, %(total_gb)s, %(used_gb)s, %(free_gb)s, %(percent_used)s
                        );
                        """,
                        {
                            "snapshot_id": snapshot_id,
                            "machine_id": machine_id,
                            "timestamp_utc": timestamp_str,
                            "device": part.get("device"),
                            "mountpoint": part.get("mountpoint"),
                            "fstype": part.get("fstype"),
                            "total_gb": part.get("total_gb"),
                            "used_gb": part.get("used_gb"),
                            "free_gb": part.get("free_gb"),
                            "percent_used": part.get("percent_used"),
                        },
                    )

                # 4. Inserimento top processi
                for p in procs.get("top_processes", []):
                    cur.execute(
                        """
                        INSERT INTO telemetry_top_processes (
                            snapshot_id, machine_id, timestamp_utc, pid, ppid,
                            name, status, username, cpu_percent, memory_percent,
                            memory_rss_mb, threads
                        ) VALUES (
                            %(snapshot_id)s, %(machine_id)s, %(timestamp_utc)s, %(pid)s, %(ppid)s,
                            %(name)s, %(status)s, %(username)s, %(cpu_percent)s, %(memory_percent)s,
                            %(memory_rss_mb)s, %(threads)s
                        );
                        """,
                        {
                            "snapshot_id": snapshot_id,
                            "machine_id": machine_id,
                            "timestamp_utc": timestamp_str,
                            "pid": p.get("pid"),
                            "ppid": p.get("ppid"),
                            "name": p.get("name"),
                            "status": p.get("status"),
                            "username": p.get("username"),
                            "cpu_percent": p.get("cpu_percent"),
                            "memory_percent": p.get("memory_percent"),
                            "memory_rss_mb": p.get("memory_rss_mb"),
                            "threads": p.get("threads"),
                        },
                    )

            conn.commit()

        logger.debug(f"Snapshot #{snapshot_id} salvato con successo per macchina {machine_id}")
        return snapshot_id

    def list_machines(self) -> List[Dict[str, Any]]:
        """Elenca tutte le macchine registrate con lo stato online/offline (soglia 2 minuti)."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        m.machine_id,
                        m.hostname,
                        m.os,
                        m.os_release,
                        m.architecture,
                        m.first_seen_at,
                        m.last_seen_at,
                        m.tags,
                        (m.last_seen_at >= NOW() - INTERVAL '2 minutes') AS is_online,
                        s.health_status,
                        s.cpu_percent_total,
                        s.ram_percent,
                        s.uptime_seconds
                    FROM machines m
                    LEFT JOIN LATERAL (
                        SELECT health_status, cpu_percent_total, ram_percent, uptime_seconds
                        FROM telemetry_snapshots
                        WHERE machine_id = m.machine_id
                        ORDER BY timestamp_utc DESC
                        LIMIT 1
                    ) s ON TRUE
                    ORDER BY m.last_seen_at DESC;
                    """
                )
                return cur.fetchall()

    def get_machine_history(self, machine_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Restituisce la serie storica delle metriche principali di una macchina per grafici/dashboard."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        id,
                        timestamp_utc,
                        timestamp_epoch,
                        uptime_seconds,
                        health_status,
                        cpu_percent_total,
                        ram_percent,
                        ram_used_mb,
                        ram_total_mb,
                        swap_percent,
                        net_bytes_sent,
                        net_bytes_recv,
                        process_count
                    FROM telemetry_snapshots
                    WHERE machine_id = %s
                    ORDER BY timestamp_utc DESC
                    LIMIT %s;
                    """,
                    (machine_id, limit),
                )
                return cur.fetchall()

    def get_latest_snapshot(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """Restituisce il JSONB completo dell'ultimo snapshot registrato per una data macchina."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT raw_payload, timestamp_utc
                    FROM telemetry_snapshots
                    WHERE machine_id = %s
                    ORDER BY timestamp_utc DESC
                    LIMIT 1;
                    """,
                    (machine_id,),
                )
                row = cur.fetchone()
                return row["raw_payload"] if row else None
