/**
 * Sysmon Telemetry Dashboard - Core Client Application
 * Handles API polling, Chart.js time-series rendering, machine selection and process filtering.
 */

// Stato dell'applicazione
const state = {
    machines: [],
    selectedMachineId: null,
    currentSnapshot: null,
    history: [],
    autoRefreshInterval: 5000,
    timerId: null,
    isRefreshing: false,
    dbConnected: true,
    charts: {
        cpuRam: null,
        network: null,
    }
};

// Elementi DOM
const elements = {
    machinesList: document.getElementById('machinesList'),
    searchInput: document.getElementById('searchMachines'),
    totalMachinesCount: document.getElementById('totalMachinesCount'),
    onlineMachinesCount: document.getElementById('onlineMachinesCount'),
    dbStatusPill: document.getElementById('dbStatusPill'),
    dbAlertBanner: document.getElementById('dbAlertBanner'),
    hostName: document.getElementById('hostName'),
    hostOs: document.getElementById('hostOs'),
    hostUptime: document.getElementById('hostUptime'),
    hostHealthBadge: document.getElementById('hostHealthBadge'),
    hostLastSeen: document.getElementById('hostLastSeen'),
    
    // Cards metriche
    cpuValue: document.getElementById('cpuValue'),
    cpuProgress: document.getElementById('cpuProgress'),
    cpuSub: document.getElementById('cpuSub'),
    
    ramValue: document.getElementById('ramValue'),
    ramProgress: document.getElementById('ramProgress'),
    ramSub: document.getElementById('ramSub'),
    
    diskValue: document.getElementById('diskValue'),
    diskProgress: document.getElementById('diskProgress'),
    diskSub: document.getElementById('diskSub'),
    
    netValue: document.getElementById('netValue'),
    netSub: document.getElementById('netSub'),
    
    // Sezioni tabelle
    disksList: document.getElementById('disksList'),
    processesTableBody: document.getElementById('processesTableBody'),
    processSearchInput: document.getElementById('searchProcesses'),
    rawJsonView: document.getElementById('rawJsonView'),
    refreshBtn: document.getElementById('refreshBtn'),
    autoRefreshSelect: document.getElementById('autoRefreshSelect'),
    copyJsonBtn: document.getElementById('copyJsonBtn'),
};

// Inizializzazione all'avvio
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    setupEventListeners();
    fetchFleetData();
    startAutoRefresh();
});

function setupEventListeners() {
    elements.refreshBtn.addEventListener('click', () => {
        elements.refreshBtn.classList.add('spinning');
        fetchFleetData().finally(() => {
            setTimeout(() => elements.refreshBtn.classList.remove('spinning'), 500);
        });
    });

    elements.autoRefreshSelect.addEventListener('change', (e) => {
        state.autoRefreshInterval = parseInt(e.target.value, 10);
        startAutoRefresh();
    });

    elements.searchInput.addEventListener('input', (e) => {
        renderMachinesList(e.target.value.toLowerCase());
    });

    elements.processSearchInput.addEventListener('input', (e) => {
        renderProcessesTable(e.target.value.toLowerCase());
    });

    elements.copyJsonBtn.addEventListener('click', () => {
        if (!state.currentSnapshot) return;
        navigator.clipboard.writeText(JSON.stringify(state.currentSnapshot, null, 2))
            .then(() => {
                const oldText = elements.copyJsonBtn.textContent;
                elements.copyJsonBtn.textContent = '✓ Copiato!';
                setTimeout(() => elements.copyJsonBtn.textContent = oldText, 2000);
            });
    });
}

function startAutoRefresh() {
    if (state.timerId) clearInterval(state.timerId);
    if (state.autoRefreshInterval > 0) {
        state.timerId = setInterval(() => {
            fetchFleetData(false);
        }, state.autoRefreshInterval);
    }
}

// Inizializzazione Grafici Chart.js
function initCharts() {
    const commonChartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400 },
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: {
                labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } }
            },
            tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                titleColor: '#f8fafc',
                bodyColor: '#cbd5e1',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                borderWidth: 1,
                padding: 10,
            }
        },
        scales: {
            x: {
                grid: { color: 'rgba(255, 255, 255, 0.04)' },
                ticks: { color: '#64748b', font: { size: 10 } }
            },
            y: {
                grid: { color: 'rgba(255, 255, 255, 0.04)' },
                ticks: { color: '#64748b', font: { size: 10 } }
            }
        }
    };

    // Grafico CPU e RAM
    const ctxCpuRam = document.getElementById('chartCpuRam').getContext('2d');
    state.charts.cpuRam = new Chart(ctxCpuRam, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'CPU %',
                    data: [],
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 2,
                },
                {
                    label: 'RAM %',
                    data: [],
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 2,
                }
            ]
        },
        options: {
            ...commonChartOptions,
            scales: {
                ...commonChartOptions.scales,
                y: { min: 0, max: 100, ticks: { callback: v => v + '%' } }
            }
        }
    });

    // Grafico Rete Traffico
    const ctxNet = document.getElementById('chartNetwork').getContext('2d');
    state.charts.network = new Chart(ctxNet, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Inviati (MB)',
                    data: [],
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.08)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 2,
                },
                {
                    label: 'Ricevuti (MB)',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 2,
                }
            ]
        },
        options: commonChartOptions
    });
}

