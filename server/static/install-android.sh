#!/bin/sh
# ==============================================================================
# Pulsar Telemetry Agent - Installer per Android (Termux / CLI)
#
# Comando one-liner da eseguire in Termux:
#   curl -fsSL https://simei.dsc-italy.app/install-android.sh | sh
# ==============================================================================

set -e

# Configurazione
SERVER_URL="${PULSAR_SERVER:-https://simei.dsc-italy.app}"
METRICS_URL="${SERVER_URL}/api/v1/metrics"
DOWNLOAD_URL="${SERVER_URL}/download/agent.tar.gz"
FALLBACK_URL="https://github.com/dspeziale/agent01/archive/refs/heads/main.tar.gz"
INTERVAL="${INTERVAL:-15}"
INSTALL_DIR="${HOME}/pulsar"
LEGACY_DIR="${HOME}/sysmon"

# Colori ANSI
C_CYAN="\033[1;36m"
C_GREEN="\033[1;32m"
C_YELLOW="\033[1;33m"
C_RED="\033[1;31m"
C_RESET="\033[0m"

printf "%b==========================================================\n" "$C_CYAN"
printf "   PULSAR TELEMETRY - INSTALLAZIONE ANDROID (Termux)\n"
printf "==========================================================%b\n\n" "$C_RESET"

# 1. Verifica ambiente Termux o Android
IS_TERMUX=false
if [ -n "$TERMUX_VERSION" ] || [ -d "/data/data/com.termux" ]; then
    IS_TERMUX=true
    printf "%b[1/5] Ambiente rilevato: Android Termux (OK)%b\n" "$C_GREEN" "$C_RESET"
else
    printf "%b[1/5] Ambiente Android/Linux shell%b\n" "$C_YELLOW" "$C_RESET"
fi

# 2. Pulizia versioni precedenti (Pulsar e Sysmon)
printf "%b[2/5] Rimozione e pulizia di eventuali versioni precedenti...%b\n" "$C_YELLOW" "$C_RESET"
# Termina processi attivi
pkill -9 -f "pulsar.*main.py" 2>/dev/null || true
pkill -9 -f "sysmon.*main.py" 2>/dev/null || true
pkill -9 -f "${INSTALL_DIR}/main.py" 2>/dev/null || true
pkill -9 -f "${LEGACY_DIR}/main.py" 2>/dev/null || true

# Pulizia cartelle precedenti
for d in "${INSTALL_DIR}" "${LEGACY_DIR}"; do
    if [ -d "$d" ]; then
        rm -rf "$d/pulsar" "$d/sysmon" "$d/main.py" "$d/config.json" "$d/*.db" "$d/*.log" 2>/dev/null || true
    fi
done

# 3. Installazione pacchetti essenziali
printf "%b[3/5] Verifica interprete Python e pacchetti di supporto...%b\n" "$C_YELLOW" "$C_RESET"
if [ "$IS_TERMUX" = true ]; then
    if ! command -v python >/dev/null 2>&1 || ! command -v pip >/dev/null 2>&1; then
        printf "  -> Installazione Python in Termux (pkg install python)...\n"
        pkg update -y >/dev/null 2>&1 || true
        pkg install -y python curl tar gzip >/dev/null 2>&1
    fi
    # Installa python-psutil dal repo Termux se disponibile (molto piu veloce della compilazione da sorgente)
    pkg install -y python-psutil >/dev/null 2>&1 || true
    # Installa termux-api se disponibile per sensori batteria
    pkg install -y termux-api >/dev/null 2>&1 || true
fi

if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    printf "%b[ERRORE CRITICO] Python non e' installato! Esegui prima: pkg install python%b\n" "$C_RED" "$C_RESET"
    exit 1
fi

PY_BIN="$(command -v python3 || command -v python)"
printf "  -> Interprete Python: %s (%s)\n" "$PY_BIN" "$("$PY_BIN" --version 2>&1)"

# Installa o aggiorna psutil e requests via pip se mancanti
if ! "$PY_BIN" -c "import psutil, requests" >/dev/null 2>&1; then
    printf "  -> Installazione dipendenze psutil e requests via pip...\n"
    if [ "$IS_TERMUX" = true ]; then
        # Assicura toolchain di compilazione nel caso in cui pip debba compilare psutil
        pkg install -y clang make libffi >/dev/null 2>&1 || true
    fi
    "$PY_BIN" -m pip install --upgrade --no-warn-script-location pip >/dev/null 2>&1 || true
    "$PY_BIN" -m pip install --no-warn-script-location "psutil>=5.9.0" "requests>=2.31.0" >/dev/null 2>&1 || {
        printf "%b  -> [AVVISO] Tentativo installazione psutil con --no-build-isolation...%b\n" "$C_YELLOW" "$C_RESET"
        "$PY_BIN" -m pip install --no-warn-script-location "requests>=2.31.0" >/dev/null 2>&1 || true
        "$PY_BIN" -m pip install --no-warn-script-location "psutil>=5.9.0" || true
    }
fi

# 4. Download ed estrazione del bundle Pulsar
printf "%b[4/5] Download agente telemetria da %s...%b\n" "$C_YELLOW" "$SERVER_URL" "$C_RESET"
mkdir -p "${INSTALL_DIR}"
TMP_TAR="/tmp/pulsar-android.tar.gz"
rm -f "${TMP_TAR}"

