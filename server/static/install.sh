#!/bin/sh
# ==============================================================================
# Pulsar Agent - Remote Installer per Linux
# Da eseguire con: sudo sh
#
# Comando one-liner:
#   curl -fsSL https://simei.dsc-italy.app/install.sh | sudo sh
# Oppure con wget:
#   wget -qO- https://simei.dsc-italy.app/install.sh | sudo sh
# ==============================================================================

set -e

# Configurazione predefinita (personalizzabile tramite variabili d'ambiente)
SERVER_URL="${PULSAR_SERVER:-${SERVER_URL:-https://simei.dsc-italy.app}}"
METRICS_URL="${METRICS_URL:-${SERVER_URL}/api/v1/metrics}"
DOWNLOAD_URL="${SERVER_URL}/download/agent.tar.gz"
FALLBACK_URL="https://github.com/dspeziale/agent01/archive/refs/heads/main.tar.gz"
TOKEN="${PULSAR_TOKEN:-${TOKEN:-}}"
INTERVAL="${INTERVAL:-15}"
INSTALL_DIR="${INSTALL_DIR:-/opt/pulsar}"
LEGACY_DIR="/opt/sysmon"
SERVICE_NAME="pulsar.service"

echo "=========================================================="
echo "    PULSAR AGENT - INSTALLAZIONE REMOTA LINUX (sudo sh)   "
echo "=========================================================="

# 1. Verifica privilegi di root
if [ "$(id -u)" -ne 0 ]; then
    echo "[ERRORE] Questo script richiede privilegi di root."
    echo "Eseguilo usando: sudo sh"
    echo "Esempio: curl -fsSL ${SERVER_URL}/install.sh | sudo sh"
    exit 1
fi

# 2. Verifica e rimozione completa di versioni precedenti (Pulsar e Sysmon)
echo "[1/6] Verifica e rimozione completa di versioni precedenti..."
HAD_PREVIOUS=false

# A. Arresto e rimozione di qualsiasi servizio systemd (Pulsar e legacy Sysmon)
if [ -x "$(command -v systemctl)" ]; then
    for s in "pulsar" "pulsar.service" "sysmon" "sysmon.service"; do
        if systemctl is-active --quiet "$s" 2>/dev/null || systemctl is-enabled --quiet "$s" 2>/dev/null || [ -f "/etc/systemd/system/$s" ]; then
            HAD_PREVIOUS=true
            echo "  -> Rimozione servizio systemd precedente: $s..."
            systemctl stop "$s" 2>/dev/null || true
            systemctl disable "$s" 2>/dev/null || true
            rm -f "/etc/systemd/system/$s"
            rm -rf "/etc/systemd/system/${s}.d"
        fi
    done
    if [ "$HAD_PREVIOUS" = true ]; then
        systemctl daemon-reload 2>/dev/null || true
        systemctl reset-failed 2>/dev/null || true
    fi
fi

# B. Terminazione forzata di eventuali processi residenti
OLD_PIDS=$(pgrep -f "pulsar.*main.py|sysmon.*main.py|${INSTALL_DIR}/main.py|${LEGACY_DIR}/main.py|debug_probe.py" 2>/dev/null || true)
if [ -n "${OLD_PIDS}" ]; then
    HAD_PREVIOUS=true
    echo "  -> Arresto forzato processi agenti attivi..."
    pkill -9 -f "pulsar.*main.py" 2>/dev/null || true
    pkill -9 -f "sysmon.*main.py" 2>/dev/null || true
    pkill -9 -f "${INSTALL_DIR}/main.py" 2>/dev/null || true
    pkill -9 -f "${LEGACY_DIR}/main.py" 2>/dev/null || true
    pkill -9 -f "debug_probe.py" 2>/dev/null || true
    sleep 1
fi

# C. Pulizia completa file e moduli obsoleti nelle cartelle di installazione
for d in "${INSTALL_DIR}" "${LEGACY_DIR}"; do
    if [ -d "$d" ]; then
        if [ -d "$d/pulsar" ] || [ -d "$d/sysmon" ] || [ -f "$d/main.py" ] || [ -f "$d/config.json" ]; then
            HAD_PREVIOUS=true
            echo "  -> Pulizia file e moduli della versione precedente in $d..."
            rm -rf "$d/pulsar" "$d/sysmon"
            rm -f "$d/main.py" "$d/debug_probe.py" "$d/requirements-agent.txt"
            rm -f "$d/pulsar_buffer.db" "$d/sysmon_buffer.db"
            find "$d" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        fi
    fi
done

if [ "$HAD_PREVIOUS" = true ]; then
    echo "  -> Disinstallazione e pulizia completata con successo."
else
    echo "  -> Nessuna versione precedente rilevata (installazione pulita)."
fi

# 3. Rilevamento sistema e installazione pacchetti
echo ""
echo "[2/6] Rilevamento sistema e installazione pacchetti..."

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

# 4. Creazione cartella e download bundle agente
echo "[3/6] Download agente telemetria da ${SERVER_URL}..."
mkdir -p "${INSTALL_DIR}"
TMP_TAR="/tmp/pulsar-agent.tar.gz"
rm -f "${TMP_TAR}"