// Chiamata API per caricamento macchine
async function fetchFleetData(showLoading = true) {
    try {
        // Controllo salute database
        const healthRes = await fetch('/health');
        state.dbConnected = healthRes.ok;
        updateDbStatus(state.dbConnected);

        const res = await fetch('/api/v1/machines');
        if (!res.ok) throw new Error('Impossibile recuperare macchine');
        
        const machines = await res.json();
        state.machines = machines;

        updateFleetStats();
        renderMachinesList();

        // Seleziona la prima macchina se nessuna è selezionata
        if (!state.selectedMachineId && machines.length > 0) {
            selectMachine(machines[0].machine_id);
        } else if (state.selectedMachineId) {
            // Aggiorna la macchina correntemente visualizzata
            fetchMachineDetails(state.selectedMachineId);
        }
    } catch (err) {
        console.warn('Errore connessione flotta (PostgreSQL potrebbe essere in fase di avvio):', err);
        state.dbConnected = false;
        updateDbStatus(false);
        renderDemoIfEmpty();
    }
}

function updateDbStatus(isConnected) {
    if (isConnected) {
        elements.dbStatusPill.innerHTML = '<span class="pulse-indicator"></span> <span>PostgreSQL Connesso</span>';
        elements.dbAlertBanner.style.display = 'none';
    } else {
        elements.dbStatusPill.innerHTML = '<span class="pulse-indicator offline"></span> <span>PostgreSQL Non Connesso</span>';
        elements.dbAlertBanner.style.display = 'flex';
    }
}

function updateFleetStats() {
    const total = state.machines.length;
    const online = state.machines.filter(m => m.is_online).length;
    elements.totalMachinesCount.textContent = total;
    elements.onlineMachinesCount.textContent = online;
}

// Rendering lista macchine nella sidebar
function renderMachinesList(filterQuery = '') {
    elements.machinesList.innerHTML = '';

    const filtered = state.machines.filter(m => {
        const text = `${m.hostname} ${m.os} ${m.machine_id}`.toLowerCase();
        return text.includes(filterQuery);
    });

    if (filtered.length === 0) {
        elements.machinesList.innerHTML = `
            <div style="text-align: center; padding: 24px; color: var(--text-dim);">
                Nessuna macchina trovata
            </div>
        `;
        return;
    }

    filtered.forEach(m => {
        const isSelected = m.machine_id === state.selectedMachineId;
        const card = document.createElement('div');
        card.className = `machine-card ${isSelected ? 'active' : ''}`;
        card.onclick = () => selectMachine(m.machine_id);

        const cpuPct = Math.round(m.cpu_percent_total || 0);
        const ramPct = Math.round(m.ram_percent || 0);
        const isOnline = m.is_online;

        card.innerHTML = `
            <div class="machine-card-head">
                <span class="machine-name">
                    <svg style="width:16px;height:16px;fill:currentColor;" viewBox="0 0 24 24"><path d="M20 18c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zM4 6h16v10H4V6z"/></svg>
                    ${escapeHtml(m.hostname)}
                </span>
                <span class="badge-status ${isOnline ? 'online' : 'offline'}">
                    ${isOnline ? 'ONLINE' : 'OFFLINE'}
                </span>
            </div>
            <div class="machine-meta">
                <span>${escapeHtml(m.os)} ${escapeHtml(m.architecture || '')}</span>
                <span>${m.health_status ? m.health_status.toUpperCase() : 'OK'}</span>
            </div>
            <div class="machine-bars">
                <div class="mini-bar-group">
                    <div class="mini-bar-label"><span>CPU</span><span>${cpuPct}%</span></div>
                    <div class="mini-bar-track">
                        <div class="mini-bar-fill" style="width:${cpuPct}%; background:${getColorForPct(cpuPct)};"></div>
                    </div>
                </div>
                <div class="mini-bar-group">
                    <div class="mini-bar-label"><span>RAM</span><span>${ramPct}%</span></div>
                    <div class="mini-bar-track">
                        <div class="mini-bar-fill" style="width:${ramPct}%; background:${getColorForPct(ramPct)};"></div>
                    </div>
                </div>
            </div>
        `;
        elements.machinesList.appendChild(card);
    });
}

