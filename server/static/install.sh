#!/bin/sh
# ==============================================================================
# Sysmon Agent - Remote Installer per Linux
# Da eseguire con: sudo sh
#
# Comando one-liner:
#   curl -fsSL https://simei.dsc-italy.app/install.sh | sudo sh
# Oppure con wget:
#   wget -qO- https://simei.dsc-italy.app/install.sh | sudo sh
# ==============================================================================

set -e

# Configurazione predefinita (personalizzabile tramite variabili d'ambiente)
SERVER_URL="${SERVER_URL:-https://simei.dsc-italy.app}"
METRICS_URL="${METRICS_URL:-${SERVER_URL}/api/v1/metrics}"
DOWNLOAD_URL="${SERVER_URL}/download/agent.tar.gz"
FALLBACK_URL="https://github.com/dspeziale/agent01/archive/refs/heads/main.tar.gz"
TOKEN="${TOKEN:-}"
INTERVAL="${INTERVAL:-15}"
INSTALL_DIR="${INSTALL_DIR:-/opt/sysmon}"
SERVICE_NAME="sysmon.service"

echo "=========================================================="
echo "    SYSMON AGENT - INSTALLAZIONE REMOTA LINUX (sudo sh)   "
echo "=========================================================="

# 1. Verifica privilegi di root
if [ "$(id -u)" -ne 0 ]; then
    echo "[ERRORE] Questo script richiede privilegi di root."
    echo "Eseguilo usando: sudo sh"
    echo "Esempio: curl -fsSL ${SERVER_URL}/install.sh | sudo sh"
    exit 1
fi

echo "[1/5] Rilevamento sistema e installazione pacchetti..."

if [ -x "$(command -v apt-get)" ]; then
    echo "  -> Rilevato Debian/Ubuntu (apt)"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null 2>&1 || true
    apt-get install -y -qq python3 python3-pip python3-venv curl tar gzip ca-certificates >/dev/null 2>&1
elif [ -x "$(command -v dnf)" ]; then
    echo "  -> Rilevato Fedora/RHEL/Rocky/Alma (dnf)"
    dnf install -y -q python3 python3-pip curl tar gzip ca-certificates >/dev/null 2>&1
elif [ -x "$(command -v yum)" ]; then
    echo "  -> Rilevato CentOS/RHEL 7 (yum)"
    yum install -y -q python3 python3-pip curl tar gzip ca-certificates >/dev/null 2>&1
elif [ -x "$(command -v pacman)" ]; then
    echo "  -> Rilevato Arch Linux (pacman)"
    pacman -Sy --noconfirm python python-pip python-virtualenv curl tar gzip ca-certificates >/dev/null 2>&1
elif [ -x "$(command -v apk)" ]; then
    echo "  -> Rilevato Alpine Linux (apk)"
    apk add --no-cache python3 py3-pip py3-virtualenv curl tar gzip ca-certificates bash >/dev/null 2>&1
elif [ -x "$(command -v zypper)" ]; then
    echo "  -> Rilevato openSUSE (zypper)"
    zypper --non-interactive install python3 python3-pip curl tar gzip ca-certificates >/dev/null 2>&1
fi

if ! [ -x "$(command -v python3)" ]; then
    echo "[ERRORE] Python 3 non e' installato o non e' stato possibile installarlo automaticamente."
    exit 1
fi
echo "  -> Python 3 rilevato: $(python3 --version 2>&1)"

# 2. Creazione cartella e download bundle agente
echo "[2/5] Download agente telemetria da ${SERVER_URL}..."
mkdir -p "${INSTALL_DIR}"
TMP_TAR="/tmp/sysmon-agent.tar.gz"
rm -f "${TMP_TAR}"

DOWNLOAD_SUCCESS=false

# Tentativo download diretto dal server Sysmon
if [ -x "$(command -v curl)" ]; then
    if curl -fsSL "${DOWNLOAD_URL}" -o "${TMP_TAR}" >/dev/null 2>&1; then
        DOWNLOAD_SUCCESS=true
    elif curl -fsSL "${FALLBACK_URL}" -o "${TMP_TAR}" >/dev/null 2>&1; then
        DOWNLOAD_SUCCESS=true
    fi
elif [ -x "$(command -v wget)" ]; then
    if wget -qO "${TMP_TAR}" "${DOWNLOAD_URL}" >/dev/null 2>&1; then
        DOWNLOAD_SUCCESS=true
    elif wget -qO "${TMP_TAR}" "${FALLBACK_URL}" >/dev/null 2>&1; then
        DOWNLOAD_SUCCESS=true
    fi
fi

if [ "$DOWNLOAD_SUCCESS" = false ] || [ ! -f "${TMP_TAR}" ]; then
    echo "[ERRORE] Impossibile scaricare l'archivio dell'agente da ${DOWNLOAD_URL} ne da GitHub."
    exit 1
fi

# Estrazione pacchetto
TMP_EXTRACT="/tmp/sysmon-extract-$$"
mkdir -p "${TMP_EXTRACT}"
tar -xzf "${TMP_TAR}" -C "${TMP_EXTRACT}"
rm -f "${TMP_TAR}"

