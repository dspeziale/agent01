# Pulsar - Agente di Telemetria & Monitoraggio Sistema (Python HTTPS)

**Pulsar** (precedentemente *Sysmon*) è una piattaforma di telemetria e monitoraggio di sistema ad alte prestazioni. Raccoglie in tempo reale le metriche hardware, prestazionali e di stato del computer (CPU, RAM, Dischi, Schede di rete, Processi, Sensori, Uptime) e le trasmette in modo sicuro a un server remoto tramite **HTTPS** (POST con payload JSON e autenticazione).

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
   - Dashboard web moderna interattiva con dark mode e telemetria in tempo reale.
   - Documentazione API interattiva automatica **Swagger UI** disponibile su `/docs`.

3. **Buffer Offline Locale (Zero Perdita Dati)**:
   - Se la connessione di rete o il server non sono raggiungibili, le metriche vengono salvate in un database locale SQLite (`pulsar_buffer.db`).
   - Al ripristino della connettività, tutti i record accumulati vengono trasmessi automaticamente in ordine cronologico (*drain* automatico).

4. **Installazione Remota Istantanea (One-Liner)**:
   - **Windows** (PowerShell Admin): `irm https://simei.dsc-italy.app/install.ps1 | iex`
   - **Linux** (sudo sh): `curl -fsSL https://simei.dsc-italy.app/install.sh | sudo sh`
   - **Sonda di Debug interattiva a video**:
     - Windows: `irm https://simei.dsc-italy.app/debug.ps1 | iex`
     - Linux: `curl -fsSL https://simei.dsc-italy.app/debug.sh | sudo sh`

---

## Struttura del Progetto

```text
agent01/
├── pulsar/                   # Package primario Pulsar Agent
│   ├── __init__.py           # Esportazioni principali del pacchetto
│   ├── collector.py          # Raccolta telemetria avanzata hardware e OS (psutil)
│   ├── sender.py             # Trasmissione HTTPS con retry e gestione sessione
│   ├── storage.py            # Coda buffer SQLite per funzionamento offline
│   ├── config.py             # Parser configurazione (JSON, Env vars, CLI)
│   ├── agent.py              # Orchestratore, loop temporizzato e gestione segnali
│   └── __main__.py           # Entrypoint eseguibile con python -m pulsar
├── sysmon/                   # Alias di retrocompatibilità verso pulsar
│   ├── __init__.py
│   └── __main__.py
├── server/                   # Backend Definitivo su Coolify (FastAPI + PostgreSQL)
│   ├── __init__.py
│   ├── main.py               # API REST FastAPI (/api/v1/metrics, /machines, /health, /docs)
│   ├── db.py                 # Connessione PostgreSQL, DDL tabelle, indici e query
│   ├── Dockerfile            # Immagine Docker di produzione per Coolify
│   ├── requirements.txt      # Dipendenze backend (FastAPI, Uvicorn, psycopg)
│   └── static/               # Dashboard Web, script install.ps1, install.sh, debug.ps1
├── debug_probe.py            # Sonda interattiva standalone di diagnostica live a video
├── docker-compose.yml        # Stack completo Coolify (PostgreSQL 16 + Pulsar Server)
├── COOLIFY_DEPLOYMENT.md     # Guida passo-passo al deployment su Coolify
├── main.py                   # Script di avvio rapido client
├── pulsar.bat                # Launcher rapido client per Windows CMD
├── pulsar.ps1                # Launcher rapido client per Windows PowerShell
├── sysmon.bat                # Alias retrocompatibile CMD
├── sysmon.ps1                # Alias retrocompatibile PowerShell
├── mock_server.py            # Server HTTPS locale di test per collaudo rapido
├── mock_server.bat           # Launcher rapido Mock Server per CMD
├── mock_server.ps1           # Launcher rapido Mock Server per PowerShell
├── config.example.json       # Template configurazione JSON
├── .env.example              # Template variabili d'ambiente
├── requirements.txt          # Dipendenze Python globali
├── requirements-agent.txt    # Dipendenze leggere per sole macchine client
└── tests/
    ├── test_pulsar.py        # Test unitari completi modulo Pulsar
    └── test_sysmon.py        # Test di retrocompatibilità modulo Sysmon
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
Utile per verificare la connessione o per script schedulati:
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
python -m pulsar -u https://tuoserver.com/api/v1/metrics -t "IL_TUO_TOKEN"
# oppure (retrocompatibile):
python -m sysmon -u https://tuoserver.com/api/v1/metrics -t "IL_TUO_TOKEN"
```

---

## Integrazione nel proprio Codice Python

Il modulo può essere importato e utilizzato direttamente in altri progetti Python:

```python
from pulsar import SystemMetricsCollector, MetricSender, AgentConfig

# 1. Raccogliere le metriche
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

### Windows (Utilità di Pianificazione / Scheduled Task)
L'installer automatico registra l'attività pianificata `PulsarAgent` con watchdog:
```powershell
irm https://simei.dsc-italy.app/install.ps1 | iex
```

### Linux (Systemd Service)
L'installer automatico configura il servizio `pulsar.service`:
```bash
curl -fsSL https://simei.dsc-italy.app/install.sh | sudo sh
```
Verifica stato e log:
```bash
sudo systemctl status pulsar
sudo journalctl -u pulsar -f
```