DOWNLOAD_SUCCESS=false
if command -v curl >/dev/null 2>&1; then
    if curl -fsSL "${DOWNLOAD_URL}" -o "${TMP_TAR}" >/dev/null 2>&1; then
        DOWNLOAD_SUCCESS=true
    elif curl -fsSL "${FALLBACK_URL}" -o "${TMP_TAR}" >/dev/null 2>&1; then
        DOWNLOAD_SUCCESS=true
    fi
fi

if [ "$DOWNLOAD_SUCCESS" = false ] || [ ! -f "${TMP_TAR}" ]; then
    printf "%b[ERRORE] Impossibile scaricare l'agente da %s.%b\n" "$C_RED" "$DOWNLOAD_URL" "$C_RESET"
    exit 1
fi

TMP_EXTRACT="/tmp/pulsar-extract-$$"
mkdir -p "${TMP_EXTRACT}"
tar -xzf "${TMP_TAR}" -C "${TMP_EXTRACT}"
rm -f "${TMP_TAR}"

SRC_DIR="${TMP_EXTRACT}"
if [ ! -d "${TMP_EXTRACT}/pulsar" ]; then
    FOUND_PULSAR="$(find "${TMP_EXTRACT}" -name "pulsar" -type d | head -n 1)"
    if [ -n "${FOUND_PULSAR}" ]; then
        SRC_DIR="$(dirname "${FOUND_PULSAR}")"
    fi
fi

cp -r "${SRC_DIR}/pulsar" "${INSTALL_DIR}/"
cp "${SRC_DIR}/main.py" "${INSTALL_DIR}/"
[ -d "${SRC_DIR}/sysmon" ] && cp -r "${SRC_DIR}/sysmon" "${INSTALL_DIR}/"
[ -f "${SRC_DIR}/debug_probe.py" ] && cp "${SRC_DIR}/debug_probe.py" "${INSTALL_DIR}/"
rm -rf "${TMP_EXTRACT}"

# 5. Generazione config.json e test invio
printf "%b[5/5] Configurazione agente e test di trasmissione...%b\n" "$C_YELLOW" "$C_RESET"
CONFIG_FILE="${INSTALL_DIR}/config.json"
cat <<EOF > "${CONFIG_FILE}"
{
  "server_url": "${METRICS_URL}",
  "api_key": "${PULSAR_TOKEN:-}",
  "auth_type": "None",
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
chmod 600 "${CONFIG_FILE}"

# Test di invio singolo (--once)
printf "  -> Test campionamento e invio metriche Android (--once)...\n"
TEST_OUTPUT=$("$PY_BIN" "${INSTALL_DIR}/main.py" --config "${CONFIG_FILE}" --once 2>&1)
TEST_STATUS=$?

if [ $TEST_STATUS -eq 0 ]; then
    printf "%b  -> Primo pacchetto telemetrico inviato con successo al server!%b\n" "$C_GREEN" "$C_RESET"
else
    printf "%b  -> [AVVISO] Invio iniziale non riuscito (exit code: %s):%b\n" "$C_YELLOW" "$TEST_STATUS" "$C_RESET"
    printf "%s\n" "$TEST_OUTPUT" | sed 's/^/     /'
fi

# Creazione comandi di avvio rapido nel PATH di Termux
BIN_DIR="${PREFIX:-/usr}/bin"
if [ -d "$BIN_DIR" ] && [ -w "$BIN_DIR" ]; then
    cat <<EOF > "${BIN_DIR}/pulsar"
#!/bin/sh
exec ${PY_BIN} ${INSTALL_DIR}/main.py --config ${CONFIG_FILE} "\$@"
EOF
    chmod +x "${BIN_DIR}/pulsar"

    cat <<EOF > "${BIN_DIR}/pulsar-bg"
#!/bin/sh
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi
nohup ${PY_BIN} ${INSTALL_DIR}/main.py --config ${CONFIG_FILE} > ${INSTALL_DIR}/pulsar.stdout.log 2>&1 &
echo "Pulsar avviato in background con PID: \$!"
echo "Log: tail -f ${INSTALL_DIR}/pulsar.log"
EOF
    chmod +x "${BIN_DIR}/pulsar-bg"
fi

# Avvio automatico in background se richiesto o consigliato
if [ "$IS_TERMUX" = true ] && command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi

nohup "$PY_BIN" "${INSTALL_DIR}/main.py" --config "${CONFIG_FILE}" > "${INSTALL_DIR}/pulsar.stdout.log" 2>&1 &
AGENT_PID=$!
sleep 2

printf "\n%b==========================================================\n" "$C_GREEN"
printf "    INSTALLAZIONE PULSAR SU ANDROID COMPLETATA!           \n"
printf "==========================================================%b\n" "$C_GREEN"
printf "L'agente Pulsar e' ora attivo in background su Android (PID: %s).\n" "$AGENT_PID"
printf "  • Dashboard Web:       %s\n" "$SERVER_URL"
printf "  • Cartella:            %s\n" "$INSTALL_DIR"
printf "  • Log attività:        %s/pulsar.log\n" "$INSTALL_DIR"
printf "\nComandi rapidi disponibili in Termux:\n"
printf "  • %bpulsar%b         -> Esegue l'agente a video\n" "$C_CYAN" "$C_RESET"
printf "  • %bpulsar-bg%b      -> Avvia l'agente in background permanente\n" "$C_CYAN" "$C_RESET"
printf "  • %btail -f %s/pulsar.log%b -> Visualizza i log in tempo reale\n" "$C_YELLOW" "$INSTALL_DIR" "$C_RESET"
printf "%b==========================================================%b\n\n" "$C_GREEN" "$C_RESET"
