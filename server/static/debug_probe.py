#!/usr/bin/env python3
"""
Sysmon Diagnostic Probe & Live Debugger
Sonda interattiva per la diagnosi completa a video di connettività, certificati SSL,
servizio locale, raccolta metriche e invio telemetria in tempo reale.
"""

from __future__ import annotations

import os
import sys
import time
import json
import socket
import ssl
import platform
import uuid
import datetime
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Optional, Tuple

# Forza encoding UTF-8 per console Windows cp1252
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Abilita colori ANSI su Windows Terminal / PowerShell
if os.name == "nt":
    os.system("")

# Costanti colori ANSI
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_GRAY = "\033[90m"

def print_header(title: str):
    print(f"\n{C_CYAN}{C_BOLD}{'=' * 65}")
    print(f"   {title}")
    print(f"{'=' * 65}{C_RESET}")

def print_step(step_num: str, title: str):
    print(f"\n{C_YELLOW}{C_BOLD}[{step_num}] {title}{C_RESET}")

def print_ok(msg: str):
    print(f"  {C_GREEN}[OK]{C_RESET} {msg}")

def print_warn(msg: str):
    print(f"  {C_YELLOW}[ATTENZIONE]{C_RESET} {msg}")

def print_err(msg: str):
    print(f"  {C_RED}[ERRORE]{C_RESET} {msg}")

def print_info(label: str, value: Any):
    print(f"  {C_GRAY}*{C_RESET} {C_BOLD}{label}:{C_RESET} {value}")


# -----------------------------------------------------------------------------
# 1. Rilevamento Configurazione Locale
# -----------------------------------------------------------------------------
def find_sysmon_installation() -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Cerca l'installazione locale di Sysmon e carica config.json se presente."""
    candidate_dirs = [
        os.path.dirname(os.path.abspath(__file__)),
        r"C:\Program Files\Sysmon",
        r"C:\Sysmon",
        "/opt/sysmon",
        "/etc/sysmon",
        os.path.expanduser("~/sysmon"),
    ]
    for d in candidate_dirs:
        cfg_path = os.path.join(d, "config.json")
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8-sig") as f:
                    cfg = json.load(f)
                return d, cfg
            except Exception as e:
                return d, None
    return None, None


# -----------------------------------------------------------------------------
# 2. Diagnostica di Rete a Basso Livello (DNS, TCP, TLS/SSL)
# -----------------------------------------------------------------------------
def check_dns(hostname: str) -> Optional[str]:
    """Verifica risoluzione DNS."""
    try:
        t0 = time.perf_counter()
        ip = socket.gethostbyname(hostname)
        elapsed = (time.perf_counter() - t0) * 1000
        print_ok(f"Risoluzione DNS riuscita: {C_BOLD}{hostname}{C_RESET} -> {C_CYAN}{ip}{C_RESET} ({elapsed:.1f} ms)")
        return ip
    except Exception as e:
        print_err(f"Risoluzione DNS fallita per '{hostname}': {e}")
        return None

def check_tcp(hostname: str, port: int = 443, timeout: float = 5.0) -> bool:
    """Verifica connessione TCP su porta specificata."""
    try:
        t0 = time.perf_counter()
        s = socket.create_connection((hostname, port), timeout=timeout)
        elapsed = (time.perf_counter() - t0) * 1000
        s.close()
        print_ok(f"Connessione TCP porta {port} stabilita con successo ({elapsed:.1f} ms)")
        return True
    except socket.timeout:
        print_err(f"Timeout connessione TCP verso {hostname}:{port} (> {timeout}s). Possibile blocco firewall.")
        return False
    except ConnectionRefusedError:
        print_err(f"Connessione rifiutata su {hostname}:{port}.")
        return False
    except Exception as e:
        print_err(f"Errore connessione TCP verso {hostname}:{port}: {e}")
        return False

