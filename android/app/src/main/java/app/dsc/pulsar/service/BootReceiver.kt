package app.dsc.pulsar.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import app.dsc.pulsar.data.PulsarPreferences

/**
 * Riceve l'evento di completamento del boot di Android e riavvia
 * automaticamente il servizio di telemetria Pulsar se era attivo.
 */
class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        if (action == Intent.ACTION_BOOT_COMPLETED || action == "android.intent.action.QUICKBOOT_POWERON") {
            val prefs = PulsarPreferences(context)
            if (prefs.isServiceEnabled) {
                PulsarTelemetryService.start(context)
            }
        }
    }
}
