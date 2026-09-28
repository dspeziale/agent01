# Guida al Deployment su Coolify con PostgreSQL

Questa guida spiega come distribuire in produzione il backend di **Sysmon** sulla tua istanza di **Coolify** collegandolo a un database **PostgreSQL**.

---

## Panoramica dell'Architettura

```text
[ Macchine Host ]                          [ Server Coolify ]
+---------------------+                      +-----------------------------------+
|  Sysmon Agent       |  HTTPS (POST JSON)   |  Traefik / Caddy Reverse Proxy    |
|  (Windows / Linux)  | -------------------> |  (Let's Encrypt SSL automatico)   |
+---------------------+                      +-----------------+-----------------+
                                                               |
                                             +-----------------v-----------------+
                                             |  sysmon-server (FastAPI / Uvicorn)|
                                             |  - /api/v1/metrics (Ingestion)    |
                                             |  - /api/v1/machines (Dashboard)   |
                                             |  - /docs (Swagger OpenAPI UI)     |
                                             +-----------------+-----------------+
                                                               |
                                             +-----------------v-----------------+
                                             |  PostgreSQL 16 Database           |
                                             |  (Tabelle, Indici GIN & B-Tree)   |
                                             +-----------------------------------+
```

---

## Metodo 1: Deploy Diretto con Docker Compose (Consigliato)

È il metodo più semplice e rapido per avere il server FastAPI e PostgreSQL pronti in un unico stack gestito da Coolify.

### Passi su Coolify:
1. Accedi alla tua dashboard di **Coolify**.
2. Seleziona il tuo **Project** e **Environment** (es. `Production`).
3. Clicca su **+ New Resource** e scegli **Docker Compose**.
4. Seleziona come sorgente:
   - Se hai il progetto su GitHub/GitLab: collega il repository.
   - Oppure seleziona **Docker Compose (Raw content)** e incolla il contenuto del file [`docker-compose.yml`](docker-compose.yml):

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: sysmon-postgres
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-sysmon}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-cambia_questa_password_sicura}
      POSTGRES_DB: ${POSTGRES_DB:-sysmon_db}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-sysmon} -d ${POSTGRES_DB:-sysmon_db}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - sysmon-net

  sysmon-server:
    build:
      context: .
      dockerfile: server/Dockerfile
    container_name: sysmon-server
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-sysmon}:${POSTGRES_PASSWORD:-cambia_questa_password_sicura}@postgres:5432/${POSTGRES_DB:-sysmon_db}
      SYSMON_SERVER_TOKEN: ${SYSMON_SERVER_TOKEN:-tuo_token_segreto}
      LOG_LEVEL: INFO
      PORT: 8000
    networks:
      - sysmon-net

volumes:
  postgres_data:
    name: sysmon_postgres_data

networks:
  sysmon-net:
    name: sysmon-net
    driver: bridge
```

5. **Configurazione FQDN (Dominio HTTPS)**:
   - Nella scheda del servizio `sysmon-server`, nel campo **Domains (FQDN)** inserisci il tuo dominio pubblico (es. `https://sysmon.tuodominio.it`).
   - Coolify configurerà automaticamente il reverse proxy Traefik e genererà un certificato **SSL/TLS valido tramite Let's Encrypt**.
6. **Variabili d'Ambiente (Environment Variables)**:
   - `POSTGRES_PASSWORD`: password complessa per il database.
   - `SYSMON_SERVER_TOKEN`: token segreto che gli agenti dovranno inviare nell'header per autenticarsi.
7. Clicca su **Deploy**.

---

## Metodo 2: Database PostgreSQL Separato + Sysmon App

Se in Coolify hai già un database PostgreSQL o preferisci crearlo dal catalogo Coolify:

1. **Crea il Database**:
   - In Coolify: **+ New Resource** -> **PostgreSQL**.
   - Coolify ti fornirà le credenziali e la stringa di connessione interna (es. `postgresql://postgres:password@postgres:5432/sysmon_db`).
2. **Crea l'Applicazione Sysmon**:
   - In Coolify: **+ New Resource** -> **Git Repository** (o Dockerfile).
   - Base Directory: `/`
   - Dockerfile Location: `server/Dockerfile`
