package app.dsc.pulsar.data

import android.content.Context
import android.content.SharedPreferences

/**
 * Gestisce la persistenza delle preferenze utente (Server URL, Token, Intervallo, Stato Servizio).
 */
class PulsarPreferences(context: Context) {

    private val prefs: SharedPreferences = context.getSharedPreferences("pulsar_settings", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_TOKEN = "token"
        private const val KEY_INTERVAL = "interval"
        private const val KEY_SERVICE_ENABLED = "service_enabled"
        private const val KEY_LAST_STATUS = "last_status"
        private const val KEY_LAST_SENT_TIME = "last_sent_time"
        private const val KEY_TOTAL_SENT_COUNT = "total_sent_count"

        const val DEFAULT_SERVER_URL = "https://simei.dsc-italy.app/api/v1/metrics"
        const val DEFAULT_INTERVAL = 15
    }

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER_URL, DEFAULT_SERVER_URL) ?: DEFAULT_SERVER_URL
        set(value) = prefs.edit().putString(KEY_SERVER_URL, value.trim()).apply()

    var token: String
        get() = prefs.getString(KEY_TOKEN, "") ?: ""
        set(value) = prefs.edit().putString(KEY_TOKEN, value.trim()).apply()

    var intervalSeconds: Int
        get() = prefs.getInt(KEY_INTERVAL, DEFAULT_INTERVAL)
        set(value) = prefs.edit().putInt(KEY_INTERVAL, value.coerceIn(5, 300)).apply()

    var isServiceEnabled: Boolean
        get() = prefs.getBoolean(KEY_SERVICE_ENABLED, false)
        set(value) = prefs.edit().putBoolean(KEY_SERVICE_ENABLED, value).apply()

    var lastStatus: String
        get() = prefs.getString(KEY_LAST_STATUS, "In attesa di avvio") ?: "In attesa di avvio"
        set(value) = prefs.edit().putString(KEY_LAST_STATUS, value).apply()

    var lastSentTimestamp: Long
        get() = prefs.getLong(KEY_LAST_SENT_TIME, 0L)
        set(value) = prefs.edit().putLong(KEY_LAST_SENT_TIME, value).apply()

    var totalSentCount: Long
        get() = prefs.getLong(KEY_TOTAL_SENT_COUNT, 0L)
        set(value) = prefs.edit().putLong(KEY_TOTAL_SENT_COUNT, value).apply()

    fun incrementSentCount() {
        totalSentCount += 1
    }
}
