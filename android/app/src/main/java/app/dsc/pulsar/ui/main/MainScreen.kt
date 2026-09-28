package app.dsc.pulsar.ui.main

import android.content.Context
import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.dsc.pulsar.collector.AndroidMetricsCollector
import app.dsc.pulsar.data.PulsarPreferences
import app.dsc.pulsar.network.PulsarSender
import app.dsc.pulsar.service.PulsarTelemetryService
import app.dsc.pulsar.theme.PulsarBackground
import app.dsc.pulsar.theme.PulsarCard
import app.dsc.pulsar.theme.PulsarCardBorder
import app.dsc.pulsar.theme.PulsarCyan
import app.dsc.pulsar.theme.PulsarGreen
import app.dsc.pulsar.theme.PulsarRed
import app.dsc.pulsar.theme.PulsarSurface
import app.dsc.pulsar.theme.PulsarTextMuted
import app.dsc.pulsar.theme.PulsarTextPrimary
import app.dsc.pulsar.theme.PulsarTextSecondary
import app.dsc.pulsar.theme.PulsarYellow
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

@Composable
fun MainScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs = remember { PulsarPreferences(context) }
    val collector = remember { AndroidMetricsCollector(context) }
    val sender = remember { PulsarSender() }

    val isRunning by PulsarTelemetryService.isRunning.collectAsState()
    val statusText by PulsarTelemetryService.lastTransmissionStatus.collectAsState()
    val lastTime by PulsarTelemetryService.lastTransmissionTime.collectAsState()
    val livePayload by PulsarTelemetryService.lastPayload.collectAsState()

    var serverUrl by remember { mutableStateOf(prefs.serverUrl) }
    var token by remember { mutableStateOf(prefs.token) }
    var interval by remember { mutableStateOf(prefs.intervalSeconds) }

    var localPayload by remember { mutableStateOf<JSONObject?>(null) }
    var isSendingManual by remember { mutableStateOf(false) }

    // Campionamento iniziale
    LaunchedEffect(Unit) {
        withContext(Dispatchers.IO) {
            localPayload = collector.collect()
        }
    }

    val displayPayload = livePayload ?: localPayload
    val scrollState = rememberScrollState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(PulsarBackground)
            .padding(horizontal = 16.dp, vertical = 24.dp)
            .verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 1. Header con Branding
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(12.dp)
                            .clip(CircleShape)
                            .background(if (isRunning) PulsarGreen else PulsarYellow)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "PULSAR TELEMETRY",
                        color = PulsarCyan,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp
                    )
                }
                Text(
                    text = "Sonda di Monitoraggio Android Native",
                    color = PulsarTextSecondary,
                    fontSize = 12.sp
                )
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(PulsarSurface)
                    .border(1.dp, if (isRunning) PulsarGreen else PulsarCardBorder, RoundedCornerShape(8.dp))
                    .padding(horizontal = 10.dp, vertical = 4.dp)
            ) {
                Text(
                    text = if (isRunning) "ATTIVA" else "STANDBY",
                    color = if (isRunning) PulsarGreen else PulsarYellow,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }

        // 2. Card Stato Operativo & Switch Servizio
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = PulsarSurface),
            shape = RoundedCornerShape(12.dp),
            border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(PulsarCardBorder))
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "Servizio in Background",
                            color = PulsarTextPrimary,
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 16.sp
                        )
                        Text(
                            text = if (isRunning) "Campionamento attivo continuo ad ogni boot" else "Servizio arrestato",
                            color = PulsarTextSecondary,
                            fontSize = 12.sp
                        )
                    }

                    Switch(
                        checked = isRunning,
                        onCheckedChange = { enable ->
                            if (enable) {
                                prefs.serverUrl = serverUrl
                                prefs.token = token
                                prefs.intervalSeconds = interval
                                PulsarTelemetryService.start(context)
                                Toast.makeText(context, "Sonda Pulsar avviata in background", Toast.LENGTH_SHORT).show()
                            } else {
                                PulsarTelemetryService.stop(context)
                                Toast.makeText(context, "Sonda Pulsar arrestata", Toast.LENGTH_SHORT).show()
                            }
                        },
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = PulsarCyan,
                            checkedTrackColor = PulsarCard,
                            uncheckedThumbColor = PulsarTextMuted,
                            uncheckedTrackColor = PulsarBackground
                        )
                    )
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Ultimo invio:",
                        color = PulsarTextMuted,
                        fontSize = 12.sp
                    )
                    Text(
                        text = lastTime ?: "Nessuno",
                        color = PulsarTextPrimary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium
                    )
                }

                Text(
                    text = statusText,
                    color = if (statusText.startsWith("Trasmesso") || statusText.startsWith("OK")) PulsarGreen else PulsarYellow,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace
                )

                // Pulsante Invia Adesso
                Button(
                    onClick = {
                        scope.launch {
                            isSendingManual = true
                            prefs.serverUrl = serverUrl
                            prefs.token = token
                            val payload = withContext(Dispatchers.IO) { collector.collect() }
                            localPayload = payload
                            val res = withContext(Dispatchers.IO) { sender.send(serverUrl, payload, token) }
                            isSendingManual = false
                            if (res.isSuccess) {
                                Toast.makeText(context, "Metriche trasmesse con successo (HTTP ${res.getOrNull()})", Toast.LENGTH_SHORT).show()
                            } else {
                                Toast.makeText(context, "Errore invio: ${res.exceptionOrNull()?.message}", Toast.LENGTH_LONG).show()
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !isSendingManual,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PulsarCyan,
                        contentColor = Color.Black
                    ),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text(
                        text = if (isSendingManual) "Invio telemetria in corso..." else "Invia Metriche Subito",
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        // 3. Snapshot Metriche Live
        displayPayload?.let { p ->
            val system = p.optJSONObject("system")
            val mem = p.optJSONObject("memory")?.optJSONObject("ram")
            val battery = p.optJSONObject("sensors")?.optJSONObject("battery")
            val diskPartitions = p.optJSONObject("disk")?.optJSONArray("partitions")
            val firstDisk = diskPartitions?.optJSONObject(0)
            val net = p.optJSONObject("network")

            Text(
                text = "PANORAMICA DISPOSITIVO",
                color = PulsarCyan,
                fontWeight = FontWeight.Bold,
                fontSize = 13.sp,
                letterSpacing = 1.sp
            )

            // Griglia schede metriche
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                // RAM
                MetricCard(
                    title = "MEMORIA RAM",
                    value = "${mem?.optDouble("percent_used", 0.0) ?: 0.0}%",
                    sub = "${mem?.optDouble("used_mb", 0.0)?.toInt() ?: 0} / ${mem?.optDouble("total_mb", 0.0)?.toInt() ?: 0} MB",
                    progress = ((mem?.optDouble("percent_used", 0.0) ?: 0.0) / 100.0).toFloat(),
                    modifier = Modifier.weight(1f)
                )

                // Batteria
                MetricCard(
                    title = "BATTERIA",
                    value = "${battery?.optInt("percent", 0)}%",
                    sub = if (battery?.optBoolean("power_plugged") == true) "In Carica (${battery.optString("plug_type")})" else "Su Batteria",
                    progress = ((battery?.optInt("percent", 0) ?: 0) / 100.0).toFloat(),
                    modifier = Modifier.weight(1f)
                )
            }

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                // Storage
                MetricCard(
                    title = "ARCHIVIAZIONE",
                    value = "${firstDisk?.optDouble("percent_used", 0.0) ?: 0.0}%",
                    sub = "Liberi: ${firstDisk?.optDouble("free_gb", 0.0) ?: 0.0} GB",
                    progress = ((firstDisk?.optDouble("percent_used", 0.0) ?: 0.0) / 100.0).toFloat(),
                    modifier = Modifier.weight(1f)
                )

                // Connessione
                MetricCard(
                    title = "CONNESSIONE",
                    value = net?.optString("active_transport") ?: "N/D",
                    sub = system?.optString("architecture") ?: "arm64",
                    progress = 1.0f,
                    modifier = Modifier.weight(1f)
                )
            }
        }

        // 4. Configurazione Parametri
        Text(
            text = "IMPOSTAZIONI SERVER & TRASMISSIONE",
            color = PulsarCyan,
            fontWeight = FontWeight.Bold,
            fontSize = 13.sp,
            letterSpacing = 1.sp
        )

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = PulsarSurface),
            shape = RoundedCornerShape(12.dp),
            border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(PulsarCardBorder))
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = serverUrl,
                    onValueChange = {
                        serverUrl = it
                        prefs.serverUrl = it
                    },
                    label = { Text("URL Endpoint Server") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = PulsarCyan,
                        unfocusedBorderColor = PulsarCardBorder,
                        focusedTextColor = PulsarTextPrimary,
                        unfocusedTextColor = PulsarTextPrimary
                    )
                )

                OutlinedTextField(
                    value = token,
                    onValueChange = {
                        token = it
                        prefs.token = it
                    },
                    label = { Text("Token Autenticazione (Opzionale)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = PulsarCyan,
                        unfocusedBorderColor = PulsarCardBorder,
                        focusedTextColor = PulsarTextPrimary,
                        unfocusedTextColor = PulsarTextPrimary
                    )
                )

                Text(
                    text = "Intervallo campionamento:",
                    color = PulsarTextSecondary,
                    fontSize = 12.sp
                )

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(5, 10, 15, 30, 60).forEach { sec ->
                        FilterChip(
                            selected = interval == sec,
                            onClick = {
                                interval = sec
                                prefs.intervalSeconds = sec
                            },
                            label = { Text("${sec}s") },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = PulsarCyan,
                                selectedLabelColor = Color.Black,
                                containerColor = PulsarCard,
                                labelColor = PulsarTextSecondary
                            )
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun MetricCard(
    title: String,
    value: String,
    sub: String,
    progress: Float,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = PulsarSurface),
        shape = RoundedCornerShape(10.dp),
        border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(PulsarCardBorder))
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(text = title, color = PulsarTextMuted, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(4.dp))
            Text(text = value, color = PulsarTextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(2.dp))
            Text(text = sub, color = PulsarTextSecondary, fontSize = 11.sp)
            Spacer(modifier = Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { progress.coerceIn(0f, 1f) },
                modifier = Modifier.fillMaxWidth().height(4.dp).clip(RoundedCornerShape(2.dp)),
                color = if (progress > 0.85f) PulsarRed else if (progress > 0.70f) PulsarYellow else PulsarCyan,
                trackColor = PulsarCard,
            )
        }
    }
}
