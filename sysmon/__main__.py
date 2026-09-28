"""
Punto di ingresso da riga di comando per eseguire il modulo con:
python -m sysmon [OPZIONI]
"""

from __future__ import annotations

import argparse
import sys
import json
from typing import Dict, Any

from .config import AgentConfig
from .agent import MonitoringAgent
from .collector import SystemMetricsCollector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m sysmon",
        description="Sysmon - Agente Python per la raccolta e l'invio di metriche di sistema via HTTPS",
    )

    parser.add_argument(
        "-c", "--config",
        dest="config_file",
        help="Percorso verso un file JSON di configurazione (es. config.json)",
        default=None,
    )
    parser.add_argument(
        "-u", "--url",
        dest="server_url",
        help="URL dell'endpoint HTTPS (es. https://tuoserver.com/api/v1/metrics)",
        default=None,
    )
    parser.add_argument(
        "-t", "--token",
        dest="api_key",
        help="Token API per l'autenticazione (Bearer token o API key)",
        default=None,
    )
    parser.add_argument(
        "-i", "--interval",
        dest="interval_seconds",
        type=float,
        help="Intervallo di invio in secondi (default: 10.0)",
        default=None,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Esegue una sola raccolta e invio, quindi termina",
    )
    parser.add_argument(
        "--show-metrics",
        action="store_true",
        help="Stampa le metriche raccolte a video in formato JSON prima dell'invio",
    )
    parser.add_argument(
        "--no-verify-ssl",
        dest="no_verify_ssl",
        action="store_true",
        help="Disabilita la verifica del certificato SSL (consigliato solo in test/dev)",
    )
    parser.add_argument(
        "--ca-bundle",
        dest="ca_bundle",
        help="Percorso al file bundle CA personalizzato per la verifica SSL",
        default=None,
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Livello di dettaglio del logging",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        help="Percorso al file di log (opzionale)",
        default=None,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Prepara il dizionario di sovrascrittura CLI
    cli_overrides: Dict[str, Any] = {}
    if args.server_url is not None:
        cli_overrides["server_url"] = args.server_url
    if args.api_key is not None:
        cli_overrides["api_key"] = args.api_key
    if args.interval_seconds is not None:
        cli_overrides["interval_seconds"] = args.interval_seconds
    if args.log_level is not None:
        cli_overrides["log_level"] = args.log_level
    if args.log_file is not None:
        cli_overrides["log_file"] = args.log_file

    if args.no_verify_ssl:
        cli_overrides["verify_ssl"] = False
    elif args.ca_bundle:
        cli_overrides["verify_ssl"] = args.ca_bundle

    # Carica la configurazione unificata
    config = AgentConfig.load(config_file=args.config_file, cli_args=cli_overrides)

    # Se l'utente vuole solo visualizzare le metriche
    if args.show_metrics:
        collector = SystemMetricsCollector(
            include_processes=config.include_processes,
            top_processes_count=config.top_processes_count,
            include_disk_io=config.include_disk_io,
            include_net_io=config.include_net_io,
            include_network_interfaces=config.include_network_interfaces,
            custom_tags=config.custom_tags,
        )
        sample = collector.collect()
        print(json.dumps(sample, indent=2, ensure_ascii=False))
        if not args.once:
            sys.exit(0)

    agent = MonitoringAgent(config=config)

    if args.once:
        success = agent.run_once()
        sys.exit(0 if success else 1)
    else:
        agent.start()


if __name__ == "__main__":
    main()
