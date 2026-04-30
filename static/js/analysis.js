// ============================================================
//  Analysis & Controller Page  —  Full port of tkinter GestureUI
//  All calibration, gesture display, chart logic mirrored 1-to-1
// ============================================================

// ─── constants (mirror Python) ──────────────────────────────
const HISTORY      = 300;
const CAL_GESTURES = ["Extend", "Flex", "Fist_Close", "Thumbs_Up", "Thumbs_Down"];
const FSR_COLORS   = ["#FF3366", "#33CCFF", "#FFCC00", "#33FF66", "#9933FF", "#FF9933"];
const RPY_COLORS   = ["#FF0054", "#390099", "#FFBD00"];
const ACC2         = "#38393e";
const WARN         = "#38393e";
const AMBER        = "#38393e";
const ACC          = "#38393e";
const TXT_M        = "#8a8b92";
const TXT_H        = "#38393e";

const GESTURE_META = {
    "Extend":      { emoji: "🖐",  name: "EXTEND"      },
    "Flex":        { emoji: "🤙",  name: "FLEX"        },
    "Fist_Close":  { emoji: "✊",  name: "FIST CLOSE"  },
    "Thumbs_Up":   { emoji: "👍",  name: "THUMBS UP"   },
    "Thumbs_Down": { emoji: "👎",  name: "THUMBS DOWN" },
    "Rest":        { emoji: "🤚",  name: "REST"        },
};

// ─── local state ────────────────────────────────────────────
let fsrChart    = null;
let imuChart    = null;
let fsrBarChart = null;

let thr_on  = 0;
let thr_off = 0;
let calibrated = false;

// Threshold annotations on FSR chart
let thrOnAnnotation  = null;
let thrOffAnnotation = null;

// Span state for gesture window overlay on chart
let spanStartIdx = null;
let spanEndIdx   = null;
let spanLabel    = null;
let spanSampleN  = 0;         // total samples seen
let clearSpanTimer = null;

// local ring buffer (for span drawing)
const fsrHistLen = HISTORY;
let   fsrSampleCount = 0;

// calibration state
let proto_count = {};
CAL_GESTURES.forEach(g => proto_count[g] = 0);

