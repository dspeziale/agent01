# Sysmon - Agente di Monitoraggio Sistema (Python HTTPS)

**Sysmon** è un modulo Python progettato per essere eseguito direttamente sulla macchina da monitorare. Raccoglie in tempo reale le metriche prestazionali e di stato del computer (CPU, RAM, Dischi, Schede di rete, Processi, Sensori, Uptime) e le trasmette in modo sicuro a un server remoto tramite **HTTPS** (POST con payload JSON e autenticazione).

---

## Caratteristiche Principali

1. **Raccolta Metriche Estesa & Telemetria Avanzata (Cross-Platform)**:
   - **Sistema**: Hostname, FQDN, Sistema Operativo, Release/Edizione, Architettura, Kernel, Uptime, Timezone, Utenti attivi loggati (`active_users`), Machine ID persistente.
   - **Salute & Alerting**: Valutazione automatica dello stato generale (`healthy`, `warning`, `critical`) con rilevamento delle soglie d'allarme per CPU, RAM e spazio dischi.
   - **CPU**: Utilizzo percentuale totale, per singolo core logico, conteggio core fisici e logici, frequenza min/max/attuale (MHz), ripartizione tempi (`user`, `system`, `idle`, `iowait`, `interrupt`, `dpc`), statistiche di context-switch, interrupt e chiamate di sistema.
   - **Memoria**: RAM fisica (totale, usata, libera, disponibile, %, attiva, inattiva, buffer, cached, slab) e Swap (totale, usata, libera, %, pagine scambiate in/out).
   - **Dischi**: Tutte le partizioni montate (GB totali, liberi, usati, %) e contatori I/O sia **globali** che **per ogni singola unità fisica** (letture/scritture in MB e tempi di latenza).
   - **Rete**: Traffico globale (MB inviati/ricevuti, pacchetti, errori/drop), traffico **per singola interfaccia di rete** (`io_per_interface`), dettaglio schede (IPv4, IPv6, MAC, MTU, duplex, velocità link) e **sommario delle connessioni di rete aperte per stato** (`ESTABLISHED`, `LISTEN`, `TIME_WAIT`, `CLOSE_WAIT`, ecc.).
   - **Processi**: Numero totale processi attivi, ripartizione per stato (`running`, `sleeping`, `stopped`) e classifica approfondita dei top processi con PID, PPID, nome, utente, thread, data avvio, consumo CPU %, memoria % e memoria residente **RSS/VMS in MB**.
   - **Sensori**: Batteria (percentuale, stato cavo alimentazione, tempo residuo), ventole e sensori di temperatura.

