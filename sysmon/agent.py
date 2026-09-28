"""
Agente principale di monitoraggio continuo.
Gestisce il ciclo di campionamento temporizzato, l'intercettazione dei segnali di terminazione
e la coordinazione tra raccoglitore (collector) e trasmettitore (sender).
"""

from __future__ import annotations

import time
import signal
import logging
import sys
from typing import Optional

from .config import AgentConfig
from .collector import SystemMetricsCollector
from .sender import MetricSender

logger = logging.getLogger("sysmon.agent")


class MonitoringAgent:
    """Orchestratore dell'agente di monitoraggio di sistema."""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self._setup_logging()

        logger.info("Inizializzazione Sysmon Agent...")
        logger.debug(f"Configurazione attiva: {self.config.to_dict()}")

        self.collector = SystemMetricsCollector(
            include_processes=self.config.include_processes,
            top_processes_count=self.config.top_processes_count,
            include_disk_io=self.config.include_disk_io,
            include_net_io=self.config.include_net_io,
            include_network_interfaces=self.config.include_network_interfaces,
            custom_tags=self.config.custom_tags,
        )

        self.sender = MetricSender(self.config)
        self._is_running = False

    def _setup_logging(self) -> None:
        """Configura il logging di base per il pacchetto sysmon."""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        root_logger = logging.getLogger("sysmon")
        root_logger.setLevel(log_level)

        if not root_logger.handlers:
            formatter = logging.Formatter(
                fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

            if self.config.log_file:
                try:
                    file_handler = logging.FileHandler(self.config.log_file, encoding="utf-8")
                    file_handler.setFormatter(formatter)
                    root_logger.addHandler(file_handler)
                except Exception as e:
                    root_logger.warning(f"Impossibile aprire il file di log {self.config.log_file}: {e}")

    def run_once(self) -> bool:
        """Esegue un singolo ciclo di raccolta e invio. Utile per test o cronjob."""
        logger.info("Campionamento istantaneo delle metriche in corso...")
        snapshot = self.collector.collect()
        success = self.sender.send(snapshot)
        if success:
            logger.info("Metriche trasmesse con successo al server.")
        else:
            logger.warning("Invio non riuscito. Le metriche sono state preservate o scartate secondo configurazione.")
        return success

    def _signal_handler(self, signum, frame):
        """Intercetta Ctrl+C o segnali di stop per terminare senza corrompere i dati."""
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        logger.info(f"Ricevuto segnale di terminazione ({sig_name}). Arresto ordinato dell'agente...")
        self._is_running = False

    def start(self) -> None:
        """Avvia il loop periodico di monitoraggio."""
        self._is_running = True

        # Registrazione gestione segnali di arresto
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except (ValueError, AttributeError):
            # In alcuni thread non principali o ambienti specifici la registrazione può non essere permessa
            pass

        logger.info(
            f"Sysmon Agent avviato. Frequenza di campionamento: ogni {self.config.interval_seconds}s. Server: {self.config.server_url}"
        )

        while self._is_running:
            start_time = time.time()

            try:
                snapshot = self.collector.collect()
                self.sender.send(snapshot)
            except Exception as e:
                logger.error(f"Errore non gestito nel ciclo di monitoraggio: {e}", exc_info=True)

            elapsed = time.time() - start_time
            sleep_duration = max(0.1, self.config.interval_seconds - elapsed)

            # Esegui la sleep a piccoli step per reagire prontamente a Ctrl+C
            step_sleep = 0.5
            total_slept = 0.0
            while self._is_running and total_slept < sleep_duration:
                chunk = min(step_sleep, sleep_duration - total_slept)
                time.sleep(chunk)
                total_slept += chunk

        self._cleanup()

    def _cleanup(self) -> None:
        """Operazioni di pulizia prima dell'uscita definitiva."""
        logger.info("Chiusura risorse e sessione di rete...")
        self.sender.close()
        logger.info("Sysmon Agent arrestato correttamente.")