def check_tls(hostname: str, port: int = 443, timeout: float = 5.0) -> bool:
    """Verifica handshake TLS/SSL e validità certificato."""
    context = ssl.create_default_context()
    try:
        t0 = time.perf_counter()
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                elapsed = (time.perf_counter() - t0) * 1000
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                version = ssock.version()
                
                subject = dict(x[0] for x in cert.get("subject", []))
                common_name = subject.get("commonName", "N/A")
                issuer = dict(x[0] for x in cert.get("issuer", []))
                issuer_cn = issuer.get("commonName", "N/A")
                not_after = cert.get("notAfter", "N/A")
                
                print_ok(f"Handshake TLS riuscito ({elapsed:.1f} ms)")
                print_info("Protocollo TLS", f"{version} ({cipher[0]})")
                print_info("Certificato Emesso Per", common_name)
                print_info("Autorità di Certificazione (CA)", issuer_cn)
                print_info("Scadenza Certificato", not_after)
                return True
    except ssl.SSLCertVerificationError as e:
        print_err(f"Validazione Certificato SSL fallita: {e}")
        print_warn("Rilevato possibile SSL inspection proxy (es. Zscaler, Fortinet) o orologio di sistema errato.")
        return False
    except Exception as e:
        print_err(f"Errore durante l'handshake TLS: {e}")
        return False


# -----------------------------------------------------------------------------
# 3. Raccolta Metriche (con psutil se disponibile, altrimenti fallback)
# -----------------------------------------------------------------------------
def get_system_snapshot(machine_id: str) -> Dict[str, Any]:
    """Raccoglie metriche del sistema in formato compatibile con il server Sysmon."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    hostname = socket.gethostname()

    has_psutil = False
    try:
        import psutil
        has_psutil = True
    except ImportError:
        pass

    if has_psutil:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.2)
        vmem = psutil.virtual_memory()
        uptime = time.time() - psutil.boot_time()
        
        # Dischi
        disk_partitions = []
        for p in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(p.mountpoint)
                disk_partitions.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": round(u.total / (1024**3), 2),
                    "used_gb": round(u.used / (1024**3), 2),
                    "free_gb": round(u.free / (1024**3), 2),
                    "percent": u.percent,
                })
            except Exception:
                pass
        
        # Rete
        net_io = psutil.net_io_counters()
        
        # Processi top
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                procs.append(p.info)
            except Exception:
                pass
        procs.sort(key=lambda x: (x.get('cpu_percent') or 0), reverse=True)
        top_procs = procs[:5]
        
        payload = {
            "metadata": {
                "agent_version": "2.0.0-debug",
                "machine_id": machine_id,
                "timestamp_utc": now_utc.isoformat(),
                "timestamp_epoch": time.time(),
                "tags": {"mode": "debug-probe"},
            },
            "system": {
                "hostname": hostname,
                "os": platform.system(),
                "os_release": platform.release(),
                "os_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "uptime_seconds": round(uptime, 1),
            },
            "cpu": {
                "percent_total": cpu_pct,
                "count_logical": psutil.cpu_count(logical=True),
                "count_physical": psutil.cpu_count(logical=False),
            },
            "memory": {
                "ram": {
                    "total_mb": round(vmem.total / (1024**2), 1),
                    "used_mb": round(vmem.used / (1024**2), 1),
                    "free_mb": round(vmem.available / (1024**2), 1),
                    "percent": vmem.percent,
                }
            },
            "disk": {
                "partitions": disk_partitions,
            },
            "network": {
                "io_total": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                }
            },
            "processes": {
                "count_total": len(procs),
                "top_cpu": top_procs,
            },
            "health": {
                "status": "healthy" if cpu_pct < 90 and vmem.percent < 90 else "warning",
                "alerts": [],
            }
        }
        return payload
    else:
        # Fallback base senza psutil
        payload = {
            "metadata": {
                "agent_version": "2.0.0-debug-fallback",
                "machine_id": machine_id,
                "timestamp_utc": now_utc.isoformat(),
                "timestamp_epoch": time.time(),
                "tags": {"mode": "debug-no-psutil"},
            },
            "system": {
                "hostname": hostname,
                "os": platform.system(),
                "os_release": platform.release(),
                "os_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "uptime_seconds": 0.0,
            },
            "cpu": {
                "percent_total": 0.0,
                "count_logical": os.cpu_count() or 1,
            },
            "memory": {
                "ram": {
                    "total_mb": 0.0,
                    "used_mb": 0.0,
                    "free_mb": 0.0,
                    "percent": 0.0,
                }
            },
            "disk": {"partitions": []},
            "network": {"io_total": {"bytes_sent": 0, "bytes_recv": 0}},
            "processes": {"count_total": 0, "top_cpu": []},
            "health": {"status": "healthy", "alerts": []}
        }
        return payload


# -----------------------------------------------------------------------------
# 4. Invio HTTP e Verifica
# -----------------------------------------------------------------------------
def send_metric_payload(url: str, payload: Dict[str, Any], api_key: Optional[str] = None) -> Tuple[bool, int, str, float]:
    """Invia payload HTTP POST con misurazione del tempo."""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "SysmonDebugProbe/2.0.0",
    }
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            elapsed = (time.perf_counter() - t0) * 1000
            body = resp.read().decode("utf-8")
            return True, resp.status, body, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - t0) * 1000
        body = e.read().decode("utf-8", errors="ignore")
        return False, e.code, body, elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return False, 0, str(e), elapsed


def verify_machine_on_server(server_base: str, machine_id: str) -> Optional[Dict[str, Any]]:
    """Interroga l'API /api/v1/machines per confermare se il server elenca questa macchina."""
    url = f"{server_base.rstrip('/')}/api/v1/machines"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status == 200:
                machines = json.loads(resp.read().decode("utf-8"))
                for m in machines:
                    if m.get("machine_id") == machine_id:
                        return m
    except Exception:
        pass
    return None


