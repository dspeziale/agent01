"""
Modulo per la raccolta estesa e dettagliata delle metriche hardware e di sistema.
Raccoglie telemetria approfondita su CPU, RAM, Swap, Dischi (per-disco e per-partizione),
Rete (globale, per-interfaccia e stato connessioni), Processi (classifica e breakdown stati),
Sensori, Utenti attivi e calcolo automatico dello stato di salute (Health/Alerts).
"""

from __future__ import annotations

import os
import time
import socket
import platform
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional
import psutil

logger = logging.getLogger("sysmon.collector")


class SystemMetricsCollector:
    """Raccoglie metriche e telemetria avanzata sulla macchina host."""

    def __init__(
        self,
        include_processes: bool = True,
        top_processes_count: int = 10,
        include_disk_io: bool = True,
        include_net_io: bool = True,
        include_network_interfaces: bool = True,
        include_connections_summary: bool = True,
        custom_tags: Optional[Dict[str, str]] = None,
    ):
        self.include_processes = include_processes
        self.top_processes_count = top_processes_count
        self.include_disk_io = include_disk_io
        self.include_net_io = include_net_io
        self.include_network_interfaces = include_network_interfaces
        self.include_connections_summary = include_connections_summary
        self.custom_tags = custom_tags or {}

        # Machine ID persistente
        self._machine_id = self._generate_machine_id()

        # Inizializzazione prima chiamata cpu_times e cpu_percent per calcolo differenziali
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(interval=None, percpu=True)
            psutil.cpu_times_percent(interval=None)
        except Exception:
            pass

    def _generate_machine_id(self) -> str:
        """Restituisce un ID univoco e stabile della macchina."""
        try:
            node_id = hex(uuid.getnode())
            return f"{socket.gethostname()}-{node_id}"
        except Exception:
            return socket.gethostname()

    def get_system_info(self) -> Dict[str, Any]:
        """Restituisce anagrafica di sistema, timezone, release OS e utenti attivi."""
        boot_timestamp = psutil.boot_time()
        uptime_seconds = max(0.0, time.time() - boot_timestamp)

        # Rilevamento utenti attualmente connessi
        users_list: List[Dict[str, Any]] = []
        try:
            for u in psutil.users():
                started_iso = datetime.datetime.fromtimestamp(
                    u.started, tz=datetime.timezone.utc
                ).isoformat() if u.started else None
                users_list.append({
                    "name": u.name,
                    "terminal": u.terminal,
                    "host": u.host,
                    "started_utc": started_iso,
                })
        except Exception as e:
            logger.debug(f"Impossibile leggere utenti connessi: {e}")

        info = {
            "machine_id": self._machine_id,
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "timezone": time.tzname[0] if time.tzname else "UTC",
            "boot_time_utc": datetime.datetime.fromtimestamp(
                boot_timestamp, tz=datetime.timezone.utc
            ).isoformat(),
            "uptime_seconds": round(uptime_seconds, 2),
            "uptime_human": str(datetime.timedelta(seconds=int(uptime_seconds))),
            "active_users": users_list,
        }

        # Informazioni aggiuntive Windows o Linux
        if platform.system() == "Windows":
            try:
                info["win32_edition"] = platform.win32_edition()
            except Exception:
                pass

        return info

    def get_cpu_metrics(self) -> Dict[str, Any]:
        """Raccoglie percentuali totali, per-core, ripartizione tempi, frequenze e statistiche."""
        cpu_data: Dict[str, Any] = {
            "percent_total": psutil.cpu_percent(interval=None),
            "percent_per_core": psutil.cpu_percent(interval=None, percpu=True),
            "count_logical": psutil.cpu_count(logical=True),
            "count_physical": psutil.cpu_count(logical=False),
        }

        # Dettaglio ripartizione tempi CPU (user, system, idle, etc.)
        try:
            times = psutil.cpu_times_percent(interval=None)
            cpu_data["times_percent"] = {
                "user": getattr(times, "user", 0.0),
                "system": getattr(times, "system", 0.0),
                "idle": getattr(times, "idle", 0.0),
                "iowait": getattr(times, "iowait", None),
                "interrupt": getattr(times, "interrupt", getattr(times, "irq", None)),
                "dpc": getattr(times, "dpc", None),
            }
        except Exception as e:
            logger.debug(f"Impossibile leggere cpu_times_percent: {e}")

        # Frequenze CPU (globale e per core se supportato)
        try:
            freq = psutil.cpu_freq()
            if freq:
                cpu_data["frequency_mhz"] = {
                    "current": round(freq.current, 2) if freq.current else None,
                    "min": round(freq.min, 2) if freq.min else None,
                    "max": round(freq.max, 2) if freq.max else None,
                }
        except Exception as e:
            logger.debug(f"Impossibile leggere frequenza CPU: {e}")

        # Load average (Linux/macOS o emulazione)
        try:
            if hasattr(psutil, "getloadavg"):
                load1, load5, load15 = psutil.getloadavg()
                cpu_data["load_average"] = {
                    "1min": round(load1, 2),
                    "5min": round(load5, 2),
                    "15min": round(load15, 2),
                }
        except Exception as e:
            logger.debug(f"Load average non disponibile: {e}")

        # Statistiche context-switch, interrupt, chiamate di sistema
        try:
            stats = psutil.cpu_stats()
            cpu_data["stats"] = {
                "ctx_switches": stats.ctx_switches,
                "interrupts": stats.interrupts,
                "soft_interrupts": stats.soft_interrupts,
                "syscalls": stats.syscalls,
            }
        except Exception as e:
            logger.debug(f"Statistiche CPU non disponibili: {e}")

        return cpu_data

    def get_memory_metrics(self) -> Dict[str, Any]:
        """Raccoglie statistiche approfondite su RAM fisica e Swap."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        ram_data: Dict[str, Any] = {
            "total_bytes": mem.total,
            "total_mb": round(mem.total / (1024**2), 2),
            "available_bytes": mem.available,
            "available_mb": round(mem.available / (1024**2), 2),
            "used_bytes": mem.used,
            "used_mb": round(mem.used / (1024**2), 2),
            "free_bytes": mem.free,
            "free_mb": round(mem.free / (1024**2), 2),
            "percent_used": mem.percent,
        }

        # Campi Unix/Linux
        for extra_attr in ("active", "inactive", "buffers", "cached", "shared", "slab"):
            if hasattr(mem, extra_attr):
                val = getattr(mem, extra_attr)
                ram_data[f"{extra_attr}_mb"] = round(val / (1024**2), 2) if val is not None else None

        swap_data: Dict[str, Any] = {
            "total_bytes": swap.total,
            "total_mb": round(swap.total / (1024**2), 2),
            "used_bytes": swap.used,
            "used_mb": round(swap.used / (1024**2), 2),
            "free_bytes": swap.free,
            "free_mb": round(swap.free / (1024**2), 2),
            "percent_used": swap.percent,
            "sin_bytes": swap.sin,
            "sout_bytes": swap.sout,
        }

        return {"ram": ram_data, "swap": swap_data}

    def get_disk_metrics(self) -> Dict[str, Any]:
        """Raccoglie le partizioni montate, lo spazio disponibile e l'I/O per singolo disco fisico."""
        partitions_data: List[Dict[str, Any]] = []

        try:
            partitions = psutil.disk_partitions(all=False)
            for part in partitions:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions_data.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "opts": part.opts,
                        "total_bytes": usage.total,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_bytes": usage.used,
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_bytes": usage.free,
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent_used": usage.percent,
                    })
                except (PermissionError, OSError) as e:
                    logger.debug(f"Impossibile leggere disco {part.mountpoint}: {e}")
        except Exception as e:
            logger.warning(f"Errore lettura partizioni: {e}")

        disk_result: Dict[str, Any] = {"partitions": partitions_data}

        # Contatori I/O disco globale e per singolo disco fisico
        if self.include_disk_io:
            try:
                io_global = psutil.disk_io_counters(perdisk=False)
                if io_global:
                    total_data = {
                        "read_count": io_global.read_count,
                        "write_count": io_global.write_count,
                        "read_bytes": io_global.read_bytes,
                        "read_mb": round(io_global.read_bytes / (1024**2), 2),
                        "write_bytes": io_global.write_bytes,
                        "write_mb": round(io_global.write_bytes / (1024**2), 2),
                        "read_time_ms": io_global.read_time,
                        "write_time_ms": io_global.write_time,
                    }
                    disk_result["io_total"] = total_data
                    disk_result["io"] = total_data  # Alias compatibilità retroattiva

                # Dettaglio I/O per ogni unità fisica (C:, PhysicalDrive0, sda, nvme, ecc.)
                io_per_disk = psutil.disk_io_counters(perdisk=True)
                if io_per_disk:
                    per_disk_dict: Dict[str, Any] = {}
                    for disk_name, counters in io_per_disk.items():
                        per_disk_dict[disk_name] = {
                            "read_count": counters.read_count,
                            "write_count": counters.write_count,
                            "read_mb": round(counters.read_bytes / (1024**2), 2),
                            "write_mb": round(counters.write_bytes / (1024**2), 2),
                            "read_time_ms": counters.read_time,
                            "write_time_ms": counters.write_time,
                        }
                    disk_result["io_per_disk"] = per_disk_dict
            except Exception as e:
                logger.debug(f"Contatori disk I/O non disponibili: {e}")

        return disk_result

    def get_network_metrics(self) -> Dict[str, Any]:
        """Raccoglie statistiche di rete globali, per singola scheda e sommario connessioni aperte."""
        net_result: Dict[str, Any] = {}

        # Contatori globali traffico
        if self.include_net_io:
            try:
                net_io = psutil.net_io_counters(pernic=False)
                if net_io:
                    total_net = {
                        "bytes_sent": net_io.bytes_sent,
                        "mb_sent": round(net_io.bytes_sent / (1024**2), 2),
                        "bytes_recv": net_io.bytes_recv,
                        "mb_recv": round(net_io.bytes_recv / (1024**2), 2),
                        "packets_sent": net_io.packets_sent,
                        "packets_recv": net_io.packets_recv,
                        "errin": net_io.errin,
                        "errout": net_io.errout,
                        "dropin": net_io.dropin,
                        "dropout": net_io.dropout,
                    }
                    net_result["io_total"] = total_net
                    net_result["io"] = total_net  # Alias compatibilità retroattiva

                # Contatori per singola interfaccia di rete
                net_io_pernic = psutil.net_io_counters(pernic=True)
                if net_io_pernic:
                    pernic_dict: Dict[str, Any] = {}
                    for nic_name, counters in net_io_pernic.items():
                        pernic_dict[nic_name] = {
                            "bytes_sent": counters.bytes_sent,
                            "mb_sent": round(counters.bytes_sent / (1024**2), 2),
                            "bytes_recv": counters.bytes_recv,
                            "mb_recv": round(counters.bytes_recv / (1024**2), 2),
                            "packets_sent": counters.packets_sent,
                            "packets_recv": counters.packets_recv,
                            "errin": counters.errin,
                            "errout": counters.errout,
                        }
                    net_result["io_per_interface"] = pernic_dict
            except Exception as e:
                logger.debug(f"Contatori network I/O non disponibili: {e}")

        # Interfacce di rete e indirizzi IP
        if self.include_network_interfaces:
            interfaces_list: List[Dict[str, Any]] = []
            try:
                addrs = psutil.net_if_addrs()
                stats = psutil.net_if_stats()

                for iface_name, addr_list in addrs.items():
                    iface_stat = stats.get(iface_name)
                    ipv4_list = []
                    ipv6_list = []
                    mac_address = None

                    for addr in addr_list:
                        if addr.family == socket.AF_INET:
                            ipv4_list.append({
                                "address": addr.address,
                                "netmask": addr.netmask,
                                "broadcast": addr.broadcast,
                            })
                        elif hasattr(socket, "AF_INET6") and addr.family == socket.AF_INET6:
                            ipv6_list.append({
                                "address": addr.address,
                                "netmask": addr.netmask,
                            })
                        elif addr.family == psutil.AF_LINK:
                            mac_address = addr.address

                    interfaces_list.append({
                        "name": iface_name,
                        "is_up": iface_stat.isup if iface_stat else None,
                        "speed_mbps": iface_stat.speed if iface_stat else None,
                        "mtu": iface_stat.mtu if iface_stat else None,
                        "duplex": str(iface_stat.duplex) if iface_stat else None,
                        "mac_address": mac_address,
                        "ipv4": ipv4_list,
                        "ipv6": ipv6_list,
                    })
                net_result["interfaces"] = interfaces_list
            except Exception as e:
                logger.debug(f"Impossibile leggere interfacce di rete: {e}")

        # Sommario connessioni aperte per stato (ESTABLISHED, LISTEN, TIME_WAIT, ecc.)
        if self.include_connections_summary:
            try:
                conns = psutil.net_connections(kind="inet")
                conn_status_counts: Dict[str, int] = {}
                for c in conns:
                    st = c.status or "UNKNOWN"
                    conn_status_counts[st] = conn_status_counts.get(st, 0) + 1
                net_result["connections_summary"] = conn_status_counts
            except (psutil.AccessDenied, PermissionError):
                logger.debug("Permesso negato per lettura net_connections (richiede privilegi elevati)")
            except Exception as e:
                logger.debug(f"Errore lettura connessioni di rete: {e}")

        return net_result

    def get_process_metrics(self) -> Dict[str, Any]:
        """Raccoglie il totale dei processi, il conteggio per stato e la top list con memoria RSS/VMS."""
        process_result: Dict[str, Any] = {
            "total_count": 0,
            "status_counts": {},
            "top_processes": [],
        }

        if not self.include_processes:
            return process_result

        all_procs: List[Dict[str, Any]] = []
        status_counts: Dict[str, int] = {}

        try:
            attrs_to_fetch = [
                "pid", "ppid", "name", "status", "cpu_percent", "memory_percent",
                "memory_info", "username", "num_threads", "create_time"
            ]
            for p in psutil.process_iter(attrs=attrs_to_fetch):
                try:
                    info = p.info
                    st = info.get("status") or "unknown"
                    status_counts[st] = status_counts.get(st, 0) + 1
                    all_procs.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            process_result["total_count"] = len(all_procs)
            process_result["status_counts"] = status_counts

            if self.top_processes_count > 0:
                # Ordina per CPU% decrescente e poi RAM% decrescente
                sorted_procs = sorted(
                    all_procs,
                    key=lambda x: (x.get("cpu_percent") or 0.0, x.get("memory_percent") or 0.0),
                    reverse=True,
                )
                top = []
                for p in sorted_procs[: self.top_processes_count]:
                    mem_info = p.get("memory_info")
                    rss_mb = round(mem_info.rss / (1024**2), 2) if mem_info and hasattr(mem_info, "rss") else 0.0
                    vms_mb = round(mem_info.vms / (1024**2), 2) if mem_info and hasattr(mem_info, "vms") else 0.0

                    create_time = p.get("create_time")
                    create_time_iso = None
                    if create_time:
                        try:
                            create_time_iso = datetime.datetime.fromtimestamp(
                                create_time, tz=datetime.timezone.utc
                            ).isoformat()
                        except Exception:
                            pass

                    top.append({
                        "pid": p.get("pid"),
                        "ppid": p.get("ppid"),
                        "name": p.get("name"),
                        "status": p.get("status"),
                        "cpu_percent": round(p.get("cpu_percent") or 0.0, 1),
                        "memory_percent": round(p.get("memory_percent") or 0.0, 2),
                        "memory_rss_mb": rss_mb,
                        "memory_vms_mb": vms_mb,
                        "username": p.get("username"),
                        "threads": p.get("num_threads"),
                        "create_time_utc": create_time_iso,
                    })
                process_result["top_processes"] = top

        except Exception as e:
            logger.warning(f"Errore raccolta processi: {e}")

        return process_result

    def get_sensors_metrics(self) -> Dict[str, Any]:
        """Raccoglie sensori batteria, ventole e temperatura se supportati."""
        sensors: Dict[str, Any] = {}

        # Batteria
        try:
            battery = psutil.sensors_battery()
            if battery:
                sensors["battery"] = {
                    "percent": battery.percent,
                    "power_plugged": battery.power_plugged,
                    "secsleft": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
                }
        except Exception:
            pass

        # Temperature
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    sensor_temps = {}
                    for name, entries in temps.items():
                        sensor_temps[name] = [
                            {"label": e.label or name, "current": e.current, "high": e.high, "critical": e.critical}
                            for e in entries
                        ]
                    sensors["temperatures"] = sensor_temps
        except Exception:
            pass

        # Ventole (Linux)
        try:
            if hasattr(psutil, "sensors_fans"):
                fans = psutil.sensors_fans()
                if fans:
                    sensors["fans"] = {
                        name: [{"label": f.label, "current": f.current} for f in entries]
                        for name, entries in fans.items()
                    }
        except Exception:
            pass

        return sensors

    def evaluate_health_and_alerts(
        self,
        cpu_metrics: Dict[str, Any],
        mem_metrics: Dict[str, Any],
        disk_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Valuta lo stato di salute generale del sistema e segnala eventuali soglie critiche."""
        alerts: List[str] = []
        status = "healthy"

        # Controllo CPU
        cpu_pct = cpu_metrics.get("percent_total", 0.0)
        if cpu_pct >= 90.0:
            alerts.append(f"Utilizzo CPU critico ({cpu_pct}%)")
            status = "critical"
        elif cpu_pct >= 80.0:
            alerts.append(f"Utilizzo CPU elevato ({cpu_pct}%)")
            if status != "critical":
                status = "warning"

        # Controllo RAM
        ram_pct = mem_metrics.get("ram", {}).get("percent_used", 0.0)
        if ram_pct >= 90.0:
            alerts.append(f"Utilizzo RAM critico ({ram_pct}%)")
            status = "critical"
        elif ram_pct >= 80.0:
            alerts.append(f"Utilizzo RAM elevato ({ram_pct}%)")
            if status != "critical":
                status = "warning"

        # Controllo partizioni dischi
        for part in disk_metrics.get("partitions", []):
            d_pct = part.get("percent_used", 0.0)
            mp = part.get("mountpoint", "")
            if d_pct >= 90.0:
                alerts.append(f"Spazio su disco {mp} quasi esaurito ({d_pct}%)")
                status = "critical"
            elif d_pct >= 85.0:
                alerts.append(f"Spazio su disco {mp} elevato ({d_pct}%)")
                if status != "critical":
                    status = "warning"

        return {
            "status": status,
            "alerts_count": len(alerts),
            "alerts": alerts,
        }

    def collect(self) -> Dict[str, Any]:
        """
        Raccoglie un snapshot completo e approfondito di tutte le metriche della macchina.
        Restituisce un dizionario pronto per essere serializzato in JSON e salvato su PostgreSQL.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        system_info = self.get_system_info()
        cpu_info = self.get_cpu_metrics()
        mem_info = self.get_memory_metrics()
        disk_info = self.get_disk_metrics()
        net_info = self.get_network_metrics()
        proc_info = self.get_process_metrics()
        sensors_info = self.get_sensors_metrics()
        health_info = self.evaluate_health_and_alerts(cpu_info, mem_info, disk_info)

        snapshot: Dict[str, Any] = {
            "metadata": {
                "timestamp_utc": now_utc.isoformat(),
                "timestamp_epoch": now_utc.timestamp(),
                "machine_id": self._machine_id,
                "hostname": socket.gethostname(),
                "tags": self.custom_tags,
                "agent_version": "2.0.0",
            },
            "health": health_info,
            "system": system_info,
            "cpu": cpu_info,
            "memory": mem_info,
            "disk": disk_info,
            "network": net_info,
            "processes": proc_info,
        }

        if sensors_info:
            snapshot["sensors"] = sensors_info

        return snapshot
