"""
Sysmon Production Telemetry Server (FastAPI + PostgreSQL)
Fornisce gli endpoint HTTPS per l'ingestion della telemetria, il monitoraggio delle macchine,
e le serie storiche per dashboard, pronto per il deploy su Coolify.
"""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Security, Depends, status, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .db import DatabaseManager

# Configurazione logging strutturato
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="[%(asctime)s] [%(levelname)s] [SYSMON-SERVER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sysmon.server")

# Inizializzazione Database Manager
db = DatabaseManager()

# Token di sicurezza opzionale configurabile da variabile d'ambiente
SERVER_AUTH_TOKEN = os.environ.get("SYSMON_SERVER_TOKEN")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_auth_token(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
) -> bool:
    """Verifica l'autenticazione tramite Bearer Token o header X-API-Key se configurato."""
    if not SERVER_AUTH_TOKEN:
        return True  # Nessuna autenticazione richiesta

    # Verifica header Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token == SERVER_AUTH_TOKEN:
            return True

    # Verifica header X-API-Key: <token>
    if api_key == SERVER_AUTH_TOKEN:
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticazione richiesta: token non valido o mancante.",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestione ciclo di vita dell'applicazione: auto-inizializzazione schema PostgreSQL."""
    logger.info("Avvio del server Sysmon Telemetry...")
    try:
        if db.check_health():
            db.init_db()
            logger.info("Connessione a PostgreSQL stabilita e schema verificato.")
        else:
            logger.warning("PostgreSQL non raggiungibile all'avvio. Lo schema verrà inizializzato non appena il database sarà attivo.")
    except Exception as e:
        logger.warning(f"PostgreSQL non ancora raggiungibile all'avvio: {e}")
    yield
    logger.info("Arresto del server Sysmon Telemetry.")


app = FastAPI(
    title="Sysmon Telemetry Server",
    description="Backend definitivo ad alte prestazioni per la telemetria di sistema su Coolify e PostgreSQL.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Abilitazione CORS per il client web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montaggio cartella file statici (CSS, JS, dashboard)
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=FileResponse)
@app.get("/dashboard", response_class=FileResponse)
async def serve_dashboard():
    """Restituisce l'interfaccia Web interattiva per la navigazione della telemetria."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Sysmon Dashboard</h1><p>Interfaccia in fase di inizializzazione...</p>")



@app.get("/health")
async def health_check():
    """Health check per Coolify e Docker container orchestrator."""
    db_ok = db.check_health()
    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "database": "disconnected"},
        )
    return {
        "status": "healthy",
        "service": "sysmon-server",
        "version": "2.0.0",
        "database": "connected",
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/metrics", status_code=status.HTTP_201_CREATED)
async def receive_metrics(payload: Dict[str, Any], authenticated: bool = Depends(verify_auth_token)):
    """
    Endpoint primario di ingestione telemetria.
    Riceve il payload JSON trasmesso dall'agente Sysmon e lo salva atomicamente su PostgreSQL.
    """
    try:
        snapshot_id = db.save_telemetry(payload)
        machine_id = payload.get("metadata", {}).get("machine_id", "unknown")

        return {
            "status": "success",
            "message": "Telemetria archiviata con successo",
            "snapshot_id": snapshot_id,
            "machine_id": machine_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Errore durante l'archiviazione dello snapshot: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore interno durante il salvataggio dei dati: {str(e)}",
        )


@app.get("/api/v1/machines")
async def get_machines(authenticated: bool = Depends(verify_auth_token)):
    """Restituisce l'elenco di tutte le macchine registrate, con stato online/offline e ultime metriche."""
    try:
        if not db.check_health():
            return []
        return db.list_machines()
    except Exception as e:
        logger.error(f"Errore recupero lista macchine: {e}")
        return []


@app.get("/api/v1/machines/{machine_id}")
async def get_machine_details(machine_id: str, authenticated: bool = Depends(verify_auth_token)):
    """Restituisce l'ultimo snapshot JSONB completo per una specifica macchina."""
    try:
        if not db.check_health():
            return {}
        snapshot = db.get_latest_snapshot(machine_id)
        return snapshot or {}
    except Exception as e:
        logger.error(f"Errore recupero macchina {machine_id}: {e}")
        return {}


@app.get("/api/v1/machines/{machine_id}/history")
async def get_machine_history(
    machine_id: str,
    limit: int = 100,
    authenticated: bool = Depends(verify_auth_token),
):
    """Restituisce la serie storica delle metriche (CPU, RAM, Rete) di una macchina per grafici."""
    try:
        if not db.check_health():
            return {"machine_id": machine_id, "count": 0, "data": []}
        history = db.get_machine_history(machine_id=machine_id, limit=limit)
        return {"machine_id": machine_id, "count": len(history), "data": history}
    except Exception as e:
        logger.error(f"Errore recupero storico per {machine_id}: {e}")
        return {"machine_id": machine_id, "count": 0, "data": []}

