#!/usr/bin/env bash
# ==============================================================================
# Sysmon Agent - Script di Installazione Completo per Linux (Systemd Service)
# Supporta: Debian, Ubuntu, CentOS, RHEL, Rocky, AlmaLinux, Fedora, Arch, Alpine, openSUSE
#
# Esecuzione rapida da remoto (one-liner):
#   curl -fsSL https://raw.githubusercontent.com/dspeziale/agent01/main/install-linux.sh | sudo bash
# Oppure in locale:
#   sudo ./install-linux.sh
# ==============================================================================

set -e

# Colori per il terminale
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Parametri predefiniti
SERVER_URL="https://simei.dsc-italy.app/api/v1/metrics"
TOKEN=""
INTERVAL=15
INSTALL_DIR="/opt/sysmon"
SERVICE_NAME="sysmon.service"
GITHUB_REPO="https://github.com/dspeziale/agent01"
TARBALL_URL="https://github.com/dspeziale/agent01/archive/refs/heads/main.tar.gz"

UNINSTALL=false
CHECK_STATUS=false
INTERACTIVE=false

# Se eseguito in un terminale interattivo e senza argomenti, attiva modalità guidata
if [ -t 0 ] && [ $# -eq 0 ]; then
    INTERACTIVE=true
fi

# Parsing argomenti
while [[ $# -gt 0 ]]; do
    case "$1" in
        -u|--url)
            SERVER_URL="$2"
            INTERACTIVE=false
            shift 2
            ;;
        -t|--token)
            TOKEN="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -d|--dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --status)
            CHECK_STATUS=true
            shift
            ;;
        -h|--help)
            echo -e "${CYAN}Sysmon Agent - Installatore Completo per Linux${NC}"
            echo -e "Uso: sudo ./install-linux.sh [OPZIONI]\n"
            echo "Opzioni:"
            echo "  -u, --url <URL>        URL endpoint del server (default: https://simei.dsc-italy.app/api/v1/metrics)"
            echo "  -t, --token <TOKEN>    Token API di autenticazione (opzionale)"
            echo "  -i, --interval <SEC>   Intervallo di campionamento in secondi (default: 15)"
            echo "  -d, --dir <PATH>       Cartella di installazione (default: /opt/sysmon)"
            echo "      --status           Mostra lo stato attuale del servizio e gli ultimi log"
            echo "      --uninstall        Rimuove completamente il servizio e i file di Sysmon"
            echo "  -h, --help             Mostra questo messaggio di aiuto"
            exit 0
            ;;
        *)
            echo -e "${RED}Opzione sconosciuta: $1${NC}"
            echo "Usa --help per visualizzare la guida."
            exit 1
            ;;
    esac
done

# Verifica privilegi di Root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[INFO] Privilegi di amministratore richiesti. Rilancio con sudo...${NC}"
    exec sudo bash "$0" "$@"
fi

# ------------------------------------------------------------------------------
# 1. CONTROLLO STATO (--status)
# ------------------------------------------------------------------------------
if [ "$CHECK_STATUS" = true ]; then
    echo -e "\n${CYAN}=== STATO DEL SERVIZIO SYSMON ===${NC}"
    if command -v systemctl &>/dev/null && [ -f "/etc/systemd/system/$SERVICE_NAME" ]; then
        systemctl status "$SERVICE_NAME" --no-pager || true
        echo -e "\n${CYAN}--- Ultimi log di sistema (journalctl) ---${NC}"
        journalctl -u "$SERVICE_NAME" -n 20 --no-pager || true
    else
        echo -e "${YELLOW}Servizio systemd non trovato.${NC}"
        if [ -d "$INSTALL_DIR" ] && [ -f "$INSTALL_DIR/sysmon.log" ]; then
            echo -e "\n${CYAN}--- Ultimi log dal file $INSTALL_DIR/sysmon.log ---${NC}"
            tail -n 20 "$INSTALL_DIR/sysmon.log"
        fi
    fi
    exit 0
fi

