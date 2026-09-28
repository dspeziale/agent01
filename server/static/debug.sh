#!/usr/bin/env sh
# ==============================================================================
# Pulsar Telemetry - Launcher Sonda di Debug a Video (Linux)
# Esecuzione rapida:
#   curl -fsSL https://simei.dsc-italy.app/debug.sh | sudo sh
# ==============================================================================

set -e

echo "\033[1;36m=========================================================="
echo "   PULSAR TELEMETRY - AVVIO SONDA DI DEBUG A VIDEO (Linux)"
echo "==========================================================\033[0m\n"

# 1. Trova il miglior Python disponibile
PYTHON_BIN=""
if [ -f "/opt/pulsar/.venv/bin/python" ]; then
    PYTHON_BIN="/opt/pulsar/.venv/bin/python"
    echo "\033[0;32m[1/2] Rilevato ambiente virtuale dedicato Pulsar: $PYTHON_BIN\033[0m"
elif [ -f "/opt/sysmon/.venv/bin/python" ]; then
    PYTHON_BIN="/opt/sysmon/.venv/bin/python"
    echo "\033[0;33m[1/2] Rilevato ambiente virtuale legacy Sysmon: $PYTHON_BIN\033[0m"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=$(command -v python3)
    echo "\033[0;33m[1/2] Rilevato Python3 di sistema: $PYTHON_BIN\033[0m"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=$(command -v python)
    echo "\033[0;33m[1/2] Rilevato Python di sistema: $PYTHON_BIN\033[0m"
else
    echo "\033[0;31m[ERRORE CRITICO] Nessun interprete Python trovato!\033[0m"
    exit 1
fi

# 2. Download o caricamento script sonda
SERVER_URL="${PULSAR_SERVER:-${SYSMON_SERVER:-https://simei.dsc-italy.app}}"
DEBUG_URL="${SERVER_URL}/debug.py"
LOCAL_PULSAR_SCRIPT="/opt/pulsar/debug_probe.py"
LOCAL_SYSMON_SCRIPT="/opt/sysmon/debug_probe.py"
TEMP_SCRIPT="/tmp/pulsar_debug_probe.py"

TARGET_SCRIPT=""
if [ -f "$LOCAL_PULSAR_SCRIPT" ]; then
    TARGET_SCRIPT="$LOCAL_PULSAR_SCRIPT"
    echo "\033[0;32m[2/2] Utilizzo sonda locale Pulsar: $LOCAL_PULSAR_SCRIPT\033[0m"
elif [ -f "$LOCAL_SYSMON_SCRIPT" ]; then
    TARGET_SCRIPT="$LOCAL_SYSMON_SCRIPT"
    echo "\033[0;33m[2/2] Utilizzo sonda locale Sysmon: $LOCAL_SYSMON_SCRIPT\033[0m"
else
    echo "\033[0;33m[2/2] Download sonda aggiornata da $DEBUG_URL...\033[0m"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$DEBUG_URL" -o "$TEMP_SCRIPT"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$TEMP_SCRIPT" "$DEBUG_URL"
    else
        echo "\033[0;31m[ERRORE] Né curl né wget disponibili per il download.\033[0m"
        exit 1
    fi
    TARGET_SCRIPT="$TEMP_SCRIPT"
fi

echo "\n\033[1;36mAvvio esecuzione diagnostica a video...\033[0m\n"
exec "$PYTHON_BIN" "$TARGET_SCRIPT" "$@"
