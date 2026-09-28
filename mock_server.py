"""
Mock HTTPS Server per test e collaudo locale di Sysmon.
Genera automaticamente un certificato TLS autofirmato, avvia un server HTTPS
e stampa le metriche ricevute dall'agente.
"""

from __future__ import annotations

import os
import ssl
import json
import logging
import argparse
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [SERVER] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mock_server")


def generate_self_signed_cert(cert_path: str = "server.crt", key_path: str = "server.key") -> None:
    """Genera una coppia certificato/chiave autofirmata per localhost usando cryptography."""
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import ipaddress

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Sysmon Local Test"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    logger.info(f"Certificato autofirmato generato con successo: {cert_path}, {key_path}")


class MetricsReceiverHandler(BaseHTTPRequestHandler):
    expected_token: Optional[str] = None

    def log_message(self, format, *args):
        # Disabilita il log standard di BaseHTTPRequestHandler per usare logger pulito
        pass

    def _send_json_response(self, status_code: int, data: dict) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self) -> None:
        if self.path in ("/health", "/api/v1/health"):
            self._send_json_response(200, {"status": "ok", "service": "sysmon-receiver"})
        else:
            self._send_json_response(404, {"error": "Endpoint non trovato"})

    def do_POST(self) -> None:
        # Controllo autenticazione opzionale
        if self.expected_token:
            auth_header = self.headers.get("Authorization", "")
            api_key_header = self.headers.get("X-API-Key", "")
            valid = (
                auth_header == f"Bearer {self.expected_token}"
                or api_key_header == self.expected_token
            )
            if not valid:
                logger.warning("Ricevuta richiesta con token di autenticazione non valido o assente!")
                self._send_json_response(401, {"error": "Non autorizzato"})
                return

        # Lettura payload
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            payload = json.loads(post_data.decode("utf-8"))
        except Exception as e:
            logger.error(f"Payload JSON non valido: {e}")
            self._send_json_response(400, {"error": "Formato JSON errato"})
            return

        # Elaborazione e visualizzazione sintetica della metrica
        host = payload.get("system", {}).get("hostname", "unknown")
        os_name = payload.get("system", {}).get("os", "unknown")
        cpu_pct = payload.get("cpu", {}).get("percent_total", 0.0)
        ram_pct = payload.get("memory", {}).get("ram", {}).get("percent_used", 0.0)
        disk_partitions = payload.get("disk", {}).get("partitions", [])
        disk_summary = ", ".join([f"{d.get('mountpoint')}={d.get('percent_used')}%" for d in disk_partitions])
        top_procs = payload.get("processes", {}).get("top_processes", [])
        top_proc_name = top_procs[0].get("name") if top_procs else "N/A"
        health_status = payload.get("health", {}).get("status", "healthy").upper()
        active_conns = payload.get("network", {}).get("connections_summary", {}).get("ESTABLISHED", 0)

        logger.info(
            f"[{health_status}] da [{host}] ({os_name}) -> CPU: {cpu_pct}% | RAM: {ram_pct}% | Dischi: [{disk_summary}] | Conns EST: {active_conns} | Top: {top_proc_name}"
        )

        self._send_json_response(200, {
            "status": "success",
            "message": "Metriche ricevute e salvate",
            "server_time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })


def run_mock_server(host: str = "127.0.0.1", port: int = 8443, token: Optional[str] = None) -> None:
    cert_file = "server.crt"
    key_file = "server.key"
    generate_self_signed_cert(cert_file, key_file)

    MetricsReceiverHandler.expected_token = token
    server = HTTPServer((host, port), MetricsReceiverHandler)

    # Configurazione SSL/TLS
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print("\n" + "=" * 65)
    print(f"  MOCK HTTPS SERVER ATTIVO su https://{host}:{port}/api/v1/metrics")
    if token:
        print(f"  Token di autenticazione richiesto: {token}")
    print("  Premi Ctrl+C per arrestare il server.")
    print("=" * 65 + "\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Arresto del mock server in corso...")
    finally:
        server.server_close()
        logger.info("Server arrestato.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock HTTPS Server per Sysmon")
    parser.add_argument("--host", default="127.0.0.1", help="Host bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8443, help="Porta HTTPS (default: 8443)")
    parser.add_argument("--token", default=None, help="Token API richiesto (opzionale)")
    args = parser.parse_args()

    run_mock_server(host=args.host, port=args.port, token=args.token)