# Se l'archivio contiene una sottocartella radice (come da GitHub) oppure e' piatto (come dal nostro bundle)
if [ -d "${TMP_EXTRACT}/sysmon" ]; then
    cp -r "${TMP_EXTRACT}/sysmon" "${INSTALL_DIR}/"
    cp "${TMP_EXTRACT}/main.py" "${INSTALL_DIR}/"
    [ -f "${TMP_EXTRACT}/requirements-agent.txt" ] && cp "${TMP_EXTRACT}/requirements-agent.txt" "${INSTALL_DIR}/"
else
    # Cerca la cartella contenente sysmon
    FOUND_DIR="$(find "${TMP_EXTRACT}" -name "sysmon" -type d | head -n 1)"
    if [ -n "${FOUND_DIR}" ]; then
        PARENT_DIR="$(dirname "${FOUND_DIR}")"
        cp -r "${PARENT_DIR}/sysmon" "${INSTALL_DIR}/"
        cp "${PARENT_DIR}/main.py" "${INSTALL_DIR}/"
        [ -f "${PARENT_DIR}/requirements-agent.txt" ] && cp "${PARENT_DIR}/requirements-agent.txt" "${INSTALL_DIR}/"
    else
        echo "[ERRORE] Struttura archivio non valida."
        rm -rf "${TMP_EXTRACT}"
        exit 1
    fi
fi
rm -rf "${TMP_EXTRACT}"
echo "  -> File dell'agente posizionati in ${INSTALL_DIR}"

# 3. Creazione ambiente virtuale Python e dipendenze
echo "[3/5] Creazione virtual environment (.venv) e installazione dipendenze..."
VENV_DIR="${INSTALL_DIR}/.venv"
if [ ! -f "${VENV_DIR}/bin/python" ]; then
    python3 -m venv "${VENV_DIR}" >/dev/null 2>&1 || {
        python3 -m pip install --upgrade virtualenv >/dev/null 2>&1 || true
        virtualenv "${VENV_DIR}" >/dev/null 2>&1
    }
fi

"${VENV_DIR}/bin/pip" install --upgrade --no-warn-script-location pip >/dev/null 2>&1 || true
if [ -f "${INSTALL_DIR}/requirements-agent.txt" ]; then
    "${VENV_DIR}/bin/pip" install --no-warn-script-location -r "${INSTALL_DIR}/requirements-agent.txt" >/dev/null 2>&1
else
    "${VENV_DIR}/bin/pip" install --no-warn-script-location "psutil>=5.9.0" "requests>=2.31.0" >/dev/null 2>&1
fi
echo "  -> psutil e requests installati correttamente."

# 4. Generazione configurazione config.json
echo "[4/5] Configurazione agente (config.json)..."
AUTH_TYPE="None"
if [ -n "${TOKEN}" ]; then
    AUTH_TYPE="Bearer"
fi

cat <<EOF > "${INSTALL_DIR}/config.json"
{
  "server_url": "${METRICS_URL}",
  "api_key": "${TOKEN}",
  "auth_type": "${AUTH_TYPE}",
  "interval_seconds": ${INTERVAL},
  "verify_ssl": true,
  "offline_buffer_enabled": true,
  "offline_buffer_db_path": "${INSTALL_DIR}/sysmon_buffer.db",
  "include_processes": true,
  "top_processes_count": 10,
  "include_disk_io": true,
  "include_net_io": true,
  "include_network_interfaces": true,
  "log_level": "INFO",
  "log_file": "${INSTALL_DIR}/sysmon.log"
}
EOF
chmod 600 "${INSTALL_DIR}/config.json"
echo "  -> Destinazione metriche: ${METRICS_URL}"
echo "  -> Frequenza invio: ogni ${INTERVAL}s"

# 5. Test di invio iniziale (--once)
echo "[5/6] Test di connessione e primo campionamento telemetria (--once)..."
if "${VENV_DIR}/bin/python" "${INSTALL_DIR}/main.py" --config "${INSTALL_DIR}/config.json" --once >/dev/null 2>&1; then
    echo "  -> Primo pacchetto telemetrico inviato con successo al server!"
else
    echo "  -> [AVVISO] Verifica fallita, consultare il log in ${INSTALL_DIR}/sysmon.log"
fi

# 6. Registrazione e avvio servizio Systemd
echo "[6/6] Registrazione e avvio servizio di sistema..."
if [ -x "$(command -v systemctl)" ]; then
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"
    cat <<EOF > "${SERVICE_FILE}"
[Unit]
Description=Sysmon - Agente Telemetria di Sistema
Documentation=${SERVER_URL}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/main.py --config ${INSTALL_DIR}/config.json
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
MemoryMax=256M

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" >/dev/null 2>&1
    systemctl restart "${SERVICE_NAME}"
    sleep 2
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo "  -> Servizio ${SERVICE_NAME} attivo e avviato!"
    fi
else
    # Fallback per container o sistemi privi di systemd
    nohup "${VENV_DIR}/bin/python" "${INSTALL_DIR}/main.py" --config "${INSTALL_DIR}/config.json" > "${INSTALL_DIR}/sysmon.stdout.log" 2>&1 &
    echo "  -> Agente avviato in background con PID: $!"
fi

echo ""
echo "=========================================================="
echo "    INSTALLAZIONE COMPLETATA CON SUCCESSO SU LINUX!       "
echo "=========================================================="
echo "L'agente e' attivo e continuera' ad inviare dati al boot."
echo "Dashboard di controllo flotta: ${SERVER_URL}"
echo "Verifica stato:   sudo systemctl status sysmon"
echo "Log in diretta:   sudo journalctl -u sysmon -f"
echo "=========================================================="
