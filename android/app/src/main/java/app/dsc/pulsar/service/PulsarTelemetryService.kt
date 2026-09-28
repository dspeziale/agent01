package app.dsc.pulsar.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import app.dsc.pulsar.MainActivity
import app.dsc.pulsar.collector.AndroidMetricsCollector
import app.dsc.pulsar.data.PulsarPreferences
import app.dsc.pulsar.network.PulsarSender
import app.dsc.pulsar.storage.OfflineBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Servizio in primo piano (Foreground Service) per la raccolta continua
 * della telemetria Android e trasmissione sicura al server Pulsar.
 */
class PulsarTelemetryService : Service() {

    private val serviceJob = Job()
    private val serviceScope = CoroutineScope(Dispatchers.IO + serviceJob)

    private lateinit var prefs: PulsarPreferences
    private lateinit var collector: AndroidMetricsCollector
    private lateinit var sender: PulsarSender
    private lateinit var buffer: OfflineBuffer

    private var loopJob: Job? = null

    companion object {
        const val CHANNEL_ID = "pulsar_telemetry_channel"
        const val NOTIFICATION_ID = 4242

        const val ACTION_START = "app.dsc.pulsar.action.START"
        const val ACTION_STOP = "app.dsc.pulsar.action.STOP"

        // Stato live condiviso con l'interfaccia Compose
        private val _isRunning = MutableStateFlow(false)
        val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()

        private val _lastTransmissionStatus = MutableStateFlow("Inattivo")
        val lastTransmissionStatus: StateFlow<String> = _lastTransmissionStatus.asStateFlow()

        private val _lastTransmissionTime = MutableStateFlow<String?>(null)
        val lastTransmissionTime: StateFlow<String?> = _lastTransmissionTime.asStateFlow()

        private val _lastPayload = MutableStateFlow<JSONObject?>(null)
        val lastPayload: StateFlow<JSONObject?> = _lastPayload.asStateFlow()

        fun start(context: Context) {
            val intent = Intent(context, PulsarTelemetryService::class.java).apply {
                action = ACTION_START
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            val intent = Intent(context, PulsarTelemetryService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }
    }

    override fun onCreate() {
        super.onCreate()
        prefs = PulsarPreferences(this)
        collector = AndroidMetricsCollector(this)
        sender = PulsarSender()
        buffer = OfflineBuffer(this)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopForegroundLoop()
                stopSelf()
                return START_NOT_STICKY
            }
            else -> {
                startForeground(NOTIFICATION_ID, buildNotification("Avvio sonda telemetrica in corso..."))
                startForegroundLoop()
            }
        }
        return START_STICKY
    }

    private fun startForegroundLoop() {
        _isRunning.value = true
        prefs.isServiceEnabled = true

        loopJob?.cancel()
        loopJob = serviceScope.launch {
            val timeFormat = SimpleDateFormat("HH:mm:ss", Locale.getDefault())

            while (isActive) {
                val serverUrl = prefs.serverUrl
                val token = prefs.token
                val intervalSeconds = prefs.intervalSeconds

                try {
                    // 1. Raccoglie metriche complete
                    val payload = collector.collect()
                    _lastPayload.value = payload

                    // 2. Tenta l'invio al server
                    val result = sender.send(serverUrl, payload, token)

                    val nowStr = timeFormat.format(Date())
                    _lastTransmissionTime.value = nowStr
                    prefs.lastSentTimestamp = System.currentTimeMillis()

                    if (result.isSuccess) {
                        prefs.incrementSentCount()
                        _lastTransmissionStatus.value = "Trasmesso con successo (HTTP ${result.getOrNull()}) alle $nowStr"
                        prefs.lastStatus = "OK (HTTP ${result.getOrNull()})"

                        // 3. Svuota il buffer offline se presente
                        val drained = buffer.drain(serverUrl, token, sender)
                        val extraMsg = if (drained > 0) " + $drained record offline" else ""

                        updateNotification("Online - Ultimo invio: $nowStr$extraMsg")
                    } else {
                        // Salva nel buffer offline locale
                        buffer.enqueue(payload)
                        val err = result.exceptionOrNull()?.message ?: "Errore di rete"
                        _lastTransmissionStatus.value = "Errore: $err (salvato nel buffer offline)"
                        prefs.lastStatus = "Errore: $err"
                        updateNotification("Buffer offline (${buffer.getPendingCount()} record) - Ultimo tentativo: $nowStr")
                    }
                } catch (e: Exception) {
                    _lastTransmissionStatus.value = "Errore imprevisto: ${e.message}"
                    prefs.lastStatus = "Errore: ${e.message}"
                }

                // Attende l'intervallo configurato
                delay(intervalSeconds * 1000L)
            }
        }
    }

    private fun stopForegroundLoop() {
        loopJob?.cancel()
        loopJob = null
        _isRunning.value = false
        prefs.isServiceEnabled = false
        _lastTransmissionStatus.value = "Sonda arrestata"
    }

    override fun onDestroy() {
        super.onDestroy()
        stopForegroundLoop()
        serviceJob.cancel()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Pulsar Telemetry Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Servizio continuo di monitoraggio e invio telemetria di sistema"
                setShowBadge(false)
            }
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(contentText: String): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Pulsar Telemetry")
            .setContentText(contentText)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, buildNotification(text))
    }
}