3. **Imposta le Variabili d'Ambiente dell'App**:
   ```ini
   DATABASE_URL=postgresql://postgres:password@postgres:5432/sysmon_db
   SYSMON_SERVER_TOKEN=tuo_token_segreto
   PORT=8000
   ```
4. Assegna il dominio pubblico HTTPS (es. `https://sysmon.tuodominio.it`) e clicca **Deploy**.

---

## Inizializzazione Automatica del Database

All'avvio, il server Sysmon si connette a PostgreSQL ed esegue automaticamente le migrazioni creando le tabelle e gli indici se non esistono:

- **`machines`**: anagrafica degli host monitorati (hostname, OS, architettura, IP, first_seen, last_seen).
- **`telemetry_snapshots`**: serie storica con metriche aggregate (CPU %, RAM %, Swap %, Rete, Uptime) e colonna **`raw_payload JSONB`** (contenente l'intero albero dettagliato della telemetria).
- **`telemetry_disks`**: partizioni montate, GB totali, usati, liberi e percentuale di occupazione.
- **`telemetry_top_processes`**: classifica dei processi con maggior consumo di CPU e memoria RAM (RSS/VMS).

---

## Configurazione dell'Agente Sysmon sui Client

Una volta che il server è attivo su Coolify con il suo dominio HTTPS, configura l'agente su ciascuna macchina da monitorare:

### Avvio rapido da riga di comando:
```powershell
python main.py --url https://sysmon.tuodominio.it/api/v1/metrics --token "tuo_token_segreto" --interval 10
```

### Oppure tramite `config.json`:
Modifica `config.json`:
```json
{
  "server_url": "https://sysmon.tuodominio.it/api/v1/metrics",
  "api_key": "tuo_token_segreto",
  "auth_type": "Bearer",
  "interval_seconds": 15.0,
  "verify_ssl": true,
  "offline_buffer_enabled": true
}
```
Ed esegui:
```powershell
.\sysmon.bat
```

> [!NOTE]
> Con Coolify il dominio ha un certificato SSL valido Let's Encrypt, quindi `verify_ssl: true` funzionerà direttamente senza alcun warning o flag speciale!

---

## Interrogazione Dati e Dashboard

### 1. Documentazione Interattiva Swagger UI
Apri nel browser:
`https://sysmon.tuodominio.it/docs`

Puoi testare direttamente le API:
- `GET /api/v1/machines`: elenco delle macchine e stato online/offline.
- `GET /api/v1/machines/{machine_id}`: ultimo snapshot completo della macchina.
- `GET /api/v1/machines/{machine_id}/history`: storico metriche per grafici.
- `GET /health`: stato di salute del server e connessione al DB.

### 2. Esempi di Query SQL su PostgreSQL

Puoi collegarti al database con qualsiasi client (DBeaver, pgAdmin, DataGrip, psql):

#### Ultimo stato di tutte le macchine:
```sql
SELECT 
    hostname, 
    os, 
    cpu_percent_total AS "CPU %", 
    ram_percent AS "RAM %", 
    health_status, 
    last_seen_at,
    (last_seen_at >= NOW() - INTERVAL '2 minutes') AS is_online
FROM machines m
JOIN LATERAL (
    SELECT cpu_percent_total, ram_percent, health_status
    FROM telemetry_snapshots
    WHERE machine_id = m.machine_id
    ORDER BY timestamp_utc DESC LIMIT 1
) s ON TRUE;
```

#### Macchine con utilizzo CPU o RAM superiore all'85%:
```sql
SELECT machine_id, timestamp_utc, cpu_percent_total, ram_percent, health_alerts
FROM telemetry_snapshots
WHERE cpu_percent_total > 85 OR ram_percent > 85
ORDER BY timestamp_utc DESC;
```

#### Estrazione dati dettagliati dal payload JSONB:
```sql
-- Dettaglio delle connessioni attive per stato dall'ultimo snapshot
SELECT 
    machine_id,
    raw_payload->'network'->'connections_summary' AS open_connections
FROM telemetry_snapshots
ORDER BY timestamp_utc DESC
LIMIT 5;
```