// Selezione macchina e caricamento dettagli
async function selectMachine(machineId) {
    state.selectedMachineId = machineId;
    renderMachinesList(); // aggiorna classe 'active'
    await fetchMachineDetails(machineId);
    await fetchMachineHistory(machineId);
}

async function fetchMachineDetails(machineId) {
    try {
        const res = await fetch(`/api/v1/machines/${encodeURIComponent(machineId)}`);
        if (!res.ok) return;
        const snapshot = await res.json();
        state.currentSnapshot = snapshot;
        renderSnapshotDetails(snapshot);
    } catch (err) {
        console.error('Errore lettura dettagli macchina:', err);
    }
}

async function fetchMachineHistory(machineId) {
    try {
        const res = await fetch(`/api/v1/machines/${encodeURIComponent(machineId)}/history?limit=30`);
        if (!res.ok) return;
        const data = await res.json();
        state.history = (data.data || []).reverse(); // ordine cronologico per grafici
        updateCharts(state.history);
    } catch (err) {
        console.error('Errore lettura storico:', err);
    }
}

// Aggiornamento interfaccia con i dati dello snapshot
function renderSnapshotDetails(snapshot) {
    const sys = snapshot.system || {};
    const meta = snapshot.metadata || {};
    const cpu = snapshot.cpu || {};
    const mem = snapshot.memory || {};
    const ram = mem.ram || {};
    const swap = mem.swap || {};
    const disk = snapshot.disk || {};
    const net = snapshot.network || {};
    const health = snapshot.health || {};
    const procs = snapshot.processes || {};

    // Header Host
    elements.hostName.textContent = sys.hostname || meta.hostname || 'Sconosciuto';
    elements.hostOs.textContent = `${sys.os || ''} ${sys.os_release || ''} (${sys.architecture || ''})`;
    elements.hostUptime.textContent = sys.uptime_human ? `Uptime: ${sys.uptime_human}` : '';
    elements.hostLastSeen.textContent = meta.timestamp_utc ? `Ultimo invio: ${new Date(meta.timestamp_utc).toLocaleTimeString()}` : '';

    const healthStatus = health.status || 'healthy';
    elements.hostHealthBadge.textContent = healthStatus.toUpperCase();
    elements.hostHealthBadge.className = `badge-status ${healthStatus === 'healthy' ? 'online' : (healthStatus === 'critical' ? 'danger' : 'warning')}`;

    // CPU Card
    const cpuPct = Math.round(cpu.percent_total || 0);
    elements.cpuValue.textContent = cpuPct;
    elements.cpuProgress.style.width = `${cpuPct}%`;
    elements.cpuProgress.style.background = getColorForPct(cpuPct);
    elements.cpuSub.textContent = `${cpu.count_logical || 0} Core | ${cpu.frequency_mhz?.current || '-'} MHz`;

    // RAM Card
    const ramPct = Math.round(ram.percent_used || 0);
    elements.ramValue.textContent = ramPct;
    elements.ramProgress.style.width = `${ramPct}%`;
    elements.ramProgress.style.background = getColorForPct(ramPct);
    elements.ramSub.textContent = `${ram.used_mb || 0} MB / ${ram.total_mb || 0} MB`;

    // Disk Card
    const partitions = disk.partitions || [];
    let maxDiskPct = 0;
    if (partitions.length > 0) {
        maxDiskPct = Math.round(partitions[0].percent_used || 0);
    }
    elements.diskValue.textContent = maxDiskPct;
    elements.diskProgress.style.width = `${maxDiskPct}%`;
    elements.diskProgress.style.background = getColorForPct(maxDiskPct);
    elements.diskSub.textContent = `${partitions.length} partizioni montate`;

    // Network Card
    const netTotal = net.io_total || {};
    elements.netValue.textContent = Math.round(netTotal.mb_recv || 0);
    elements.netSub.textContent = `Inviati: ${Math.round(netTotal.mb_sent || 0)} MB`;

    // Dischi Lista
    renderDisksList(partitions);

    // Processi Table
    renderProcessesTable();

    // Raw JSON
    elements.rawJsonView.textContent = JSON.stringify(snapshot, null, 2);
}

