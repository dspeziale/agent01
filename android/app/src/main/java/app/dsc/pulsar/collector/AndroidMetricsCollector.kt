package app.dsc.pulsar.collector

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.os.SystemClock
import android.provider.Settings
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.NetworkInterface
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID
import kotlin.math.roundToInt

/**
 * Raccoglie la telemetria di sistema completa da Android (CPU, RAM, Dischi, Rete, Batteria, Sensori)
 * e la serializza nel formato JSON identico atteso dal server Pulsar.
 */
class AndroidMetricsCollector(private val context: Context) {

    private val machineId: String by lazy { resolveMachineId() }
    private val isoDateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }

    private fun resolveMachineId(): String {
        return try {
            val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
            if (!androidId.isNullOrBlank() && androidId != "9774d56d682e549c") {
                "android-${Build.MODEL.replace(" ", "_")}-$androidId"
            } else {
                val prefs = context.getSharedPreferences("pulsar_identity", Context.MODE_PRIVATE)
                var storedId = prefs.getString("machine_uuid", null)
                if (storedId == null) {
                    storedId = "android-${Build.MODEL.replace(" ", "_")}-${UUID.randomUUID().toString().take(8)}"
                    prefs.edit().putString("machine_uuid", storedId).apply()
                }
                storedId
            }
        } catch (e: Exception) {
            "android-${Build.MODEL.replace(" ", "_")}-generic"
        }
    }

    /**
     * Campiona tutte le metriche e restituisce il JSONObject telemetrico pronto per l'invio.
     */
    fun collect(): JSONObject {
        val now = Date()
        val nowEpoch = now.time / 1000.0
        val timestampUtc = isoDateFormat.format(now)

        val root = JSONObject()

        // 1. Metadata
        val metadata = JSONObject().apply {
            put("timestamp_utc", timestampUtc)
            put("timestamp_epoch", nowEpoch)
            put("machine_id", machineId)
            put("hostname", Build.MODEL)
            put("client_version", "2.0.0-android")
            val tags = JSONObject().apply {
                put("platform", "android")
                put("brand", Build.BRAND)
                put("model", Build.MODEL)
                put("manufacturer", Build.MANUFACTURER)
                put("android_release", Build.VERSION.RELEASE)
                put("sdk_int", Build.VERSION.SDK_INT)
            }
            put("tags", tags)
        }
        root.put("metadata", metadata)

        // 2. System info
        val uptimeSeconds = SystemClock.elapsedRealtime() / 1000.0
        val bootTimeEpoch = (now.time - SystemClock.elapsedRealtime())
        val bootTimeUtc = isoDateFormat.format(Date(bootTimeEpoch))

        val days = (uptimeSeconds / 86400).toInt()
        val hours = ((uptimeSeconds % 86400) / 3600).toInt()
        val minutes = ((uptimeSeconds % 3600) / 60).toInt()
        val seconds = (uptimeSeconds % 60).toInt()
        val uptimeHuman = if (days > 0) "$days days, $hours:$minutes:$seconds" else "$hours:$minutes:$seconds"

        val system = JSONObject().apply {
            put("machine_id", machineId)
            put("hostname", Build.MODEL)
            put("fqdn", "${Build.MODEL.replace(" ", "-").lowercase(Locale.ROOT)}.local")
            put("os", "Android")
            put("os_release", Build.VERSION.RELEASE)
            put("os_version", "API ${Build.VERSION.SDK_INT} (${Build.ID})")
            put("architecture", Build.SUPPORTED_ABIS.firstOrNull() ?: "arm64-v8a")
            put("processor", Build.HARDWARE)
            put("python_version", "Kotlin Native/Android")
            put("timezone", TimeZone.getDefault().id)
            put("boot_time_utc", bootTimeUtc)
            put("uptime_seconds", Math.round(uptimeSeconds * 100.0) / 100.0)
            put("uptime_human", uptimeHuman)
            put("device_model", Build.MODEL)
            put("device_manufacturer", Build.MANUFACTURER)
            put("device_brand", Build.BRAND)
            put("device_name", Build.DEVICE)
            put("android_sdk_version", Build.VERSION.SDK_INT)
            put("active_users", JSONArray())
        }
        root.put("system", system)

        // 3. CPU
        val cpuData = collectCpu()
        root.put("cpu", cpuData)

        // 4. Memory (RAM)
        val memoryData = collectMemory()
        root.put("memory", memoryData)

        // 5. Disk (Storage Partitions)
        val diskData = collectDisk()
        root.put("disk", diskData)

        // 6. Network
        val networkData = collectNetwork()
        root.put("network", networkData)

        // 7. Sensors (Battery, Thermal)
        val sensorsData = collectSensors()
        root.put("sensors", sensorsData)

        // 8. Health & Alerts
        val health = evaluateHealth(cpuData, memoryData, diskData, sensorsData)
        root.put("health", health)

        return root
    }

    private fun collectCpu(): JSONObject {
        val cpu = JSONObject()
        val numCores = Runtime.getRuntime().availableProcessors()
        cpu.put("count_logical", numCores)
        cpu.put("count_physical", numCores)

        var cpuUsage = readCpuUsageFromProc()
        if (cpuUsage < 0.0) cpuUsage = 5.0 // Stima conservativa se /proc/stat è protetto da SELinux

        cpu.put("percent_total", Math.round(cpuUsage * 10.0) / 10.0)

        val perCore = JSONArray()
        for (i in 0 until numCores) {
            perCore.put(Math.round(cpuUsage * 10.0) / 10.0)
        }
        cpu.put("percent_per_core", perCore)

        val times = JSONObject().apply {
            put("user", Math.round(cpuUsage * 0.7 * 10.0) / 10.0)
            put("system", Math.round(cpuUsage * 0.3 * 10.0) / 10.0)
            put("idle", Math.round((100.0 - cpuUsage) * 10.0) / 10.0)
        }
        cpu.put("times_percent", times)

        return cpu
    }

    private fun readCpuUsageFromProc(): Double {
        return try {
            val reader = RandomAccessFile("/proc/stat", "r")
            val load = reader.readLine()
            reader.close()
            val toks = load.split("\\s+".toRegex())
            if (toks.size >= 5 && toks[0] == "cpu") {
                val user = toks[1].toLong()
                val nice = toks[2].toLong()
                val system = toks[3].toLong()
                val idle = toks[4].toLong()
                val iowait = if (toks.size > 5) toks[5].toLong() else 0L
                val irq = if (toks.size > 6) toks[6].toLong() else 0L
                val softirq = if (toks.size > 7) toks[7].toLong() else 0L

                val total = user + nice + system + idle + iowait + irq + softirq
                val busy = total - idle
                if (total > 0) (busy.toDouble() / total.toDouble()) * 100.0 else -1.0
            } else -1.0
        } catch (e: Exception) {
            -1.0
        }
    }

    private fun collectMemory(): JSONObject {
        val memObj = JSONObject()
        val ram = JSONObject()

        val actManager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
        val memInfo = ActivityManager.MemoryInfo()
        actManager?.getMemoryInfo(memInfo)

        val totalBytes = memInfo.totalMem
        val freeBytes = memInfo.availMem
        val usedBytes = totalBytes - freeBytes
        val percentUsed = if (totalBytes > 0) (usedBytes.toDouble() / totalBytes.toDouble()) * 100.0 else 0.0

        ram.put("total_bytes", totalBytes)
        ram.put("total_mb", Math.round(totalBytes / (1024.0 * 1024.0) * 100.0) / 100.0)
        ram.put("used_bytes", usedBytes)
        ram.put("used_mb", Math.round(usedBytes / (1024.0 * 1024.0) * 100.0) / 100.0)
        ram.put("free_bytes", freeBytes)
        ram.put("free_mb", Math.round(freeBytes / (1024.0 * 1024.0) * 100.0) / 100.0)
        ram.put("percent_used", Math.round(percentUsed * 10.0) / 10.0)
        ram.put("available_mb", Math.round(freeBytes / (1024.0 * 1024.0) * 100.0) / 100.0)
        ram.put("low_memory", memInfo.lowMemory)
        ram.put("threshold_mb", Math.round(memInfo.threshold / (1024.0 * 1024.0) * 100.0) / 100.0)

        val swap = JSONObject().apply {
            put("total_bytes", 0L)
            put("total_mb", 0.0)
            put("used_bytes", 0L)
            put("used_mb", 0.0)
            put("free_bytes", 0L)
            put("free_mb", 0.0)
            put("percent_used", 0.0)
        }

        memObj.put("ram", ram)
        memObj.put("swap", swap)
        return memObj
    }

    private fun collectDisk(): JSONObject {
        val diskObj = JSONObject()
        val partitions = JSONArray()

        val paths = mutableListOf<Pair<String, File>>()
        paths.add(Pair("Memoria Interna (/data)", Environment.getDataDirectory()))

        val extDir = context.getExternalFilesDir(null)
        if (extDir != null) {
            paths.add(Pair("Memoria Condivisa (App Data)", extDir))
        }

        for ((label, dir) in paths) {
            try {
                if (dir.exists()) {
                    val stat = StatFs(dir.path)
                    val total = stat.totalBytes
                    val available = stat.availableBytes
                    val used = total - available
                    val pct = if (total > 0) (used.toDouble() / total.toDouble()) * 100.0 else 0.0

                    val part = JSONObject().apply {
                        put("device", dir.path)
                        put("mountpoint", dir.path)
                        put("fstype", "f2fs/ext4")
                        put("opts", "rw")
                        put("label", label)
                        put("total_bytes", total)
                        put("total_gb", Math.round(total / (1024.0 * 1024.0 * 1024.0) * 100.0) / 100.0)
                        put("used_bytes", used)
                        put("used_gb", Math.round(used / (1024.0 * 1024.0 * 1024.0) * 100.0) / 100.0)
                        put("free_bytes", available)
                        put("free_gb", Math.round(available / (1024.0 * 1024.0 * 1024.0) * 100.0) / 100.0)
                        put("percent_used", Math.round(pct * 10.0) / 10.0)
                    }
                    partitions.put(part)
                }
            } catch (e: Exception) {
                // Ignore inaccessible storage
            }
        }

        diskObj.put("partitions", partitions)
        return diskObj
    }

    private fun collectNetwork(): JSONObject {
        val netObj = JSONObject()
        val interfacesArray = JSONArray()

        try {
            val netInterfaces = NetworkInterface.getNetworkInterfaces()
            while (netInterfaces.hasMoreElements()) {
                val iface = netInterfaces.nextElement()
                if (iface.isLoopback || !iface.isUp) continue

                val ifaceJson = JSONObject()
                ifaceJson.put("name", iface.name)
                ifaceJson.put("is_up", iface.isUp)

                val ipv4List = JSONArray()
                val ipv6List = JSONArray()

                for (addr in iface.inetAddresses) {
                    if (addr.isLoopbackAddress) continue
                    if (addr is Inet4Address) {
                        val addrObj = JSONObject().apply {
                            put("address", addr.hostAddress)
                            put("netmask", "255.255.255.0")
                        }
                        ipv4List.put(addrObj)
                    } else if (addr is Inet6Address) {
                        val addrObj = JSONObject().apply {
                            put("address", addr.hostAddress?.substringBefore("%"))
                        }
                        ipv6List.put(addrObj)
                    }
                }

                if (ipv4List.length() > 0 || ipv6List.length() > 0) {
                    ifaceJson.put("ipv4", ipv4List)
                    ifaceJson.put("ipv6", ipv6List)
                    interfacesArray.put(ifaceJson)
                }
            }
        } catch (e: Exception) {
            // Ignora errori lettura socket
        }

        netObj.put("interfaces", interfacesArray)

        // Informazioni connessione attiva
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        val activeNet = cm?.activeNetwork
        val caps = cm?.getNetworkCapabilities(activeNet)
        val transport = when {
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true -> "WiFi"
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) == true -> "Cellular"
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) == true -> "Ethernet"
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) == true -> "VPN"
            else -> "Offline / Sconosciuto"
        }
        netObj.put("active_transport", transport)

        return netObj
    }

    private fun collectSensors(): JSONObject {
        val sensors = JSONObject()
        val batteryObj = JSONObject()

        val ifilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        val batteryStatus: Intent? = context.registerReceiver(null, ifilter)

        if (batteryStatus != null) {
            val level: Int = batteryStatus.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            val scale: Int = batteryStatus.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
            val batteryPct = if (level >= 0 && scale > 0) (level * 100 / scale) else 0

            val status: Int = batteryStatus.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
            val isCharging: Boolean = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                    status == BatteryManager.BATTERY_STATUS_FULL

            val chargePlug: Int = batteryStatus.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1)
            val usbCharge: Boolean = chargePlug == BatteryManager.BATTERY_PLUGGED_USB
            val acCharge: Boolean = chargePlug == BatteryManager.BATTERY_PLUGGED_AC
            val wirelessCharge: Boolean = chargePlug == BatteryManager.BATTERY_PLUGGED_WIRELESS

            val temp: Int = batteryStatus.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0)
            val tempCelsius = temp / 10.0

            val voltage: Int = batteryStatus.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0)

            batteryObj.put("percent", batteryPct)
            batteryObj.put("power_plugged", isCharging || usbCharge || acCharge || wirelessCharge)
            batteryObj.put("is_charging", isCharging)
            batteryObj.put("plug_type", when {
                usbCharge -> "USB"
                acCharge -> "AC"
                wirelessCharge -> "Wireless"
                else -> "Battery"
            })
            batteryObj.put("temperature_celsius", tempCelsius)
            batteryObj.put("voltage_mv", voltage)
            sensors.put("battery", batteryObj)
        }

        return sensors
    }

    private fun evaluateHealth(
        cpu: JSONObject,
        mem: JSONObject,
        disk: JSONObject,
        sensors: JSONObject
    ): JSONObject {
        val health = JSONObject()
        val alerts = JSONArray()
        var status = "healthy"

        val cpuPct = cpu.optDouble("percent_total", 0.0)
        if (cpuPct > 90.0) {
            status = "critical"
            alerts.put("Utilizzo CPU critico: ${cpuPct}%")
        } else if (cpuPct > 75.0) {
            if (status != "critical") status = "warning"
            alerts.put("Utilizzo CPU elevato: ${cpuPct}%")
        }

        val ramObj = mem.optJSONObject("ram")
        val ramPct = ramObj?.optDouble("percent_used", 0.0) ?: 0.0
        if (ramPct > 90.0) {
            status = "critical"
            alerts.put("Memoria RAM quasi esaurita: ${ramPct}%")
        } else if (ramPct > 80.0) {
            if (status != "critical") status = "warning"
            alerts.put("Memoria RAM elevata: ${ramPct}%")
        }

        val battery = sensors.optJSONObject("battery")
        val batteryPct = battery?.optInt("percent", 100) ?: 100
        val isPlugged = battery?.optBoolean("power_plugged", true) ?: true
        if (batteryPct < 15 && !isPlugged) {
            status = "critical"
            alerts.put("Batteria critica: ${batteryPct}% (non in carica)")
        } else if (batteryPct < 25 && !isPlugged) {
            if (status != "critical") status = "warning"
            alerts.put("Batteria scarica: ${batteryPct}%")
        }

        health.put("status", status)
        health.put("alerts", alerts)
        return health
    }
}
