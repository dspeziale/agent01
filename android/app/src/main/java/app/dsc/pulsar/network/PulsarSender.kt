package app.dsc.pulsar.network

import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import javax.net.ssl.HttpsURLConnection

/**
 * Gestisce l'invio HTTP/HTTPS dei pacchetti telemetria al server Pulsar.
 */
class PulsarSender {

    /**
     * Invia il payload JSON al server specificato.
     * Restituisce Result con il codice di stato HTTP (es. 200, 202).
     */
    fun send(serverUrl: String, payload: JSONObject, token: String = ""): Result<Int> {
        var connection: HttpURLConnection? = null
        return try {
            val url = URL(serverUrl)
            connection = url.openConnection() as HttpURLConnection
            connection.apply {
                requestMethod = "POST"
                connectTimeout = 12000
                readTimeout = 12000
                doOutput = true
                doInput = true
                useCaches = false
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                setRequestProperty("User-Agent", "Pulsar-Android-Agent/2.0.0")
                if (token.isNotBlank()) {
                    setRequestProperty("Authorization", "Bearer $token")
                }
            }

            val jsonBytes = payload.toString().toByteArray(Charsets.UTF_8)
            connection.setFixedLengthStreamingMode(jsonBytes.size)

            connection.outputStream.use { os ->
                os.write(jsonBytes)
                os.flush()
            }

            val statusCode = connection.responseCode
            if (statusCode in 200..299) {
                Result.success(statusCode)
            } else {
                val errorStream = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                Result.failure(Exception("HTTP $statusCode: $errorStream"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        } finally {
            connection?.disconnect()
        }
    }
}