# ------------------------------------------------------------------------------
# 2. DISINSTALLAZIONE (--uninstall)
# ------------------------------------------------------------------------------
if [ "$UNINSTALL" = true ]; then
    echo -e "\n${YELLOW}==========================================================${NC}"
    echo -e "${YELLOW}           DISINSTALLAZIONE AGENTE SYSMON                 ${NC}"
    echo -e "${YELLOW}==========================================================${NC}"
    
    if command -v systemctl &>/dev/null; then
        if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
            echo -e "${CYAN}[1/3] Arresto del servizio $SERVICE_NAME...${NC}"
            systemctl stop "$SERVICE_NAME" || true
        fi
        if [ -f "/etc/systemd/system/$SERVICE_NAME" ]; then
            echo -e "${CYAN}[2/3] Rimozione del servizio systemd...${NC}"
            systemctl disable "$SERVICE_NAME" 2>/dev/null || true
            rm -f "/etc/systemd/system/$SERVICE_NAME"
            systemctl daemon-reload || true
        fi
    fi

    # Uccisione di eventuali processi rimasti
    pkill -f "$INSTALL_DIR/main.py" 2>/dev/null || true

    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${CYAN}[3/3] Eliminazione cartella $INSTALL_DIR...${NC}"
        rm -rf "$INSTALL_DIR"
    fi

    echo -e "${GREEN}[OK] Agente Sysmon rimosso completamente dal sistema!${NC}\n"
    exit 0
fi

# ------------------------------------------------------------------------------
# 3. INTERATTIVITÀ (se aperto in shell senza argomenti)
# ------------------------------------------------------------------------------
clear 2>/dev/null || true
echo -e "${CYAN}==========================================================${NC}"
echo -e "${CYAN}       SYSMON AGENT - INSTALLATORE AUTOMATICO LINUX       ${NC}"
echo -e "${CYAN}==========================================================${NC}\n"

if [ "$INTERACTIVE" = true ]; then
    echo -e "${WHITE}Configurazione iniziale dell'agente:${NC}"
    read -r -p "URL del Server Telemetria [default: $SERVER_URL]: " input_url
    [ -n "$input_url" ] && SERVER_URL="$input_url"

    read -r -p "Token API (opzionale, premi Invio se non richiesto): " input_token
    [ -n "$input_token" ] && TOKEN="$input_token"

    read -r -p "Intervallo di invio in secondi [default: $INTERVAL]: " input_interval
    [ -n "$input_interval" ] && INTERVAL="$input_interval"
    echo ""
fi

# ------------------------------------------------------------------------------
# 4. INSTALLAZIONE PACCHETTI DI SISTEMA (Python 3, pip, venv, curl)
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[1/5] Rilevamento sistema e installazione dipendenze di sistema...${NC}"

if command -v apt-get &>/dev/null; then
    echo -e "  -> Gestore pacchetti rilevato: ${CYAN}apt (Debian/Ubuntu)${NC}"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv curl tar gzip ca-certificates
elif command -v dnf &>/dev/null; then
    echo -e "  -> Gestore pacchetti rilevato: ${CYAN}dnf (Fedora/RHEL/Rocky/Alma)${NC}"
    dnf install -y -q python3 python3-pip curl tar gzip ca-certificates
elif command -v yum &>/dev/null; then
    echo -e "  -> Gestore pacchetti rilevato: ${CYAN}yum (CentOS/RHEL 7)${NC}"
    yum install -y -q python3 python3-pip curl tar gzip ca-certificates
elif command -v pacman &>/dev/null; then
    echo -e "  -> Gestore pacchetti rilevato: ${CYAN}pacman (Arch/Manjaro)${NC}"
    pacman -Sy --noconfirm python python-pip python-virtualenv curl tar gzip ca-certificates
elif command -v apk &>/dev/null; then
    echo -e "  -> Gestore pacchetti rilevato: ${CYAN}apk (Alpine Linux)${NC}"
    apk add --no-cache python3 py3-pip py3-virtualenv curl tar gzip ca-certificates bash
elif command -v zypper &>/dev/null; then
    echo -e "  -> Gestore pacchetti rilevato: ${CYAN}zypper (openSUSE)${NC}"
    zypper --non-interactive install python3 python3-pip curl tar gzip ca-certificates
else
    echo -e "${YELLOW}  -> Gestore pacchetti standard non rilevato. Verifico la presenza di python3...${NC}"
fi

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[ERRORE] Python 3 non e' installato e non e' stato possibile installarlo automaticamente.${NC}"
    echo "Installa Python 3 manualmente e riprova."
    exit 1
fi

