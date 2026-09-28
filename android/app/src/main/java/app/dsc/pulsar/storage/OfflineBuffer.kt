package app.dsc.pulsar.storage

import android.content.Context
import app.dsc.pulsar.network.PulsarSender
import org.json.JSONObject
import java.io.File

/**
 * Buffer locale offline per evitare la perdita di metriche quando lo smartphone
 * e' offline o in assenza temporanea di connettivita' 4G/5G/WiFi.
 */
class OfflineBuffer(private val context: Context) {

    private val bufferDir: File by lazy {
        File(context.filesDir, "pulsar_offline_buffer").apply { mkdirs() }
    }

    private val maxBufferFiles = 200

    /**
     * Salva un payload JSON sul disco locale in formato timestamp.json
     */
    fun enqueue(payload: JSONObject) {
        try {
            val files = bufferDir.listFiles() ?: emptyArray()
            if (files.size >= maxBufferFiles) {
                // Elimina il piu vecchio
                files.sortedBy { it.lastModified() }.firstOrNull()?.delete()
            }

            val timestamp = System.currentTimeMillis()
            val file = File(bufferDir, "buffer_${timestamp}.json")
            file.writeText(payload.toString(), Charsets.UTF_8)
        } catch (e: Exception) {
            // Ignora errori di salvataggio disco
        }
    }

    /**
     * Tenta di inviare tutti i file accumulati in ordine cronologico.
     * Restituisce il numero di file svuotati con successo.
     */
    fun drain(serverUrl: String, token: String, sender: PulsarSender): Int {
        var flushedCount = 0
        try {
            val files = (bufferDir.listFiles() ?: emptyArray()).sortedBy { it.name }
            for (file in files) {
                try {
                    val content = file.readText(Charsets.UTF_8)
                    val json = JSONObject(content)
                    val res = sender.send(serverUrl, json, token)
                    if (res.isSuccess) {
                        file.delete()
                        flushedCount++
                    } else {
                        // Se fallisce l'invio, interrompi il drain per preservare l'ordine
                        break
                    }
                } catch (e: Exception) {
                    // File corrotto, rimuovilo
                    file.delete()
                }
            }
        } catch (e: Exception) {
            // Errore durante il drain
        }
        return flushedCount
    }

    fun getPendingCount(): Int {
        return (bufferDir.listFiles() ?: emptyArray()).size
    }
}