2. **Backend Definitivo su Coolify con Database PostgreSQL**:
   - Server di produzione basato su **FastAPI** e **Uvicorn** ad altissime prestazioni.
   - Persistenza automatica su **PostgreSQL 16**: salva l'anagrafica delle macchine, le serie storiche aggregate e l'intero payload dettagliato in colonna `raw_payload JSONB` indicizzata con indici GIN e B-Tree.
   - Pronto al deployment su **Coolify** con un click tramite `docker-compose.yml` e `server/Dockerfile` (con certificati SSL Let's Encrypt automatici e health check integrato).
   - Documentazione API interattiva automatica **Swagger UI** disponibile su `/docs`.

3. **Buffer Offline Locale (Zero Perdita Dati)**:
   - Se la connessione di rete o il server non sono raggiungibili, le metriche vengono salvate in un database locale SQLite (`sysmon_buffer.db`).
   - Al ripristino della connettività, tutti i record accumulati vengono trasmessi automaticamente in ordine cronologico (*drain* automatico).

---

## Struttura del Progetto

```text
agent01/
├── sysmon/
│   ├── __init__.py           # Esportazioni principali del pacchetto
│   ├── collector.py          # Raccolta telemetria avanzata hardware e OS (psutil)
│   ├── sender.py             # Trasmissione HTTPS con retry e gestione sessione
│   ├── storage.py            # Coda buffer SQLite per funzionamento offline
│   ├── config.py             # Parser configurazione (JSON, Env vars, CLI)
│   ├── agent.py              # Orchestratore, loop temporizzato e gestione segnali
│   └── __main__.py           # Entrypoint eseguibile con python -m sysmon
├── server/                   # Backend Definitivo su Coolify (FastAPI + PostgreSQL)
│   ├── __init__.py
│   ├── main.py               # API REST FastAPI (/api/v1/metrics, /machines, /health, /docs)
│   ├── db.py                 # Connessione PostgreSQL, DDL tabelle, indici e query
│   ├── Dockerfile            # Immagine Docker di produzione per Coolify
│   └── requirements.txt      # Dipendenze backend (FastAPI, Uvicorn, psycopg)
├── docker-compose.yml        # Stack completo Coolify (PostgreSQL 16 + Sysmon Server)
├── COOLIFY_DEPLOYMENT.md     # Guida passo-passo al deployment su Coolify
├── main.py                   # Script di avvio rapido client
├── sysmon.bat                # Launcher rapido client per Windows CMD
├── sysmon.ps1                # Launcher rapido client per Windows PowerShell
├── mock_server.py            # Server HTTPS locale di test per collaudo rapido
├── mock_server.bat           # Launcher rapido Mock Server per CMD
├── mock_server.ps1           # Launcher rapido Mock Server per PowerShell
├── config.example.json       # Template configurazione JSON
├── .env.example              # Template variabili d'ambiente
├── requirements.txt          # Dipendenze Python globali
├── requirements-agent.txt    # Dipendenze leggere per sole macchine client
└── tests/
    └── test_sysmon.py        # Test unitari completi
```

---

## Installazione e Avvio Rapido

### 1. Prerequisiti
- Python 3.9 o superiore.
- Creazione e attivazione del virtual environment:

```bash
# Su Windows:
python -m venv .venv
.venv\Scripts\activate

# Su Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Installazione delle dipendenze
```bash
pip install -r requirements.txt
```

---

## Modalità d'Uso

### A. Visualizzare le metriche locali (Senza invio)
Per testare la raccolta delle metriche sulla macchina locale:
```bash
python main.py --show-metrics
```

### B. Invio singolo (One-off)
Utile per script schedulati con cron o per verificare la connessione al server:
```bash
python main.py --once --url https://tuoserver.com/api/v1/metrics --token "IL_TUO_TOKEN"
```

### C. Esecuzione continua come Demone/Servizio
Campionamento e trasmissione continua (es. ogni 10 secondi):
```bash
python main.py --url https://tuoserver.com/api/v1/metrics --token "IL_TUO_TOKEN" --interval 10
```

### D. Esecuzione tramite file di configurazione
Crea un file `config.json` (copiando `config.example.json`):
```bash
python main.py --config config.json
```

### E. Esecuzione come modulo Python
```bash
python -m sysmon -u https://tuoserver.com/api/v1/metrics -t "IL_TUO_TOKEN"
```

---

## Test Locale con il Mock Server HTTPS

Nel progetto è incluso `mock_server.py`, un server HTTPS di test che genera automaticamente un certificato TLS autofirmato e riceve le metriche sulla porta `8443`.

1. **Terminale 1 (Avvio del Server HTTPS di test)**:
   ```cmd
   .\mock_server.bat
   ```
   *(oppure: `python mock_server.py --port 8443`)*

2. **Terminale 2 (Avvio dell'Agente Sysmon)**:
   ```cmd
   .\sysmon.bat
   ```
   *(oppure: `python main.py`)*

---

## Formato del Payload Trasmesso (JSON)

Esempio di payload inviato via HTTP POST:

```json
{
  "metadata": {
    "timestamp_utc": "2026-09-28T10:49:02.676883+00:00",
    "timestamp_epoch": 1790592542.67,
    "machine_id": "ISED-8088-DELL-0x90faa0001",
    "hostname": "ISED-8088-DELL",
    "tags": { "environment": "production" }
  },
  "system": {
    "hostname": "ISED-8088-DELL",
    "os": "Windows",
    "os_release": "11",
    "uptime_seconds": 953812.9,
    "uptime_human": "11 days, 0:56:52"
  },
  "cpu": {
    "percent_total": 24.5,
    "percent_per_core": [20.0, 30.0, 15.0, 35.0],
    "count_logical": 8,
    "count_physical": 4,
    "frequency_mhz": { "current": 2600.0, "max": 3200.0 }
  },
  "memory": {
    "ram": {
      "total_bytes": 17179869184,
      "total_mb": 16384.0,
      "used_bytes": 8589934592,
      "used_mb": 8192.0,
      "percent_used": 50.0
    },
    "swap": {
      "total_bytes": 4294967296,
      "percent_used": 12.0
    }
  },
  "disk": {
    "partitions": [
      {
        "device": "C:\\",
        "mountpoint": "C:\\",
        "fstype": "NTFS",
        "total_gb": 930.42,
        "used_gb": 223.43,
        "percent_used": 24.0
      }
    ],
    "io": {
      "read_mb": 459947.72,
      "write_mb": 431019.49
    }
  },
  "network": {
    "io": {
      "mb_sent": 6503.64,
      "mb_recv": 30616.97
    },
    "interfaces": [
      {
        "name": "Ethernet",
        "is_up": true,
        "speed_mbps": 1000,
        "mac_address": "FC-4C-EA-98-A1-EC",
        "ipv4": [{ "address": "10.20.10.40", "netmask": "255.255.255.0" }]
      }
    ]
  },
  "processes": {
    "total_count": 280,
    "top_processes": [
      {
        "pid": 1234,
        "name": "chrome.exe",
        "cpu_percent": 4.5,
        "memory_percent": 2.1,
        "status": "running"
      }
    ]
  },
  "sensors": {
    "battery": {
      "percent": 85,
      "power_plugged": true
    }
  }
}
```

---

## Integrazione nel proprio Codice Python

Il modulo può essere importato e utilizzato direttamente in altri progetti Python:

```python
from sysmon import SystemMetricsCollector, MetricSender, AgentConfig

# 1. Raccogliere solo le metriche
collector = SystemMetricsCollector()
metriche = collector.collect()
print(metriche["cpu"]["percent_total"])

# 2. Inviare metriche manualmente
config = AgentConfig(
    server_url="https://api.tuoserver.com/metrics",
    api_key="il_tuo_token",
    verify_ssl=True
)
sender = MetricSender(config)
sender.send(metriche)
sender.close()
```

---

## Esecuzione come Servizio in Background

### Windows (NSSM o Task Scheduler)
È possibile configurare lo script affinché parta all'avvio di Windows con l'Utilità di pianificazione (Task Scheduler) o creando un servizio di Windows con [NSSM](https://nssm.cc/):
```powershell
nssm install SysmonAgent "C:\JobArea\Personale\Codice\tests\agent01\.venv\Scripts\python.exe" "C:\JobArea\Personale\Codice\tests\agent01\main.py --config C:\JobArea\Personale\Codice\tests\agent01\config.json"
nssm start SysmonAgent
```

### Linux (Systemd Service)
Crea il file `/etc/systemd/system/sysmon.service`:
```ini
[Unit]
Description=Sysmon Agent - Monitoraggio Metriche di Sistema
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/agent01
ExecStart=/opt/agent01/.venv/bin/python main.py --config /opt/agent01/config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
Abilita e avvia:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sysmon.service
```