PY_VER=$(python3 --version 2>&1)
echo -e "  -> ${GREEN}Interprete attivo: $PY_VER${NC}"

# ------------------------------------------------------------------------------
# 5. PREPARAZIONE FILE DI SORGENTE
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/5] Predisposizione cartella applicazione in $INSTALL_DIR...${NC}"
mkdir -p "$INSTALL_DIR"

SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

SOURCE_FOUND=false

# Controlla se i sorgenti sono presenti in locale
if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/sysmon" ] && [ -f "$SCRIPT_DIR/main.py" ]; then
    echo -e "  -> Sorgenti trovati nella directory corrente: $SCRIPT_DIR"
    cp -r "$SCRIPT_DIR/sysmon" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/main.py" "$INSTALL_DIR/"
    [ -f "$SCRIPT_DIR/requirements-agent.txt" ] && cp "$SCRIPT_DIR/requirements-agent.txt" "$INSTALL_DIR/"
    SOURCE_FOUND=true
elif [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/../sysmon" ] && [ -f "$SCRIPT_DIR/../main.py" ]; then
    PARENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    echo -e "  -> Sorgenti trovati nella cartella superiore: $PARENT_DIR"
    cp -r "$PARENT_DIR/sysmon" "$INSTALL_DIR/"
    cp "$PARENT_DIR/main.py" "$INSTALL_DIR/"
    [ -f "$PARENT_DIR/requirements-agent.txt" ] && cp "$PARENT_DIR/requirements-agent.txt" "$INSTALL_DIR/"
    SOURCE_FOUND=true
elif [ -d "./sysmon" ] && [ -f "./main.py" ]; then
    echo -e "  -> Sorgenti trovati nel percorso corrente."
    cp -r "./sysmon" "$INSTALL_DIR/"
    cp "./main.py" "$INSTALL_DIR/"
    [ -f "./requirements-agent.txt" ] && cp "./requirements-agent.txt" "$INSTALL_DIR/"
    SOURCE_FOUND=true
fi

# Se non trovati in locale (es. script lanciato via curl/wget su server remoto), scarica da GitHub
if [ "$SOURCE_FOUND" = false ]; then
    echo -e "  -> Scaricamento sorgenti completi da GitHub (${CYAN}$TARBALL_URL${NC})..."
    TMP_DL_DIR=$(mktemp -d /tmp/sysmon-install-XXXXXX)
    
    if command -v curl &>/dev/null; then
        curl -fsSL "$TARBALL_URL" -o "$TMP_DL_DIR/sysmon.tar.gz"
    elif command -v wget &>/dev/null; then
        wget -qO "$TMP_DL_DIR/sysmon.tar.gz" "$TARBALL_URL"
    else
        echo -e "${RED}[ERRORE] Necessario curl o wget per scaricare i sorgenti dell'agente.${NC}"
        exit 1
    fi
    
    tar -xzf "$TMP_DL_DIR/sysmon.tar.gz" -C "$TMP_DL_DIR"
    EXTRACTED_DIR=$(find "$TMP_DL_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    
    if [ -d "$EXTRACTED_DIR/sysmon" ]; then
        cp -r "$EXTRACTED_DIR/sysmon" "$INSTALL_DIR/"
        cp "$EXTRACTED_DIR/main.py" "$INSTALL_DIR/"
        [ -f "$EXTRACTED_DIR/requirements-agent.txt" ] && cp "$EXTRACTED_DIR/requirements-agent.txt" "$INSTALL_DIR/"
        echo -e "  -> ${GREEN}Sorgenti scaricati ed estratti in $INSTALL_DIR con successo.${NC}"
    else
        echo -e "${RED}[ERRORE] Formato archivio sorgenti non valido.${NC}"
        rm -rf "$TMP_DL_DIR"
        exit 1
    fi
    rm -rf "$TMP_DL_DIR"
fi

# ------------------------------------------------------------------------------
# 6. CONFIGURAZIONE AMBIENTE VIRTUALE PYTHON (.venv)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/5] Creazione ambiente virtuale isolato (.venv)...${NC}"
VENV_DIR="$INSTALL_DIR/.venv"

if [ ! -f "$VENV_DIR/bin/python" ]; then
    python3 -m venv "$VENV_DIR" || {
        echo -e "${YELLOW}Tentativo fallback creazione virtualenv...${NC}"
        python3 -m pip install --upgrade virtualenv
        virtualenv "$VENV_DIR"
    }
fi

echo -e "  -> Installazione librerie minime (psutil, requests)..."
"$VENV_DIR/bin/pip" install --upgrade --no-warn-script-location pip >/dev/null 2>&1 || true

if [ -f "$INSTALL_DIR/requirements-agent.txt" ]; then
    "$VENV_DIR/bin/pip" install --no-warn-script-location -r "$INSTALL_DIR/requirements-agent.txt"
else
    "$VENV_DIR/bin/pip" install --no-warn-script-location "psutil>=5.9.0" "requests>=2.31.0"
fi
echo -e "  -> ${GREEN}Dipendenze Python installate con successo nel venv.${NC}"

# ------------------------------------------------------------------------------
# 7. GENERAZIONE CONFIGURAZIONE (config.json)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/5] Configurazione parametri operativi (config.json)...${NC}"
CONFIG_FILE="$INSTALL_DIR/config.json"

AUTH_TYPE="None"
if [ -n "$TOKEN" ]; then
    AUTH_TYPE="Bearer"
fi

cat <<EOF > "$CONFIG_FILE"
{
  "server_url": "$SERVER_URL",
  "api_key": "$TOKEN",
  "auth_type": "$AUTH_TYPE",
  "interval_seconds": $INTERVAL,
  "verify_ssl": true,
  "offline_buffer_enabled": true,
  "offline_buffer_db_path": "$INSTALL_DIR/sysmon_buffer.db",
  "include_processes": true,
  "top_processes_count": 10,
  "include_disk_io": true,
  "include_net_io": true,
  "include_network_interfaces": true,
  "log_level": "INFO",
  "log_file": "$INSTALL_DIR/sysmon.log"
}
EOF

chmod 600 "$CONFIG_FILE"
echo -e "  -> Server di destinazione: ${CYAN}$SERVER_URL${NC}"
echo -e "  -> Intervallo campionamento: ${CYAN}ogni ${INTERVAL}s${NC}"
echo -e "  -> Permessi ristretti applicati (chmod 600)"

# Copia questo installer in /opt/sysmon per consentire comode disinstallazioni o cambi config
cp "$0" "$INSTALL_DIR/install-linux.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/install-linux.sh" 2>/dev/null || true

# ------------------------------------------------------------------------------
# 8. REGISTRAZIONE E AVVIO SERVIZIO SYSTEMD
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/5] Registrazione e avvio servizio Systemd ($SERVICE_NAME)...${NC}"

if command -v systemctl &>/dev/null; then
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Sysmon - Agente Telemetria di Sistema
Documentation=https://simei.dsc-italy.app/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/main.py --config $CONFIG_FILE
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
MemoryMax=256M

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "  -> ${GREEN}Servizio $SERVICE_NAME avviato e attivo (running)!${NC}"
    else
        echo -e "  -> ${RED}[ATTENZIONE] Il servizio non risulta attivo. Verifica con: journalctl -u $SERVICE_NAME${NC}"
    fi
else
    echo -e "${YELLOW}Systemd non rilevato sul sistema (ambiente container o OpenRC).${NC}"
    echo -e "Avvio dell'agente in background tramite nohup..."
    nohup "$VENV_DIR/bin/python" "$INSTALL_DIR/main.py" --config "$CONFIG_FILE" > "$INSTALL_DIR/sysmon.stdout.log" 2>&1 &
    echo -e "  -> ${GREEN}Agente avviato con PID: $!${NC}"
fi

echo -e "\n${GREEN}==========================================================${NC}"
echo -e "${GREEN}    INSTALLAZIONE COMPLETATA CON SUCCESSO SU LINUX!       ${NC}"
echo -e "${GREEN}==========================================================${NC}"
echo -e "L'agente telemetria e' ora operativo e partira' automaticamente al riavvio."
echo -e "  • Verifica stato:      ${CYAN}sudo systemctl status sysmon${NC}"
echo -e "  • Log in tempo reale:  ${CYAN}sudo journalctl -u sysmon -f${NC}"
echo -e "  • Dashboard Web:       ${CYAN}https://simei.dsc-italy.app/${NC}"
echo -e "  • Disinstallazione:    ${YELLOW}sudo /opt/sysmon/install-linux.sh --uninstall${NC}\n"
