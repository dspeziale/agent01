"""
Gestione della configurazione dell'agente di monitoraggio.
Supporta valori di default, file JSON di configurazione, variabili d'ambiente e argomenti CLI.
"""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, Union


@dataclass
class AgentConfig:
    # Destinazione server HTTPS
    server_url: str = "https://localhost:8443/api/v1/metrics"
    api_key: Optional[str] = None
    auth_header_name: str = "Authorization"
    auth_type: str = "Bearer"  # "Bearer", "ApiKey", "None"
    custom_headers: Dict[str, str] = field(default_factory=dict)

    # Parametri temporali e di rete
    interval_seconds: float = 10.0
    timeout_seconds: float = 10.0
    verify_ssl: Union[bool, str] = True
    max_retries: int = 3
    retry_backoff_factor: float = 0.5

    # Buffer offline locale (in caso di indisponibilità del server)
    offline_buffer_enabled: bool = True
    offline_buffer_db_path: str = "pulsar_buffer.db"
    offline_buffer_max_records: int = 1000

    # Metriche dettagliate
    include_processes: bool = True
    top_processes_count: int = 5
    include_disk_io: bool = True
    include_net_io: bool = True
    include_network_interfaces: bool = True

    # Tag personalizzati (es. ambiente, cluster, datacenter)
    custom_tags: Dict[str, str] = field(default_factory=dict)

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentConfig:
        """Crea un'istanza di AgentConfig a partire da un dizionario filtrando le chiavi sconosciute."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        cfg = cls(**filtered)

        # Se si invia a localhost/127.0.0.1 con verify_ssl=True (default),
        # verifica se esiste il certificato locale 'server.crt' generato dal mock_server
        # per consentire una verifica SSL valida e automatica nei test locali
        if cfg.verify_ssl is True and ("localhost" in cfg.server_url or "127.0.0.1" in cfg.server_url):
            possible_crt = [
                "server.crt",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server.crt"),
            ]
            for p in possible_crt:
                if os.path.isfile(p):
                    cfg.verify_ssl = os.path.abspath(p)
                    break

        return cfg

    @classmethod
    def load(
        cls,
        config_file: Optional[str] = None,
        cli_args: Optional[Dict[str, Any]] = None,
    ) -> AgentConfig:
        """
        Carica la configurazione combinando:
        1. Defaults
        2. File JSON (se presente o specificato)
        3. Variabili d'ambiente (PULSAR_* con fallback SYSMON_*)
        4. Argomenti CLI forniti
        """
        config_data: Dict[str, Any] = {}

        # 1. Carica da file JSON se esiste
        target_file = config_file or os.environ.get("PULSAR_CONFIG_FILE") or os.environ.get("SYSMON_CONFIG_FILE", "config.json")
        if target_file and os.path.isfile(target_file):
            try:
                with open(target_file, "r", encoding="utf-8-sig") as f:
                    file_content = json.load(f)
                    if isinstance(file_content, dict):
                        config_data.update(file_content)
            except Exception as e:
                logging.getLogger("pulsar.config").warning(
                    f"Impossibile leggere il file di configurazione {target_file}: {e}"
                )

        # 2. Sovrascrittura da variabili d'ambiente
        suffixes = {
            "SERVER_URL": ("server_url", str),
            "API_KEY": ("api_key", str),
            "AUTH_HEADER": ("auth_header_name", str),
            "AUTH_TYPE": ("auth_type", str),
            "INTERVAL": ("interval_seconds", float),
            "TIMEOUT": ("timeout_seconds", float),
            "VERIFY_SSL": ("verify_ssl", lambda v: v.lower() not in ("0", "false", "no")),
            "MAX_RETRIES": ("max_retries", int),
            "OFFLINE_BUFFER": ("offline_buffer_enabled", lambda v: v.lower() not in ("0", "false", "no")),
            "BUFFER_DB": ("offline_buffer_db_path", str),
            "LOG_LEVEL": ("log_level", str),
            "LOG_FILE": ("log_file", str),
            "TOP_PROCESSES": ("top_processes_count", int),
        }

        for suffix, (field_name, parser) in suffixes.items():
            val = os.environ.get(f"PULSAR_{suffix}")
            if val is None:
                val = os.environ.get(f"SYSMON_{suffix}")
            if val is not None and val != "":
                try:
                    config_data[field_name] = parser(val)
                except Exception as e:
                    logging.getLogger("pulsar.config").warning(
                        f"Valore non valido per variabile d'ambiente PULSAR_{suffix}='{val}': {e}"
                    )

        # 3. Sovrascrittura da CLI args
        if cli_args:
            for k, v in cli_args.items():
                if v is not None:
                    config_data[k] = v

        return cls.from_dict(config_data)

    def to_dict(self) -> Dict[str, Any]:
        """Restituisce il dizionario della configurazione (escludendo api_key per log sicuri)."""
        d = asdict(self)
        if d.get("api_key"):
            d["api_key"] = "***HIDDEN***"
        return d
