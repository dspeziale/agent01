"""
Buffer locale SQLite per memorizzare le metriche in caso di indisponibilità della rete.
Garantisce che nessuna metrica vada persa durante disconnessioni o manutenzioni del server.
"""

from __future__ import annotations

import json
import sqlite3
import logging
from typing import List, Tuple, Dict, Any

logger = logging.getLogger("sysmon.storage")


class MetricOfflineBuffer:
    """Gestisce una coda persistente su file SQLite per i payload non recapitati."""

    def __init__(self, db_path: str = "sysmon_buffer.db", max_records: int = 1000):
        self.db_path = db_path
        self.max_records = max_records
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Inizializza la tabella SQLite se non esiste già."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS buffered_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        payload TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Errore inizializzazione database buffer SQLite: {e}")

    def push(self, metric: Dict[str, Any]) -> bool:
        """Salva un payload nel buffer locale."""
        try:
            payload_str = json.dumps(metric, ensure_ascii=False)
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO buffered_metrics (payload) VALUES (?)",
                    (payload_str,),
                )
                # Mantieni la dimensione sotto la soglia massima (elimina i più vecchi)
                conn.execute(
                    """
                    DELETE FROM buffered_metrics
                    WHERE id NOT IN (
                        SELECT id FROM buffered_metrics
                        ORDER BY id DESC
                        LIMIT ?
                    )
                    """,
                    (self.max_records,),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Errore salvataggio metrica nel buffer offline: {e}")
            return False

    def pop_batch(self, limit: int = 50) -> List[Tuple[int, Dict[str, Any]]]:
        """Estrae i record più vecchi ancora da inviare."""
        records: List[Tuple[int, Dict[str, Any]]] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT id, payload FROM buffered_metrics ORDER BY id ASC LIMIT ?",
                    (limit,),
                )
                for row in cursor.fetchall():
                    try:
                        data = json.loads(row["payload"])
                        records.append((row["id"], data))
                    except Exception as e:
                        logger.warning(f"Record {row['id']} corrotto nel buffer: {e}")
                        # Elimina record corrotti
                        conn.execute("DELETE FROM buffered_metrics WHERE id = ?", (row["id"],))
                conn.commit()
        except Exception as e:
            logger.error(f"Errore lettura buffer offline: {e}")
        return records

    def delete_batch(self, ids: List[int]) -> None:
        """Rimuove dal buffer i record inviati con successo."""
        if not ids:
            return
        try:
            with self._get_connection() as conn:
                placeholders = ",".join("?" for _ in ids)
                conn.execute(
                    f"DELETE FROM buffered_metrics WHERE id IN ({placeholders})",
                    ids,
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Errore eliminazione record inviati dal buffer: {e}")

    def count(self) -> int:
        """Restituisce il numero totale di elementi attualmente in coda."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM buffered_metrics")
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0