// ─── chart initialisation ───────────────────────────────────
function initCharts() {
    const fsrCtx = document.getElementById('fsr-chart');
    const imuCtx = document.getElementById('imu-chart');
    const barCtx = document.getElementById('fsr-bar-chart');
    if (!fsrCtx || !imuCtx || !barCtx) return;

    const emptyData = Array(HISTORY).fill(null);
    const labels    = Array(HISTORY).fill('');

    // ── FSR time-series ──────────────────────────────────────
    fsrChart = new Chart(fsrCtx, {
        type: 'line',
        data: {
            labels,
            datasets: FSR_COLORS.map((c, i) => ({
                label: `FSR${i+1}`,
                data:  [...emptyData],
                borderColor: c,
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.2,
                fill: false,
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { boxWidth: 12, font: { size: 10 } }
                },
                annotation: { annotations: {} }
            },
            scales: {
                x: { display: false },
                y: {
                    min: 0, max: 10,
                    grid: { color: '#dfd8c7' },
                    ticks: { color: TXT_M, font: { size: 9 } }
                }
            }
        }
    });

    // ── RPY time-series ─────────────────────────────────────
    imuChart = new Chart(imuCtx, {
        type: 'line',
        data: {
            labels,
            datasets: ['Roll','Pitch','Yaw'].map((nm, i) => ({
                label: nm,
                data:  [...emptyData],
                borderColor: RPY_COLORS[i],
                borderWidth: 1.8,
                pointRadius: 0,
                tension: 0.2,
                fill: false,
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { boxWidth: 12, font: { size: 10 } }
                }
            },
            scales: {
                x: { display: false },
                y: {
                    min: -190, max: 190,
                    grid: { color: '#dfd8c7' },
                    ticks: { color: TXT_M, font: { size: 9 } }
                }
            }
        }
    });

    // ── FSR bar chart ────────────────────────────────────────
    fsrBarChart = new Chart(barCtx, {
        type: 'bar',
        data: {
            labels: ['F1','F2','F3','F4','F5','F6'],
            datasets: [{
                label: 'Live FSR',
                data: [0,0,0,0,0,0],
                backgroundColor: FSR_COLORS,
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                y: {
                    min: 0, max: 8,
                    grid: { color: '#dfd8c7' },
                    ticks: { color: TXT_M, font: { size: 9 } }
                },
                x: { ticks: { color: TXT_M, font: { size: 9 } } }
            },
            plugins: { legend: { display: false } }
        }
    });
}

document.addEventListener('DOMContentLoaded', initCharts);

// ─── port management ────────────────────────────────────────
function fetchPortsAnalysis() {
    fetch('/api/ports')
        .then(r => r.json())
        .then(d => {
            const sel = document.getElementById('analysis-port-select');
            if (!sel) return;
            sel.innerHTML = '<option value="">Select Port...</option>';
            (d.ports || []).forEach(p => {
                sel.innerHTML += `<option value="${p}">${p}</option>`;
            });
        })
        .catch(() => {});
}
fetchPortsAnalysis();

// ─── connect / disconnect ────────────────────────────────────
function toggleConnectAnalysis() {
    if (isConnected) {
        socket.emit('disconnect_port');
    } else {
        const port = document.getElementById('analysis-port-select').value;
        if (!port) { appendLog("⚠ No port selected"); return; }
        socket.emit('connect_port', { port });
    }
}

// keep analysis connect button in sync with global isConnected
setInterval(() => {
    const btn = document.getElementById('analysis-connect-btn');
    const sl  = document.getElementById('analysis-conn-status');
    if (!btn) return;
    if (isConnected) {
        btn.textContent = '■  Disconnect';
        btn.style.background = '#DC2626';
        if (sl) { sl.textContent = '⬤  Connected'; sl.style.color = ACC2; }
        // enable baseline cal button
        const bb = document.getElementById('cal-base-btn');
        if (bb) bb.disabled = false;
    } else {
        btn.textContent = '▶  Connect';
        btn.style.background = '#2563EB';
        if (sl) { sl.textContent = '⬤  Disconnected'; sl.style.color = TXT_M; }
        const bb = document.getElementById('cal-base-btn');
        if (bb) bb.disabled = true;
    }
}, 300);

// ─── calibration ─────────────────────────────────────────────
function startCalibration(label) {
    if (!isConnected) { appendLog("⚠ Connect first"); return; }
    socket.emit('start_calibration', { label });
}

// ─── event log helpers ───────────────────────────────────────
function appendLog(msg) {
    const el = document.getElementById('event-log');
    if (!el) return;
    const ts = new Date().toLocaleTimeString();
    el.value += `[${ts}]  ${msg}\n`;
    el.scrollTop = el.scrollHeight;
}

function setCalStat(text, color) {
    const el = document.getElementById('calibration-status');
    if (!el) return;
    el.textContent = text;
    el.style.color  = color || WARN;
}

function setModeLbl(text, color) {
    const el = document.getElementById('analysis-mode-lbl');
    if (!el) return;
    el.textContent = text;
    el.style.color  = color || AMBER;
}

// ─── progress bar ─────────────────────────────────────────────
socket.on('calibration_progress', (d) => {
    const bar  = document.getElementById('cal-progress-bar');
    const stat = document.getElementById('cal-progress-status');
    if (bar)  bar.style.width = d.pct.toFixed(1) + '%';
    if (stat) stat.textContent = `⏺  ${d.mode === 'base' ? 'Rest' : d.mode.replace(/_/g,' ')}…  ${d.rem}s left`;
});

// ─── calibration start ───────────────────────────────────────
socket.on('calibration_start', (d) => {
    const lbl = d.mode === 'base' ? 'Rest' : d.mode.replace(/_/g,' ');
    setCalStat(`⏺  Recording ${lbl}…`, AMBER);
    setModeLbl(`Mode: calibrating ${lbl}`, AMBER);

    const bar  = document.getElementById('cal-progress-bar');
    const stat = document.getElementById('cal-progress-status');
    if (bar)  { bar.style.width = '0%'; bar.style.background = ACC; }
    if (stat) stat.textContent = `⏺  ${lbl}…  ${d.duration}s left`;

    appendLog(`⏺  Recording ${lbl}…`);
});

// ─── calibration done ────────────────────────────────────────
socket.on('calibration_done', (d) => {
    const bar  = document.getElementById('cal-progress-bar');
    const stat = document.getElementById('cal-progress-status');

    if (d.error) {
        setCalStat('⚠ Too few samples — retry', WARN);
        if (bar)  { bar.style.width = '0%'; }
        if (stat) stat.textContent = '⚠ Retry';
        return;
    }

    if (d.mode === 'base') {
        // ── baseline done ──
        setCalStat('✅ Baseline calibrated', ACC2);
        setModeLbl('Mode: gesture calibration', ACC2);
        if (bar)  { bar.style.width = '100%'; bar.style.background = ACC2; }
        if (stat) stat.textContent = '✅ Baseline done';

        const bb = document.getElementById('cal-base-btn');
        if (bb) bb.textContent = '① Re-calibrate Rest';

        // unlock gesture buttons
        CAL_GESTURES.forEach(g => {
            const b = document.getElementById(`cal-${g}-btn`);
            if (b) b.disabled = false;
        });

        // baseline FSR values
        if (d.baseline_fsr) {
            d.baseline_fsr.forEach((v, i) => {
                const el = document.getElementById(`bf-${i}`);
                if (el) el.textContent = `F${i+1}:${v.toFixed(1)}`;
            });
        }
        const tl = document.getElementById('analysis-thr-lbl');
        if (tl) tl.textContent = `on >${d.thr_on.toFixed(1)}   off <${d.thr_off.toFixed(1)}`;

        // store locally for chart threshold lines
        thr_on     = d.thr_on;
        thr_off    = d.thr_off;
        calibrated = true;
        updateFSRChartThresholds();

        appendLog(`Baseline done — on>${d.thr_on.toFixed(1)} off<${d.thr_off.toFixed(1)}`);
        appendLog(`μ=${d.mu.toFixed(1)} σ=${d.sig.toFixed(1)}`);

    } else {
        // ── gesture prototype done ──
        proto_count[d.mode] = d.count;
        const label = d.mode.replace(/_/g,' ');
        setCalStat(`✅ ${label} saved (#${d.count})`, ACC2);
        setModeLbl('Mode: gesture calibration', ACC2);
        if (bar)  { bar.style.width = '100%'; bar.style.background = ACC2; }
        if (stat) stat.textContent = `✅ ${label} saved (#${d.count})`;

        const btn = document.getElementById(`cal-${d.mode}-btn`);
        if (btn) { btn.style.background = ACC2; btn.style.color = 'white'; }

        appendLog(`Prototype → ${d.mode}  set#${d.count}`);

        if (d.all_done) {
            const lb = document.getElementById('cal-live-btn');
            if (lb) { lb.disabled = false; lb.style.opacity = '1'; }
            setCalStat('✅ All 5 gestures calibrated — press ③!', ACC2);
            appendLog('All prototypes ready');
        }
    }
});

// ─── threshold lines on FSR chart ────────────────────────────
function updateFSRChartThresholds() {
    if (!fsrChart || thr_on <= 0) return;

    // update y-axis max if needed
    const currentMax = fsrChart.options.scales.y.max;
    const needed     = thr_on * 1.2;
    if (needed > currentMax) {
        fsrChart.options.scales.y.max = needed;
    }

    // use chartjs-plugin-annotation if available, else draw manually
    if (fsrChart.options.plugins && fsrChart.options.plugins.annotation) {
        fsrChart.options.plugins.annotation.annotations = {
            thrOn: {
                type: 'line', yMin: thr_on, yMax: thr_on,
                borderColor: WARN, borderWidth: 2,
                borderDash: [6,3],
                label: {
                    display: true,
                    content: ` ON>${thr_on.toFixed(1)}`,
                    position: 'start',
                    color: WARN,
                    font: { size: 9, weight: 'bold' },
                    backgroundColor: 'rgba(255,255,255,0.8)',
                }
            },
            thrOff: {
                type: 'line', yMin: thr_off, yMax: thr_off,
                borderColor: AMBER, borderWidth: 1.5,
                borderDash: [4,4],
                label: {
                    display: true,
                    content: ` OFF<${thr_off.toFixed(1)}`,
                    position: 'start',
                    color: AMBER,
                    font: { size: 9 },
                    backgroundColor: 'rgba(255,255,255,0.8)',
                }
            }
        };
    }
    fsrChart.update('none');
}

// ─── window events ───────────────────────────────────────────
socket.on('window_event', (d) => {
    const wl = document.getElementById('analysis-win-lbl');
    if (!wl) return;
    if (d.type === 'open') {
        wl.textContent  = '🔴  Recording...';
        wl.style.color  = WARN;
        spanStartIdx    = fsrSampleCount;
        spanEndIdx      = null;
        spanLabel       = null;
        if (clearSpanTimer) clearTimeout(clearSpanTimer);
    } else if (d.type === 'classifying') {
        wl.textContent  = '⏳  Classifying...';
        wl.style.color  = AMBER;
        spanEndIdx      = fsrSampleCount;
    } else {
        wl.textContent  = '● Idle';
        wl.style.color  = TXT_M;
    }
    updateSpans();
});

// ─── fsr sum live ────────────────────────────────────────────
socket.on('fsr_sum', (d) => {
    const sl = document.getElementById('analysis-fsr-sum');
    if (sl) sl.textContent = `FSR sum: ${d.sum.toFixed(2)}   on>${d.thr_on.toFixed(1)}   off<${d.thr_off.toFixed(1)}`;
});

// ─── gesture result ──────────────────────────────────────────
socket.on('gesture', (d) => {
    // Analysis panel display
    const nameEl  = document.getElementById('analysis-gesture-name');
    const confEl  = document.getElementById('analysis-confidence');
    const imgEl   = document.getElementById('analysis-gesture-img');
    const emoEl   = document.getElementById('analysis-gesture-emoji');
    const winEl   = document.getElementById('analysis-win-lbl');

    const meta = GESTURE_META[d.gesture] || { emoji: '?', name: d.gesture.toUpperCase() };
    const conf = d.confidence || 0;
    const col  = conf > 0.80 ? ACC2 : (conf > 0.55 ? AMBER : WARN);

    const cnnLabel = d.cnn_label !== undefined ? d.cnn_label : '?';
    const cnnConf  = d.cnn_conf !== undefined ? d.cnn_conf : 0;

    if (nameEl)  { nameEl.textContent = meta.name; nameEl.style.color = col; }
    if (confEl)  confEl.textContent = `Final: ${(conf*100).toFixed(1)}%  |  CNN: ${cnnLabel} ${(cnnConf*100).toFixed(1)}%`;
    if (imgEl)   { imgEl.src = `/assets/gestures/${d.gesture}.png`; imgEl.style.opacity = '1'; }
    if (emoEl)   emoEl.textContent = meta.emoji;
    if (winEl)   { winEl.textContent = `✅  ${meta.name}`; winEl.style.color = col; }

    // span annotation label
    spanLabel = meta.name;

    appendLog(`→ ${d.gesture}  final=${conf.toFixed(2)}  CNN=${cnnLabel}:${(cnnConf).toFixed(2)}`);

    // proto scores
    if (d.proto_scores && Object.keys(d.proto_scores).length > 0) {
        const ps = Object.entries(d.proto_scores)
            .sort((a,b)=>b[1]-a[1])
            .map(([k,v])=>`${k}:${v.toFixed(2)}`)
            .join('  ');
        appendLog(`PROTO: ${ps}`);
    }

    // auto-clear span after 4s
    if (clearSpanTimer) clearTimeout(clearSpanTimer);
    clearSpanTimer = setTimeout(() => {
        spanStartIdx = null;
        spanEndIdx   = null;
        spanLabel    = null;
        const wl = document.getElementById('analysis-win-lbl');
        if (wl) { wl.textContent = '● Idle'; wl.style.color = TXT_M; }
        updateSpans();
    }, 4000);
});

// ─── stream data → charts ────────────────────────────────────
socket.on('stream_data', (msg) => {
    if (!fsrChart || !imuChart || !fsrBarChart) return;
    const batch = msg.data;
    if (!batch || batch.length === 0) return;

    const latest = batch[batch.length - 1];

    // ── bar chart ──
    fsrBarChart.data.datasets[0].data = latest.slice(12,18).map(v => Math.max(0, v));
    fsrBarChart.update('none');

    // ── IMU label ──
    const imuEl = document.getElementById('analysis-imu');
    if (imuEl) {
        imuEl.textContent = `Roll: ${latest[0].toFixed(0)}°  |  Pitch: ${latest[1].toFixed(0)}°  |  Yaw: ${latest[2].toFixed(0)}°`;
    }

    // ── rolling push to FSR & IMU charts ──
    batch.forEach(row => {
        fsrSampleCount++;
        for (let i=0; i<6; i++) {
            fsrChart.data.datasets[i].data.shift();
            fsrChart.data.datasets[i].data.push(row[12+i]);
        }
        for (let i=0; i<3; i++) {
            imuChart.data.datasets[i].data.shift();
            imuChart.data.datasets[i].data.push(row[i]);
        }
    });

    updateSpans();
    fsrChart.update('none');
    imuChart.update('none');
});

// ─── draw chart spans ─────────────────────────────────────────
function updateSpans() {
    if (!fsrChart || !imuChart) return;
    
    let boxLive = null;
    let boxDone = null;
    
    if (spanStartIdx !== null) {
        const xStart = HISTORY - 1 - (fsrSampleCount - spanStartIdx);
        const xEnd   = spanEndIdx !== null 
            ? HISTORY - 1 - (fsrSampleCount - spanEndIdx)
            : HISTORY - 1;
            
        if (xEnd >= 0) {
            const isLive = (spanEndIdx === null);
            const box = {
                type: 'box',
                xMin: Math.max(0, xStart),
                xMax: Math.min(HISTORY - 1, xEnd),
                backgroundColor: isLive ? 'rgba(56,57,62,0.1)' : 'rgba(56,57,62,0.2)',
                borderWidth: 0,
                label: {
                    display: !!spanLabel,
                    content: spanLabel || '',
                    position: { x: 'start', y: 'start' },
                    color: '#38393e',
                    font: { weight: 'bold', size: 9 },
                    backgroundColor: 'rgba(248,242,228,0.85)'
                }
            };
            if (isLive) boxLive = box; else boxDone = box;
        }
    }
    // initialize plugin options if needed
    if (!fsrChart.options.plugins) fsrChart.options.plugins = {};
    if (!fsrChart.options.plugins.annotation) fsrChart.options.plugins.annotation = { annotations: {} };
    if (!fsrChart.options.plugins.annotation.annotations) fsrChart.options.plugins.annotation.annotations = {};
    
    const fsrAnns = fsrChart.options.plugins.annotation.annotations;
    if (boxLive) fsrAnns.spanLive = boxLive; else delete fsrAnns.spanLive;
    if (boxDone) fsrAnns.spanDone = boxDone; else delete fsrAnns.spanDone;
    
    if (!imuChart.options.plugins) imuChart.options.plugins = {};
    if (!imuChart.options.plugins.annotation) imuChart.options.plugins.annotation = { annotations: {} };
    if (!imuChart.options.plugins.annotation.annotations) imuChart.options.plugins.annotation.annotations = {};
    
    const imuAnns = imuChart.options.plugins.annotation.annotations;
    if (boxLive) imuAnns.spanLive = boxLive; else delete imuAnns.spanLive;
    if (boxDone) imuAnns.spanDone = boxDone; else delete imuAnns.spanDone;
}

// ─── socket log relay ────────────────────────────────────────
socket.on('log', (d) => appendLog(d.msg));

// ─── calibration enable-live button ─────────────────────────
function enableLiveClassification() {
    if (!calibrated) return;
    setModeLbl('Mode: LIVE classification ●', ACC2);
    appendLog('Live classification active');
}
