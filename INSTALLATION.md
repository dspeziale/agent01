# 🚀 Sysmon Agent - Guida Completa all'Installazione (Windows & Linux)

Questa guida illustra gli script di installazione automatica dell'agente **Sysmon** per **Windows** e **Linux**. Gli script configurano l'ambiente Python isolato, installano le dipendenze minime (`psutil`, `requests`) e registrano l'agente come **servizio persistente ad avvio automatico** al boot del sistema.

I dati raccolti vengono trasmessi al server centrale e visualizzati in tempo reale sulla dashboard web:
👉 **[https://simei.dsc-italy.app/](https://simei.dsc-italy.app/)**

---

## 🪟 1. INSTALLAZIONE SU WINDOWS

Lo script per Windows registra l'agente nell'**Utilità di Pianificazione di Windows** (*Task Scheduler*) come attività con massimi privilegi (`ONSTART` come `SYSTEM`, con fallback su `ONLOGON`). L'agente viene eseguito in modalità **100% invisibile** in background (tramite runner VBScript dedicato, senza alcuna finestra console o popup).

### Metodo A: Doppio Clic (Consigliato per desktop)
1. Fai clic destro su [`install-windows.bat`](file:///c:/JobArea/Personale/Codice/tests/agent01/install-windows.bat) e seleziona **"Esegui come amministratore"**.
2. L'installatore eseguirà tutte le fasi in automatico e avvierà il servizio in background.

---

### Metodo B: Da PowerShell locale (con parametri personalizzati)
Apri PowerShell come Amministratore nella cartella del repository:

```powershell
# Installazione base con parametri predefiniti:
.\scripts\install-windows.ps1

# Installazione personalizzata (URL server, Token API, intervallo in secondi):
.\scripts\install-windows.ps1 -ServerUrl "https://simei.dsc-italy.app/api/v1/metrics" -Token "IL_TUO_TOKEN" -Interval 15
```

---

### Metodo C: Installazione One-Liner da remoto su un nuovo PC
Se devi installare l'agente su una macchina Windows vergine senza dover clonare il repository manualmente:
Apri **PowerShell come Amministratore** ed esegui:

```powershell
irm https://raw.githubusercontent.com/dspeziale/agent01/main/scripts/install-windows.ps1 | iex
```
*(Lo script scaricherà automaticamente i sorgenti da GitHub, installerà Python via winget se mancante, configurerà il virtualenv in `C:\Program Files\Sysmon` e avvierà il servizio).*

---

### Gestione del Servizio su Windows:
- **Verifica stato del servizio e processi attivi**:
  ```powershell
  .\scripts\install-windows.ps1 -Status
  # Oppure:
  .\install-windows.bat --status
  ```
- **Visualizza i log in tempo reale**:
  ```powershell
  Get-Content .\sysmon.log -Wait -Tail 20
  ```
- **Disinstallazione completa**:
  ```powershell
  .\scripts\install-windows.ps1 -Uninstall
  # Oppure:
  .\install-windows.bat --uninstall
  ```

---

## 🐧 2. INSTALLAZIONE SU LINUX

Lo script per Linux rileva automaticamente la distribuzione in uso (**Debian, Ubuntu, CentOS, RHEL, Rocky Linux, AlmaLinux, Fedora, Arch Linux, Alpine, openSUSE**), installa le dipendenze di sistema necessarie e configura un servizio **Systemd** nativo (`sysmon.service`) con policy di riavvio automatico continuo (`Restart=always`, `RestartSec=10`).

### Metodo A: One-Liner remoto (Il più veloce)
Accedi via SSH al server Linux ed esegui come root:

```bash
curl -fsSL https://raw.githubusercontent.com/dspeziale/agent01/main/install-linux.sh | sudo bash
```
oppure con `wget`:
```bash
wget -qO- https://raw.githubusercontent.com/dspeziale/agent01/main/install-linux.sh | sudo bash
```

---

### Metodo B: Esecuzione in locale (se hai clonato il repo)
```bash
# 1. Rendi eseguibile lo script
chmod +x install-linux.sh

# 2. Avvia l'installazione con privilegi di root
sudo ./install-linux.sh

# Con opzioni personalizzate:
sudo ./install-linux.sh --url "https://simei.dsc-italy.app/api/v1/metrics" --token "IL_TUO_TOKEN" --interval 15
```

---

### Cosa fa l'installatore Linux:
1. Rileva il gestore pacchetti nativo (`apt`, `dnf`, `yum`, `pacman`, `apk`, `zypper`) e installa `python3`, `python3-pip`, `python3-venv`, `curl`, `tar`.
2. Se i file locali non sono presenti (es. lancio via curl), scarica ed estrae l'ultima versione da GitHub in `/opt/sysmon`.
3. Crea un virtual environment isolato in `/opt/sysmon/.venv/`.
4. Installa le librerie minime `psutil` e `requests`.
5. Genera `/opt/sysmon/config.json` con permessi protetti `600`.
6. Configura `/etc/systemd/system/sysmon.service` con limitazione di memoria a 256MB e riavvio resiliente.
7. Ricarica i demoni systemd, abilita il servizio all'avvio del sistema e lo avvia immediatamente.

---

### Gestione del Servizio su Linux:
- **Verifica stato del servizio**:
  ```bash
  sudo ./install-linux.sh --status
  # Oppure:
  sudo systemctl status sysmon
  ```
- **Visualizza i log in tempo reale**:
  ```bash
  sudo journalctl -u sysmon -f
  # Oppure dal file:
  tail -f /opt/sysmon/sysmon.log
  ```
- **Riavvia l'agente (es. dopo modifica config.json)**:
  ```bash
  sudo systemctl restart sysmon
  ```
- **Disinstallazione completa**:
  ```bash
  sudo ./install-linux.sh --uninstall
  # Oppure:
  sudo /opt/sysmon/install-linux.sh --uninstall
  ```

---

## 📊 3. PARAMETRI DI CONFIGURAZIONE DISPONIBILI

Entrambi gli installatori accettano i seguenti parametri per adattarsi a qualsiasi ambiente:

| Parametro (Linux) | Parametro (Windows) | Default | Descrizione |
|---|---|---|---|
| `-u`, `--url` | `-ServerUrl` | `https://simei.dsc-italy.app/api/v1/metrics` | Endpoint HTTPS di destinazione per le metriche |
| `-t`, `--token` | `-Token` | *(vuoto)* | Token Bearer API se l'autenticazione è abilitata |
| `-i`, `--interval` | `-Interval` | `15` | Frequenza di campionamento e invio (in secondi) |
| `-d`, `--dir` | `-InstallDir` | `/opt/sysmon` (Linux) / Repo o `C:\Program Files\Sysmon` (Win) | Percorso di destinazione dell'agente |
| `--status` | `-Status` | - | Controlla stato del servizio, processo e log |
| `--uninstall` | `-Uninstall` | - | Arresta e rimuove completamente il servizio |

---

## 🛡️ 4. BUFFER OFFLINE E TOLLERANZA AI GUASTI

Sia su Windows che su Linux, l'agente include un database SQLite locale (`sysmon_buffer.db`):
- Se il server centrale o la rete risultano temporaneamente non raggiungibili (es. blackout di rete, riavvio del server, codice HTTP 500/503), le metriche vengono salvate localmente in coda FIFO.
- Non appena la connessione al server viene ripristinata, l'agente svuota automaticamente la coda inviando tutti i record accumulati senza perdere alcun secondo di telemetria.
