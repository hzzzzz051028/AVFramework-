/* RK Cast standby view: browser-previewable and dependency-free. */
(() => {
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const demo = params.get('demo') === '1';
  $('demoBadge').classList.toggle('is-visible', demo);

  const slides = [
    { title: '把屏幕，<em>放大</em> 到这里。', description: '连接同一 Wi‑Fi，几秒钟就能把电脑画面带到大屏上。', caption: '零等待的连接' },
    { title: '一块屏幕，<em>共享</em> 所见。', description: '会议、课堂、照片和演示，画面始终清晰、稳定、同步。', caption: '让分享自然发生' },
    { title: 'RK3588，<em>准备就绪。</em>', description: '硬件解码、图形缩放和 HDMI 输出协同工作，只为更流畅的每一帧。', caption: '硬件级低延迟' },
  ];
  let slide = 0;
  let cpuSample = null;
  let interval;

  function setText(id, value, fallback = '--') { $(id).textContent = value ?? fallback; }
  function setMeter(id, value) { $(id).style.width = `${Math.max(0, Math.min(100, Number(value) || 0))}%`; }
  function formatUptime(seconds) {
    const s = Math.max(0, Number(seconds) || 0);
    const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
    return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
  }
  function maxTemperature(temperatures) {
    const values = Object.values(temperatures || {}).map(Number).filter(Number.isFinite);
    return values.length ? Math.max(...values) : null;
  }
  function setSlide(index) {
    slide = (index + slides.length) % slides.length;
    const item = slides[slide];
    $('slideTitle').innerHTML = item.title;
    setText('slideDescription', item.description);
    setText('slideCaption', item.caption);
    setText('slideIndex', String(slide + 1).padStart(2, '0'));
    document.querySelectorAll('.slide-dot').forEach((dot, i) => dot.classList.toggle('is-active', i === slide));
    document.querySelector('.ambient').dataset.slide = String(slide);
  }
  document.querySelectorAll('.slide-dot').forEach((dot) => dot.addEventListener('click', () => setSlide(Number(dot.dataset.slide))));
  setSlide(0);
  interval = window.setInterval(() => setSlide(slide + 1), 11000);

  function renderDevice(info) {
    if (!info) return;
    setText('deviceName', info.name, 'RK Wireless Display');
    setText('ssid', info.ssid, 'RK-Screencast');
    setText('password', info.password, 'RKcast2026');
    setText('address', info.https_url || info.address, 'https://192.168.50.1:8080');
    renderNetwork(info.network);
  }
  function renderNetwork(network) {
    if (!network) return;
    const labels = {
      same_lan: '现有局域网 · 不切网',
      wired_lan: '有线局域网 · 稳定链路',
      standalone_ap: '仅局域网投屏',
      ap_uplink: 'AP + 有线上行',
      offline: '等待网络',
    };
    setText('networkState', labels[network.mode] || network.label || '网络已就绪');
  }
  function renderRuntime(runtime) {
    if (!runtime) return;
    const labels = { ready: '等待连接', connecting: '正在连接', casting: '投屏中', degraded: '需要检查', fault: '设备异常', stopping: '正在停止' };
    setText('statusText', labels[runtime.state] || runtime.state || '等待连接');
    setText('runtimeState', (runtime.state || 'ready').toUpperCase());
    setText('profileValue', `${runtime.adaptation?.recommended_profile?.name || '1080p30'} · adaptive`);
    const active = runtime.state === 'casting';
    $('statusPill').style.color = active ? 'var(--cyan)' : runtime.state === 'degraded' || runtime.state === 'fault' ? 'var(--coral)' : 'var(--safe)';
    $('footerHint').textContent = active ? `正在接收 · ${runtime.active_session_id || 'LIVE'}` : '等待你的画面';
  }
  function renderProduct(product) {
    if (!product) return;
    const active = product.display?.active;
    const perf = product.runtime?.performance;
    const fps = Number(perf?.sender?.fps);
    const kbps = Number(perf?.sender?.kbps);
    if (Number.isFinite(fps)) {
      const quality = perf.verdict === 'pass' ? '稳定' : perf.verdict === 'investigate' ? '检查链路' : '采样中';
      const rate = Number.isFinite(kbps) ? ` · ${Math.round(kbps)}kbps` : '';
      setText('profileValue', `${Math.round(fps)}fps${rate} · ${quality}`);
    }
    if (active) {
      $('footerHint').textContent = `HDMI 输出 · ${String(active.source).toUpperCase()}`;
    }
  }
  function renderSystem(system) {
    if (!system) return;
    const mem = Number(system.memory?.percent);
    if (Number.isFinite(mem)) { setText('memoryValue', `${mem.toFixed(0)}%`); setMeter('memoryMeter', mem); }
    const temp = maxTemperature(system.temperatures);
    if (temp !== null) { setText('tempValue', `${temp.toFixed(0)}°`); setMeter('tempMeter', temp / 100 * 100); }
    if (system.cpu_idle !== undefined && system.cpu_total !== undefined) {
      const current = { idle: Number(system.cpu_idle), total: Number(system.cpu_total) };
      if (cpuSample && current.total > cpuSample.total) {
        const usage = (1 - (current.idle - cpuSample.idle) / (current.total - cpuSample.total)) * 100;
        setText('cpuValue', `${Math.max(0, usage).toFixed(0)}%`); setMeter('cpuMeter', usage);
      }
      cpuSample = current;
    }
    setText('uptimeValue', formatUptime(system.service_uptime));
  }
  function renderStatus(status) {
    const caps = status?.hardware || {};
    const items = [['MPP', caps.mpp_available], ['RGA', caps.rga_available], ['KMS', caps.drm_available]];
    $('capabilities').replaceChildren(...items.map(([label, ready]) => { const el = document.createElement('span'); el.textContent = ready === false ? `${label} · SW` : label; return el; }));
  }
  function demoData() {
    const t = Date.now() / 1000;
    return {
      info: { name: 'RK Wireless Display', ssid: 'RK-Screencast', password: 'RKcast2026', https_url: 'https://192.168.50.1:8080', network: { mode: 'standalone_ap' } },
      runtime: { state: 'ready', adaptation: { recommended_profile: { name: '1080p30' } } },
      system: { memory: { percent: 42 }, temperatures: { soc: 51 + Math.sin(t / 8) * 2 }, cpu_idle: 4400 - Math.round(t * 4), cpu_total: 5100 + Math.round(t * 4), service_uptime: 12784 },
      status: { hardware: { mpp_available: true, rga_available: true, drm_available: true } },
      product: { display: { active: null }, runtime: { performance: { verdict: 'awaiting_stream', sender: {} } } },
    };
  }
  async function getJson(path) { const response = await fetch(path, { cache: 'no-store' }); if (!response.ok) throw new Error(`${response.status}`); return response.json(); }
  async function refresh() {
    if (demo) { const d = demoData(); renderDevice(d.info); renderRuntime(d.runtime); renderSystem(d.system); renderStatus(d.status); renderProduct(d.product); return; }
    const results = await Promise.allSettled(['/api/device-info', '/api/device/runtime', '/api/system', '/api/status', '/api/device/pairing-code', '/api/product/status'].map(getJson));
    const [info, runtime, system, status, pairing, product] = results.map((result) => result.status === 'fulfilled' ? result.value : null);
    renderDevice(info); renderRuntime(runtime); renderSystem(system); renderStatus(status); renderProduct(product);
    setText('pairingCode', pairing?.code, '--------');
    if (results.every((result) => result.status === 'rejected')) { document.body.dataset.offline = 'true'; }
  }
  function updateClock() { const now = new Date(); setText('clock', now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })); }
  const qr = $('wifiQr'); qr.addEventListener('error', () => qr.classList.add('is-failed'));
  updateClock(); window.setInterval(updateClock, 1000); refresh(); window.setInterval(refresh, 2500);
})();
