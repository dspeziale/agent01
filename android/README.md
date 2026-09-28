# Pulsar Android Agent (App Nativa Android)

Applicazione nativa Android in **Kotlin** e **Jetpack Compose** progettata per trasformare qualsiasi smartphone, tablet o dispositivo Android (Android 8.0 Oreo - Android 15+) in una sonda di telemetria attiva per la piattaforma **Pulsar**.

---

## Caratteristiche Principali

1. **Foreground Service Continuo con Watchdog**:
   - `PulsarTelemetryService`: Servizio in primo piano con notifica permanente a bassa priorità (`NotificationCompat.PRIORITY_LOW`), conforme ai requisiti di Android 14/15 (`foregroundServiceType="specialUse|dataSync"`).
   - Non viene terminato dal sistema operativo né dal risparmio energetico durante lo standby.
   - Avvio automatico al riavvio del dispositivo (`BootReceiver` con permesso `RECEIVE_BOOT_COMPLETED`).

2. **Raccolta Hardware e Sensori Approfondita**:
   - **Sistema**: Modello dispositivo (`Build.MODEL`), Produttore, Brand, Versione Android, Livello API, Architettura (`arm64-v8a`), Uptime reale.
   - **CPU**: Conteggio core logici/fisici e calcolo dell'utilizzo percentuale.
   - **RAM**: Monitoraggio in tempo reale della memoria totale, usata, libera (`ActivityManager.MemoryInfo`) e soglie di allarme memoria bassa.
   - **Storage**: Monitoraggio delle partizioni di archiviazione interna (`/data`) e memoria condivisa (`StatFs`).
   - **Batteria**: Livello percentuale, stato di carica (AC, USB, Wireless), temperatura (°C) e voltaggio (mV).
   - **Rete**: Schede di rete attive, rilevamento tipo di connessione (Wi-Fi, 4G/5G cellulare, Ethernet, VPN) e indirizzi IPv4/IPv6 locali.

3. **Buffer Locale Offline (Zero Perdita Dati)**:
   - Se la connessione mobile o Wi-Fi viene temporaneamente persa, i pacchetti telemetrici vengono salvati localmente nella memoria protetta dell'app (`pulsar_offline_buffer/`).
   - Al ripristino della connettività, l'agente esegue automaticamente il *drain* cronologico dei dati accumulati.

4. **Interfaccia Grafica Moderna Jetpack Compose**:
   - Palette scura e ciano coordinata con la Dashboard Web di Pulsar.
   - Switch per avviare o fermare la sonda con un tocco.
   - Pulsante "Invia Metriche Subito" per test manuali istantanei.
   - Configurazione grafica dell'URL Server, Token di autenticazione e selettore intervallo (5s, 10s, 15s, 30s, 60s).
   - Card diagnostiche riepilogative live su RAM, Batteria, Spazio e Rete.

---

## Compilazione e Installazione APK

### Requisiti
- **JDK 17** o superiore.
- **Android SDK** (API 26+) o **Android Studio Ladybug / Meerkat / Jellyfish**.

### 1. Apertura in Android Studio
1. Apri Android Studio.
2. Seleziona **Open...** e scegli la cartella `tests/agent01/android`.
3. Attendi la sincronizzazione di Gradle.
4. Collega il tuo dispositivo Android con Debug USB attivo oppure avvia un emulatore.
5. Clicca su **Run 'app'** (tasto verde Play).

### 2. Compilazione APK da riga di comando (Gradle)
```bash
cd android

# Su Windows:
.\gradlew.bat assembleDebug

# Su Linux / macOS:
./gradlew assembleDebug
```
L'APK generato sarà disponibile in:
`android/app/build/outputs/apk/debug/app-debug.apk`

### 3. Installazione rapida via ADB
```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

---

## Configurazione nell'App
1. Apri l'app **Pulsar Agent** sullo smartphone.
2. Inserisci l'URL del server:
   ```text
   https://simei.dsc-italy.app/api/v1/metrics
   ```
3. Seleziona l'intervallo desiderato (default: `15s`).
4. Attiva lo switch **Servizio in Background**.
5. Lo smartphone apparirà immediatamente online nella dashboard web:
   [https://simei.dsc-italy.app/](https://simei.dsc-italy.app/)