function renderDisksList(partitions) {
    elements.disksList.innerHTML = '';
    if (partitions.length === 0) {
        elements.disksList.innerHTML = '<p style="color:var(--text-dim);">Nessun disco rilevato</p>';
        return;
    }

    partitions.forEach(p => {
        const item = document.createElement('div');
        item.style.cssText = 'background:var(--bg-glass); border:1px solid var(--border-glass); border-radius:var(--radius-sm); padding:10px 14px; margin-bottom:8px;';
        const pct = Math.round(p.percent_used || 0);
        item.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                <span style="font-weight:600; color:var(--text-main);">${escapeHtml(p.mountpoint)} (${escapeHtml(p.device)})</span>
                <span style="color:${getColorForPct(pct)}; font-weight:700;">${pct}% (${p.used_gb} / ${p.total_gb} GB)</span>
            </div>
            <div style="height:6px; background:rgba(255,255,255,0.06); border-radius:4px; overflow:hidden;">
                <div style="height:100%; width:${pct}%; background:${getColorForPct(pct)};"></div>
            </div>
        `;
        elements.disksList.appendChild(item);
    });
}

function renderProcessesTable(filterQuery = '') {
    const procs = state.currentSnapshot?.processes?.top_processes || [];
    elements.processesTableBody.innerHTML = '';

    const filtered = procs.filter(p => {
        const text = `${p.name} ${p.pid} ${p.username || ''}`.toLowerCase();
        return text.includes(filterQuery);
    });

    if (filtered.length === 0) {
        elements.processesTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-dim); padding:20px;">Nessun processo corrispondente</td></tr>`;
        return;
    }

    filtered.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="proc-pid">${p.pid}</td>
            <td class="proc-name">${escapeHtml(p.name)}</td>
            <td>${escapeHtml(p.username || '-')}</td>
            <td><span class="badge-status online" style="font-size:9px;">${escapeHtml(p.status || 'running')}</span></td>
            <td style="color:${getColorForPct(p.cpu_percent)}; font-weight:600;">${p.cpu_percent}%</td>
            <td>${p.memory_percent}%</td>
            <td>${p.memory_rss_mb || '-'} MB</td>
        `;
        elements.processesTableBody.appendChild(tr);
    });
}

function updateCharts(history) {
    if (!history || history.length === 0) return;

    const labels = history.map(h => {
        const d = new Date(h.timestamp_utc || h.created_at);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    });

    const cpuData = history.map(h => h.cpu_percent_total || 0);
    const ramData = history.map(h => h.ram_percent || 0);
    const netSent = history.map(h => Math.round((h.net_bytes_sent || 0) / (1024 * 1024)));
    const netRecv = history.map(h => Math.round((h.net_bytes_recv || 0) / (1024 * 1024)));

    // Aggiornamento CPU/RAM Chart
    state.charts.cpuRam.data.labels = labels;
    state.charts.cpuRam.data.datasets[0].data = cpuData;
    state.charts.cpuRam.data.datasets[1].data = ramData;
    state.charts.cpuRam.update();

    // Aggiornamento Network Chart
    state.charts.network.data.labels = labels;
    state.charts.network.data.datasets[0].data = netSent;
    state.charts.network.data.datasets[1].data = netRecv;
    state.charts.network.update();
}

// Fallback dimostrativo se PostgreSQL non è ancora collegato
function renderDemoIfEmpty() {
    if (state.machines.length > 0) return;

    const demoMachine = {
        machine_id: 'LOCAL-NODE-PREVIEW',
        hostname: 'Nodo-Locale-Anteprima',
        os: 'Windows 11 / Linux',
        architecture: 'x86_64',
        is_online: false,
        health_status: 'healthy',
        cpu_percent_total: 18.5,
        ram_percent: 54.2,
    };

    state.machines = [demoMachine];
    updateFleetStats();
    renderMachinesList();
}

function getColorForPct(pct) {
    if (pct >= 90) return 'var(--danger)';
    if (pct >= 75) return 'var(--warning)';
    return 'var(--primary)';
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/* Gestione Modal Installazione Sonda Remota */
window.openInstallModal = function() {
    const modal = document.getElementById('installModal');
    if (modal) modal.style.display = 'flex';
};

window.closeInstallModal = function() {
    const modal = document.getElementById('installModal');
    if (modal) modal.style.display = 'none';
};

window.copyInstallCmd = function(text, buttonEl) {
    navigator.clipboard.writeText(text).then(() => {
        const originalText = buttonEl.textContent;
        buttonEl.textContent = 'Copiato!';
        buttonEl.style.background = 'rgba(16, 185, 129, 0.3)';
        buttonEl.style.color = '#34d399';
        setTimeout(() => {
            buttonEl.textContent = originalText;
            buttonEl.style.background = '';
            buttonEl.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Errore durante la copia:', err);
    });
};