# -----------------------------------------------------------------------------
# 5. Ispezione del Servizio Locale e File di Log
# -----------------------------------------------------------------------------
def inspect_local_service(install_dir: Optional[str]):
    """Ispeziona lo stato del servizio Windows (Attività Pianificata) o Linux (systemd)."""
    if os.name == "nt":
        # Windows: controlla Attività Pianificata SysmonAgent
        try:
            import subprocess
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-ScheduledTask -TaskName SysmonAgent -ErrorAction SilentlyContinue | Select-Object TaskName, State, @{N='LastRun';E={(Get-ScheduledTaskInfo -TaskName $_.TaskName).LastRunTime}}, @{N='LastResult';E={(Get-ScheduledTaskInfo -TaskName $_.TaskName).LastTaskResult}} | Format-List"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            out = res.stdout.strip()
            if out:
                print_ok("Attivita' Pianificata 'SysmonAgent' rilevata nel sistema:")
                for line in out.splitlines():
                    if line.strip():
                        print(f"    {C_CYAN}{line.strip()}{C_RESET}")
            else:
                print_warn("Attivita' Pianificata 'SysmonAgent' NON registrata su questa macchina Windows!")
        except Exception as e:
            print_warn(f"Impossibile interrogare Task Scheduler: {e}")
    else:
        # Linux: controlla systemd sysmon.service
        try:
            import subprocess
            res = subprocess.run(["systemctl", "is-active", "sysmon"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            status = res.stdout.strip()
            if status == "active":
                print_ok(f"Servizio systemd 'sysmon': {C_GREEN}ATTIVO (in esecuzione){C_RESET}")
            else:
                print_warn(f"Servizio systemd 'sysmon': {status or 'NON ATTIVO'}")
        except Exception as e:
            print_warn(f"Impossibile verificare systemd: {e}")

    # Ispezione log locale
    if install_dir:
        log_file = os.path.join(install_dir, "sysmon.log")
        if os.path.isfile(log_file):
            print_info("File di Log locale trovato", log_file)
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as lf:
                    lines = lf.readlines()
                if lines:
                    last_lines = [l.rstrip() for l in lines[-10:] if l.strip()]
                    print(f"  {C_GRAY}--- Ultime righe di {log_file} ---{C_RESET}")
                    for l in last_lines:
                        col = C_RED if "ERROR" in l else (C_YELLOW if "WARN" in l else C_GRAY)
                        print(f"    {col}{l}{C_RESET}")
                    print(f"  {C_GRAY}------------------------------------{C_RESET}")
                else:
                    print_info("File di Log", "Presente ma vuoto (nessun evento scritto finora)")
            except Exception as e:
                print_warn(f"Impossibile leggere sysmon.log: {e}")


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    print_header("SYSMON TELEMETRY - SONDA DI DIAGNOSTICA INTERATTIVA")
    print(f"{C_GRAY}Questa sonda verifica ogni livello (ambiente, DNS, TCP, SSL, log, servizio, invio HTTP){C_RESET}")
    print(f"{C_GRAY}e mantiene una sessione attiva a video con l'esito di ogni pacchetto telemetrico.{C_RESET}")

    # 1. Info Ambiente
    print_step("1/6", "Identificazione Macchina Host e Interprete Python")
    node_id = hex(uuid.getnode())
    machine_id = f"{socket.gethostname()}-{node_id}"
    
    print_info("Hostname", socket.gethostname())
    print_info("Machine ID univoco", f"{C_BOLD}{machine_id}{C_RESET}")
    print_info("Sistema Operativo", f"{platform.system()} {platform.release()} ({platform.machine()})")
    print_info("Interprete Python", sys.executable)
    print_info("Versione Python", platform.python_version())
    in_venv = sys.prefix != sys.base_prefix
    print_info("Ambiente Virtuale (.venv)", f"{C_GREEN}SI (Attivo){C_RESET}" if in_venv else f"{C_YELLOW}NO (Python globale di sistema){C_RESET}")

    # 2. Ricerca installazione
    print_step("2/6", "Verifica Installazione e Stato Servizio Sysmon")
    install_dir, cfg = find_sysmon_installation()
    if install_dir:
        print_ok(f"Directory installazione Sysmon trovata: {C_CYAN}{install_dir}{C_RESET}")
    else:
        print_warn("Directory installazione standard non trovata (la sonda opererà in modalità standalone).")

    server_url = "https://simei.dsc-italy.app/api/v1/metrics"
    api_key = None
    if cfg:
        server_url = cfg.get("server_url", server_url)
        api_key = cfg.get("api_key")
        print_info("URL configurato in config.json", server_url)
    else:
        print_info("URL di default", server_url)

    inspect_local_service(install_dir)

    # 3. Diagnostica di Rete
    print_step("3/6", f"Test di Connettività verso il Server ({server_url})")
    parsed_url = urllib.parse.urlparse(server_url)
    target_host = parsed_url.hostname or "simei.dsc-italy.app"
    target_port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    server_base = f"{parsed_url.scheme}://{parsed_url.netloc}"

    print_info("Target Host", target_host)
    print_info("Target Port", target_port)

    # A. DNS
    ip = check_dns(target_host)
    if not ip:
        print_err("Impossibile procedere: il nome a dominio non viene risolto dal DNS locale.")
        return

    # B. TCP
    tcp_ok = check_tcp(target_host, target_port)
    if not tcp_ok:
        print_err(f"Impossibile raggiungere {target_host}:{target_port} via TCP. Verifica firewall aziendale o proxy.")
        return

    # C. TLS
    if parsed_url.scheme == "https":
        tls_ok = check_tls(target_host, target_port)
        if not tls_ok:
            print_warn("I certificati non possono essere validati. Potrebbe essere necessario impostare 'verify_ssl: false'.")

    # D. Health Check HTTP
    health_url = f"{server_base}/health"
    try:
        t0 = time.perf_counter()
        with urllib.request.urlopen(health_url, timeout=5.0) as resp:
            elapsed = (time.perf_counter() - t0) * 1000
            data = resp.read().decode("utf-8")
            print_ok(f"Endpoint salute server {health_url} raggiungibile -> HTTP {resp.status} ({elapsed:.1f} ms)")
            print_info("Risposta Server Health", data.strip())
    except Exception as e:
        print_warn(f"Chiamata a {health_url} non riuscita ({e}). Potrebbe richiedere autenticazione.")

    # 4. Raccolta Metriche
    print_step("4/6", "Campionamento Telemetria Locale")
    has_psutil = "psutil" in sys.modules or os.path.exists(os.path.join(sys.prefix, "lib"))
    try:
        import psutil
        print_ok(f"Libreria 'psutil' attiva (v{psutil.__version__})")
    except ImportError:
        print_warn("Libreria 'psutil' NON presente in questo ambiente Python! Verranno usate metriche di base.")
        if install_dir:
            venv_pip = os.path.join(install_dir, ".venv", "Scripts", "pip.exe")
            if os.path.isfile(venv_pip):
                print_info("Suggerimento", f"Esegui la sonda con l'interprete del venv: & '{install_dir}\\.venv\\Scripts\\python.exe' debug_probe.py")

    sample = get_system_snapshot(machine_id)
    print_ok(f"Snapshot generato con successo:")
    print_info("CPU rilevata", f"{sample['cpu']['percent_total']}% (Core logici: {sample['cpu'].get('count_logical', 1)})")
    ram = sample["memory"]["ram"]
    print_info("RAM rilevata", f"{ram['percent']}% ({ram['used_mb']} MB usati su {ram['total_mb']} MB)")
    print_info("Processi attivi", sample["processes"]["count_total"])

    # 5. Primo Invio Test
    print_step("5/6", f"Invio Telemetria di Test a {server_url}")
    success, code, body, elapsed = send_metric_payload(server_url, sample, api_key=api_key)
    if success and 200 <= code < 300:
        print_ok(f"Telemetria accettata dal server con codice {C_BOLD}HTTP {code}{C_RESET} ({elapsed:.1f} ms)!")
        print_info("Risposta dal server", body.strip())
        
        # Verifica se appare su /api/v1/machines
        m_info = verify_machine_on_server(server_base, machine_id)
        if m_info:
            print_ok(f"Macchina {C_BOLD}{machine_id}{C_RESET} confermata visibile e ONLINE nella lista server!")
            print_info("Ultimo contatto registrato", m_info.get("last_seen_at"))
        else:
            print_warn(f"Macchina archiviata, ma non ancora apparsa nella lista /api/v1/machines (potrebbe aggiornarsi a breve).")
    else:
        print_err(f"Invio fallito! Codice risposta: {C_BOLD}HTTP {code}{C_RESET} ({elapsed:.1f} ms)")
        print_err(f"Dettaglio risposta server: {body}")
        print_warn("Questa è la causa per cui la macchina non compare sul server!")

    # 6. Modalità Live Continua a Video
    if "--once" in sys.argv:
        print_step("6/6", "Modalita' singola (--once) completata.")
        return

    print_step("6/6", "Avvio Monitoraggio Live Continuo a Video")
    print(f"{C_CYAN}La sonda inviera' uno snapshot ogni 5 secondi mostrando i risultati in tempo reale.{C_RESET}")
    print(f"{C_GRAY}Premi {C_BOLD}CTRL+C{C_RESET}{C_GRAY} in qualsiasi momento per arrestare la sonda.{C_RESET}\n")

    count = 1
    try:
        while True:
            time.sleep(5)
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            payload = get_system_snapshot(machine_id)
            ok, status_code, resp_body, resp_ms = send_metric_payload(server_url, payload, api_key=api_key)
            
            cpu_val = payload["cpu"]["percent_total"]
            ram_val = payload["memory"]["ram"]["percent"]
            
            if ok and 200 <= status_code < 300:
                print(f"[{now_str}] {C_GREEN}[OK] Snapshot #{count:03d}{C_RESET} -> {C_BOLD}HTTP {status_code}{C_RESET} ({resp_ms:4.0f}ms) | {C_CYAN}CPU: {cpu_val:4.1f}%{C_RESET} | {C_CYAN}RAM: {ram_val:4.1f}%{C_RESET} | Host: {sample['system']['hostname']}")
            else:
                print(f"[{now_str}] {C_RED}[ERRORE] Snapshot #{count:03d} FALLITO{C_RESET} -> HTTP {status_code} ({resp_ms:4.0f}ms) | Dettaglio: {resp_body[:120]}")
            count += 1
    except KeyboardInterrupt:
        print(f"\n\n{C_YELLOW}Monitoraggio diagnostico interrotto dall'utente.{C_RESET}")
        print(f"{C_GREEN}Tutti i test completati.{C_RESET}\n")

if __name__ == "__main__":
    main()
