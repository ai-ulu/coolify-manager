"""
Web Dashboard - Flask Web Interface
Tarayıcıdan yönetim paneli
"""

from flask import Flask, jsonify, render_template_string
import psutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

app = Flask(__name__)

# HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🐫 Coolify Manager</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', system-ui, sans-serif; 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh; color: #fff;
        }
        .header {
            background: rgba(0,0,0,0.3);
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 1.5rem; }
        .status-badge {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8rem;
        }
        .status-ok { background: #10b981; }
        .container { padding: 20px; }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        
        .card h3 { 
            color: #94a3b8;
            font-size: 0.85rem;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        
        .metric {
            font-size: 2.5rem;
            font-weight: bold;
        }
        
        .metric-cpu { color: #f59e0b; }
        .metric-ram { color: #8b5cf6; }
        .metric-disk { color: #06b6d4; }
        .metric-net { color: #10b981; }
        
        .progress-bar {
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            margin-top: 10px;
            overflow: hidden;
        }
        
        .progress {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        
        .cpu-bar { background: linear-gradient(90deg, #f59e0b, #ef4444); }
        .ram-bar { background: linear-gradient(90deg, #8b5cf6, #d946ef); }
        .disk-bar { background: linear-gradient(90deg, #06b6d4, #3b82f6); }
        
        .chart-container {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }
        
        .process-list {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
        }
        
        .process-item {
            display: flex;
            justify-content: space-between;
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .process-item:last-child { border: none; }
        
        .actions {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 20px;
        }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.2s;
        }
        
        .btn:hover { transform: scale(1.05); }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-success { background: #10b981; color: white; }
        .btn-danger { background: #ef4444; color: white; }
        
        .alert-box {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid #ef4444;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            display: none;
        }
        
        .alert-box.show { display: block; }
        
        .refresh-info {
            text-align: center;
            color: #64748b;
            font-size: 0.8rem;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐫 Coolify Manager</h1>
        <span class="status-badge status-ok">● Sistem Aktif</span>
    </div>
    
    <div class="container">
        <div id="alerts" class="alert-box"></div>
        
        <div class="grid">
            <div class="card">
                <h3>💻 CPU</h3>
                <div class="metric metric-cpu" id="cpu-value">0%</div>
                <div class="progress-bar">
                    <div class="progress cpu-bar" id="cpu-bar" style="width: 0%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>🧠 RAM</h3>
                <div class="metric metric-ram" id="ram-value">0%</div>
                <div class="progress-bar">
                    <div class="progress ram-bar" id="ram-bar" style="width: 0%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>💾 Disk</h3>
                <div class="metric metric-disk" id="disk-value">0%</div>
                <div class="progress-bar">
                    <div class="progress disk-bar" id="disk-bar" style="width: 0%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>📶 Network</h3>
                <div class="metric metric-net" id="net-value">0 MB</div>
                <small id="net-detail">↑0 ↓0</small>
            </div>
        </div>
        
        <div class="chart-container">
            <h3>📈 Son 1 Saat</h3>
            <canvas id="metricsChart" height="80"></canvas>
        </div>
        
        <div class="process-list">
            <h3>🔥 En Çok Kaynak Kullanan Processler</h3>
            <div id="process-list"></div>
        </div>
        
        <div class="actions">
            <button class="btn btn-primary" onclick="refreshData()">🔄 Yenile</button>
            <button class="btn btn-success" onclick="runBackup()">💾 Yedekle</button>
            <button class="btn btn-danger" onclick="cleanup()">🧹 Temizle</button>
        </div>
        
        <div class="refresh-info">
            Son güncelleme: <span id="last-update">-</span>
        </div>
    </div>
    
    <script>
        let chart;
        
        function initChart() {
            const ctx = document.getElementById('metricsChart').getContext('2d');
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Array(60).fill(''),
                    datasets: [
                        {
                            label: 'CPU %',
                            data: Array(60).fill(0),
                            borderColor: '#f59e0b',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: 'RAM %',
                            data: Array(60).fill(0),
                            borderColor: '#8b5cf6',
                            backgroundColor: 'rgba(139, 92, 246, 0.1)',
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: 'Disk %',
                            data: Array(60).fill(0),
                            borderColor: '#06b6d4',
                            backgroundColor: 'rgba(6, 182, 212, 0.1)',
                            fill: true,
                            tension: 0.4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { position: 'top' } },
                    scales: {
                        y: { beginAtZero: true, max: 100 }
                    }
                }
            });
        }
        
        async function refreshData() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                
                // Update metrics
                document.getElementById('cpu-value').textContent = data.cpu.percent + '%';
                document.getElementById('cpu-bar').style.width = data.cpu.percent + '%';
                
                document.getElementById('ram-value').textContent = data.ram.percent + '%';
                document.getElementById('ram-bar').style.width = data.ram.percent + '%';
                
                document.getElementById('disk-value').textContent = data.disk.percent + '%';
                document.getElementById('disk-bar').style.width = data.disk.percent + '%';
                
                const net = data.network;
                document.getElementById('net-value').textContent = Math.round(net.bytes_recv / 1024 / 1024) + ' MB';
                document.getElementById('net-detail').textContent = 
                    '↑' + Math.round(net.bytes_sent / 1024) + 'KB ↓' + Math.round(net.bytes_recv / 1024) + 'KB';
                
                // Update chart
                chart.data.datasets[0].data.shift();
                chart.data.datasets[0].data.push(data.cpu.percent);
                chart.data.datasets[1].data.shift();
                chart.data.datasets[1].data.push(data.ram.percent);
                chart.data.datasets[2].data.shift();
                chart.data.datasets[2].data.push(data.disk.percent);
                chart.update();
                
                // Update processes
                const processList = document.getElementById('process-list');
                processList.innerHTML = data.processes.map(p => 
                    '<div class="process-item"><span>' + p.name + '</span><span>CPU: ' + p.cpu + '% | RAM: ' + p.memory + '%</span></div>'
                ).join('');
                
                // Alerts
                const alerts = [];
                if (data.cpu.percent > 80) alerts.push('⚠️ Yüksek CPU: ' + data.cpu.percent + '%');
                if (data.ram.percent > 80) alerts.push('⚠️ Yüksek RAM: ' + data.ram.percent + '%');
                if (data.disk.percent > 80) alerts.push('⚠️ Yüksek Disk: ' + data.disk.percent + '%');
                
                const alertBox = document.getElementById('alerts');
                if (alerts.length > 0) {
                    alertBox.innerHTML = alerts.join('<br>');
                    alertBox.classList.add('show');
                } else {
                    alertBox.classList.remove('show');
                }
                
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString('tr-TR');
                
            } catch (e) {
                console.error('Veri hatası:', e);
            }
        }
        
        async function runBackup() {
            alert('💾 Yedekleme başlatıldı!');
        }
        
        async function cleanup() {
            alert('🧹 Temizlik başlatıldı!');
        }
        
        initChart();
        refreshData();
        setInterval(refreshData, 5000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Dashboard ana sayfası"""
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/metrics')
def api_metrics():
    """API endpoint - metrikler"""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        
        # Top processes
        processes = []
        for p in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
            try:
                info = p.info
                if info['cpu_percent'] or info['memory_percent']:
                    processes.append({
                        'name': info['name'][:30],
                        'cpu': round(info['cpu_percent'] or 0, 1),
                        'memory': round(info['memory_percent'] or 0, 1)
                    })
            except:
                pass
        
        processes.sort(key=lambda x: x['cpu'], reverse=True)
        processes = processes[:10]
        
        return jsonify({
            'cpu': {'percent': round(cpu, 1)},
            'ram': {'percent': round(ram.percent, 1), 'used': round(ram.used / 1024**3, 1), 'total': round(ram.total / 1024**3, 1)},
            'disk': {'percent': round(disk.percent, 1), 'used': round(disk.used / 1024**3, 1), 'total': round(disk.total / 1024**3, 1)},
            'network': {'bytes_sent': net.bytes_sent, 'bytes_recv': net.bytes_recv},
            'processes': processes,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/actions/<action>')
def api_actions(action):
    """API endpoint - eylemler"""
    return jsonify({'status': 'ok', 'action': action})


def run_dashboard(host='0.0.0.0', port=5000):
    """Dashboard'u çalıştırır"""
    logger.info(f"🌐 Dashboard başlatılıyor: http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    run_dashboard()