DOWNLOAD_SUCCESS=false

# Tentativo download diretto dal server primario
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
TMP_EXTRACT="/tmp/pulsar-extract-$$"
mkdir -p "${TMP_EXTRACT}"
tar -xzf "${TMP_TAR}" -C "${TMP_EXTRACT}"
rm -f "${TMP_TAR}"

# Trova la cartella sorgente
SRC_DIR="${TMP_EXTRACT}"
if [ ! -d "${TMP_EXTRACT}/pulsar" ] && [ ! -d "${TMP_EXTRACT}/sysmon" ]; then
    FOUND_PULSAR="$(find "${TMP_EXTRACT}" -name "pulsar" -type d | head -n 1)"
    if [ -n "${FOUND_PULSAR}" ]; then
        SRC_DIR="$(dirname "${FOUND_PULSAR}")"
    else
        FOUND_SYSMON="$(find "${TMP_EXTRACT}" -name "sysmon" -type d | head -n 1)"
        if [ -n "${FOUND_SYSMON}" ]; then
            SRC_DIR="$(dirname "${FOUND_SYSMON}")"
        fi
    fi
fi

if [ -d "${SRC_DIR}/pulsar" ]; then
    cp -r "${SRC_DIR}/pulsar" "${INSTALL_DIR}/"
fi
if [ -d "${SRC_DIR}/sysmon" ]; then
    cp -r "${SRC_DIR}/sysmon" "${INSTALL_DIR}/"
fi
if [ -f "${SRC_DIR}/main.py" ]; then
    cp "${SRC_DIR}/main.py" "${INSTALL_DIR}/"
fi
if [ -f "${SRC_DIR}/requirements-agent.txt" ]; then
    cp "${SRC_DIR}/requirements-agent.txt" "${INSTALL_DIR}/"
fi
if [ -f "${SRC_DIR}/debug_probe.py" ]; then
    cp "${SRC_DIR}/debug_probe.py" "${INSTALL_DIR}/"
fi

rm -rf "${TMP_EXTRACT}"

# Assicura presenza di debug_probe.py
if [ ! -f "${INSTALL_DIR}/debug_probe.py" ]; then
    curl -fsSL "${SERVER_URL}/debug.py" -o "${INSTALL_DIR}/debug_probe.py" 2>/dev/null || true
fi
echo "  -> File dell'agente posizionati in ${INSTALL_DIR}"

# 5. Creazione ambiente virtuale Python e dipendenze
echo ""
echo "[4/6] Creazione virtual environment (.venv) e installazione dipendenze..."
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

# 6. Generazione configurazione config.json
echo ""
echo "[5/6] Configurazione agente (config.json) e test invio..."
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
  "offline_buffer_db_path": "${INSTALL_DIR}/pulsar_buffer.db",
  "include_processes": true,
  "top_processes_count": 10,
  "include_disk_io": true,
  "include_net_io": true,
  "include_network_interfaces": true,
  "log_level": "INFO",
  "log_file": "${INSTALL_DIR}/pulsar.log"
}
EOF
chmod 600 "${INSTALL_DIR}/config.json"
echo "  -> Destinazione metriche: ${METRICS_URL}"
echo "  -> Frequenza invio: ogni ${INTERVAL}s"

# Test di invio iniziale (--once)
echo "  -> Test di connessione e primo campionamento telemetria (--once)..."
TEST_OUTPUT=$("${VENV_DIR}/bin/python" "${INSTALL_DIR}/main.py" --config "${INSTALL_DIR}/config.json" --once 2>&1)
TEST_STATUS=$?
if [ $TEST_STATUS -eq 0 ]; then
    echo "  -> Primo pacchetto telemetrico inviato con successo al server!"
else
    echo "  -> [AVVISO] Invio iniziale non completato (exit code: $TEST_STATUS):"
    echo "$TEST_OUTPUT" | sed 's/^/     /'
    echo "  -> Puoi verificare la causa eseguendo: curl -fsSL ${SERVER_URL}/debug.sh | sudo sh"
fi

# 7. Registrazione e avvio servizio Systemd
echo ""
echo "[6/6] Registrazione e avvio servizio di sistema..."
if [ -x "$(command -v systemctl)" ]; then
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"
    cat <<EOF > "${SERVICE_FILE}"
[Unit]
Description=Pulsar - Agente Telemetria di Sistema
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
    nohup "${VENV_DIR}/bin/python" "${INSTALL_DIR}/main.py" --config "${INSTALL_DIR}/config.json" > "${INSTALL_DIR}/pulsar.stdout.log" 2>&1 &
    echo "  -> Agente avviato in background con PID: $!"
fi

echo ""
echo "=========================================================="
echo "    INSTALLAZIONE COMPLETATA CON SUCCESSO SU LINUX!       "
echo "=========================================================="
echo "L'agente Pulsar e' attivo e continuera' ad inviare dati al boot."
echo "Dashboard di controllo flotta: ${SERVER_URL}"
echo "Verifica stato:   sudo systemctl status pulsar"
echo "Log in diretta:   sudo journalctl -u pulsar -f"
echo "Sonda di debug:   curl -fsSL ${SERVER_URL}/debug.sh | sudo sh"
echo "=========================================================="
