"""
Modulo per la trasmissione delle metriche al server remoto tramite HTTPS.
Include gestione sessioni HTTP, autenticazione sicura (Bearer/API Key), retry automatici,
verifica SSL e svuotamento del buffer locale offline.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

from .config import AgentConfig
from .storage import MetricOfflineBuffer

logger = logging.getLogger("sysmon.sender")


class MetricSender:
    """Invia le metriche raccolte all'endpoint HTTPS configurato."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.buffer: Optional[MetricOfflineBuffer] = None
        if config.offline_buffer_enabled:
            self.buffer = MetricOfflineBuffer(
                db_path=config.offline_buffer_db_path,
                max_records=config.offline_buffer_max_records,
            )

        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Crea e configura una sessione requests con pool di connessione e retry."""
        session = requests.Session()

        # Configurazione header base
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SysmonAgent/1.0.0",
        }

        # Autenticazione
        if self.config.api_key:
            if self.config.auth_type.lower() == "bearer":
                headers[self.config.auth_header_name] = f"Bearer {self.config.api_key}"
            elif self.config.auth_type.lower() == "apikey":
                header_name = self.config.auth_header_name or "X-API-Key"
                headers[header_name] = self.config.api_key
            else:
                # Custom
                headers[self.config.auth_header_name] = self.config.api_key

        # Header personalizzati utente
        if self.config.custom_headers:
            headers.update(self.config.custom_headers)

        session.headers.update(headers)

        # Configurazione Retry automatici a livello HTTP
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Gestione verifica SSL (disabilitazione warning se verify=False intenzionale)
        if self.config.verify_ssl is False:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.warning("Verifica del certificato SSL DISABILITATA. Utilizzare solo in sviluppo.")

        return session

    def _post_payload(self, payload: Dict[str, Any]) -> requests.Response:
        """Esegue una singola chiamata POST HTTPS verso l'endpoint configurato."""
        return self.session.post(
            self.config.server_url,
            json=payload,
            timeout=self.config.timeout_seconds,
            verify=self.config.verify_ssl,
        )

    def flush_buffer(self, max_batch: int = 50) -> int:
        """
        Invia al server i dati accumulati nel buffer locale durante precedenti disconnessioni.
        Restituisce il numero di record svuotati con successo.
        """
        if not self.buffer:
            return 0

        pending_count = self.buffer.count()
        if pending_count == 0:
            return 0

        logger.info(f"Trovati {pending_count} record nel buffer offline. Tentativo di svuotamento...")
        flushed_count = 0
        batch = self.buffer.pop_batch(limit=max_batch)

        successful_ids = []
        for row_id, record in batch:
            resp = None
            try:
                resp = self._post_payload(record)
                if 200 <= resp.status_code < 300:
                    successful_ids.append(row_id)
                    flushed_count += 1
                else:
                    logger.warning(
                        f"Impossibile inviare record bufferizzato {row_id} (HTTP {resp.status_code}). Interruzione svuotamento."
                    )
                    break
            except Exception as e:
                logger.warning(f"Errore di rete durante lo svuotamento del buffer: {e}")
                break
            finally:
                if resp is not None:
                    try:
                        resp.close()
                    except Exception:
                        pass

        if successful_ids:
            self.buffer.delete_batch(successful_ids)
            logger.info(f"Svuotati con successo {flushed_count} record dal buffer offline.")

        return flushed_count

    def send(self, payload: Dict[str, Any]) -> bool:
        """
        Invia il payload delle metriche al server HTTPS.
        Se il server non è raggiungibile, salva i dati nel buffer locale per l'invio futuro.
        """
        # Prima prova a svuotare eventuali dati arretrati se la connessione è tornata
        if self.buffer and self.buffer.count() > 0:
            self.flush_buffer()

        response = None
        try:
            response = self._post_payload(payload)

            if 200 <= response.status_code < 300:
                logger.debug(f"Metriche inviate con successo a {self.config.server_url} (HTTP {response.status_code})")
                return True
            else:
                logger.warning(
                    f"Il server ha risposto con codice di errore HTTP {response.status_code}: {response.text[:200]}"
                )
                self._buffer_fallback(payload)
                return False

        except requests.exceptions.SSLError as e:
            logger.error(f"Errore di validazione certificato SSL su {self.config.server_url}: {e}")
            self._buffer_fallback(payload)
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"Errore di connessione HTTPS verso {self.config.server_url}: {e}")
            self._buffer_fallback(payload)
            return False
        except Exception as e:
            logger.error(f"Errore imprevisto durante l'invio metriche: {e}", exc_info=True)
            self._buffer_fallback(payload)
            return False
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

    def _buffer_fallback(self, payload: Dict[str, Any]) -> None:
        """Salva il record nel buffer locale se abilitato."""
        if self.buffer:
            saved = self.buffer.push(payload)
            if saved:
                logger.info(f"Metrica salvata nel buffer offline locale (totale in coda: {self.buffer.count()})")

    def close(self) -> None:
        """Chiude la sessione HTTP."""
        try:
            self.session.close()
        except Exception:
            pass
