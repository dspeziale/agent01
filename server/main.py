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
from fastapi.responses import JSONResponse, HTMLResponse
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
        db.init_db()
        logger.info("Connessione a PostgreSQL stabilita e schema verificato.")
    except Exception as e:
        logger.error(f"Errore critico durante l'inizializzazione del database: {e}", exc_info=True)
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

# Abilitazione CORS per eventuali frontend/dashboard web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Pagina di benvenuto con stato del servizio e link alla documentazione OpenAPI."""
    db_ok = db.check_health()
    badge_color = "#22c55e" if db_ok else "#ef4444"
    status_text = "OPERATIVO & CONNESSO A POSTGRES" if db_ok else "ERRORE CONNESSIONE DATABASE"

    html = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <title>Sysmon Telemetry Server</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .card {{ background: #1e293b; border-radius: 12px; padding: 32px; max-width: 520px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; }}
            h1 {{ margin-top: 0; color: #38bdf8; font-size: 24px; }}
            p {{ line-height: 1.6; color: #94a3b8; }}
            .status {{ display: inline-block; padding: 6px 12px; border-radius: 9999px; background: {badge_color}22; color: {badge_color}; border: 1px solid {badge_color}; font-weight: bold; font-size: 13px; margin-bottom: 16px; }}
            .btn {{ display: inline-block; background: #38bdf8; color: #0f172a; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 12px; transition: background 0.2s; }}
            .btn:hover {{ background: #7dd3fc; }}
            code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #38bdf8; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="status">● {status_text}</div>
            <h1>Sysmon Telemetry Server v2.0</h1>
            <p>Il backend riceve le metriche hardware in streaming HTTPS (POST su <code>/api/v1/metrics</code>) e le archivia permanentemente su PostgreSQL.</p>
            <p>Deploy attivo e pronto su <strong>Coolify</strong>.</p>
            <a class="btn" href="/docs">Apri Documentazione Swagger API (/docs)</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


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
        return db.list_machines()
    except Exception as e:
        logger.error(f"Errore recupero lista macchine: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/v1/machines/{machine_id}")
async def get_machine_details(machine_id: str, authenticated: bool = Depends(verify_auth_token)):
    """Restituisce l'ultimo snapshot JSONB completo per una specifica macchina."""
    try:
        snapshot = db.get_latest_snapshot(machine_id)
        if not snapshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nessuna telemetria trovata per la macchina '{machine_id}'",
            )
        return snapshot
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore recupero macchina {machine_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/v1/machines/{machine_id}/history")
async def get_machine_history(
    machine_id: str,
    limit: int = 100,
    authenticated: bool = Depends(verify_auth_token),
):
    """Restituisce la serie storica delle metriche (CPU, RAM, Rete) di una macchina per grafici."""
    try:
        history = db.get_machine_history(machine_id=machine_id, limit=limit)
        return {"machine_id": machine_id, "count": len(history), "data": history}
    except Exception as e:
        logger.error(f"Errore recupero storico per {machine_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
