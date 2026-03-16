from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_home():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Мониторинг ширины металла</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #1a1a1a; color: #eee; font-family: 'Segoe UI', Arial, sans-serif; }

    header {
      background: #111; padding: 14px 24px; border-bottom: 2px solid #333;
      display: flex; align-items: center; gap: 16px;
    }
    header h1 { font-size: 1.2rem; font-weight: 600; }
    #dot { width: 12px; height: 12px; border-radius: 50%; background: #555; flex-shrink: 0; }
    #dot.connected { background: #2ecc71; box-shadow: 0 0 6px #2ecc71; }
    #dot.error { background: #e74c3c; }
    #status-text { font-size: 0.85rem; color: #aaa; }

    /* ── Баннер тревоги ── */
    #alert-banner {
      display: none; padding: 12px 24px; text-align: center;
      font-size: 1rem; font-weight: 600; letter-spacing: 0.04em;
    }
    #alert-banner.alert-wider   { background: #c0392b; color: #fff; }
    #alert-banner.alert-narrower{ background: #e67e22; color: #fff; }
    #alert-banner.alert-ok      { background: #27ae60; color: #fff; }

    /* ── Диалог подтверждения ── */
    #confirm-banner {
      display: none; background: #2c3e50; border-bottom: 2px solid #3498db;
      padding: 14px 24px; align-items: center; gap: 16px; flex-wrap: wrap;
    }
    #confirm-banner.visible { display: flex; }
    #confirm-text { flex: 1; font-size: 0.95rem; }
    #confirm-banner button {
      padding: 8px 22px; border: none; border-radius: 5px;
      font-size: 0.9rem; font-weight: 600; cursor: pointer;
    }
    #btn-yes { background: #2ecc71; color: #111; }
    #btn-no  { background: #e74c3c; color: #fff; }
    #btn-yes:hover { background: #27ae60; }
    #btn-no:hover  { background: #c0392b; }

    /* ── Ручная установка ширины ── */
    #manual-panel {
      background: #1f2b38; border-bottom: 1px solid #2c3e50;
      padding: 10px 24px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    }
    #manual-panel label { font-size: 0.85rem; color: #aaa; }
    #inp-width {
      width: 100px; padding: 6px 10px; background: #2c3e50; border: 1px solid #3d5166;
      border-radius: 4px; color: #eee; font-size: 0.9rem;
    }
    #btn-set-width {
      padding: 6px 18px; background: #3498db; color: #fff;
      border: none; border-radius: 4px; font-size: 0.85rem; font-weight: 600; cursor: pointer;
    }
    #btn-set-width:hover { background: #2980b9; }
    #btn-reset {
      padding: 6px 14px; background: #555; color: #ccc;
      border: none; border-radius: 4px; font-size: 0.85rem; cursor: pointer;
    }
    #btn-reset:hover { background: #666; }
    #monitor-status-label {
      font-size: 0.82rem; color: #888;
    }

    /* ── Основной контент ── */
    main { display: flex; flex-direction: column; align-items: center; padding: 20px; gap: 16px; }
    #canvas-wrap {
      position: relative; width: 100%; max-width: 960px;
      background: #000; border-radius: 8px; overflow: hidden;
    }
    canvas { display: block; width: 100%; height: auto; }
    #overlay {
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      display: flex; align-items: center; justify-content: center;
      background: rgba(0,0,0,0.6); font-size: 1.1rem; color: #aaa;
    }

    /* ── Панель статистики ── */
    #stats {
      width: 100%; max-width: 960px; background: #222;
      border-radius: 8px; padding: 16px 24px;
      display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px;
    }
    .stat { display: flex; flex-direction: column; gap: 4px; }
    .stat label { font-size: 0.72rem; text-transform: uppercase; color: #888; letter-spacing: 0.05em; }
    .stat span { font-size: 1.6rem; font-weight: 700; color: #2ecc71; }
    .stat span.warn  { color: #e74c3c; }
    .stat span.na    { color: #555; font-size: 1.1rem; }
    .stat span.info  { color: #3498db; font-size: 1.2rem; }

    /* ── Мигание при тревоге ── */
    @keyframes flash-red { 0%,100%{opacity:1} 50%{opacity:0.35} }
    .flashing { animation: flash-red 0.6s infinite; }
  </style>
</head>
<body>

  <!-- Шапка -->
  <header>
    <div id="dot"></div>
    <h1>Мониторинг ширины металла</h1>
    <span id="status-text">Подключение…</span>
  </header>

  <!-- Баннер тревоги (шире / уже / норма) -->
  <div id="alert-banner"></div>

  <!-- Диалог подтверждения ширины -->
  <div id="confirm-banner">
    <span id="confirm-text"></span>
    <button id="btn-yes">Да</button>
    <button id="btn-no">Нет</button>
  </div>

  <!-- Ручная установка ширины -->
  <div id="manual-panel">
    <label for="inp-width">Ожидаемая ширина (мм):</label>
    <input id="inp-width" type="number" min="0" step="10" placeholder="напр. 250">
    <button id="btn-set-width">Установить</button>
    <button id="btn-reset">Сбросить</button>
    <span id="monitor-status-label">Состояние: —</span>
  </div>

  <main>
    <div id="canvas-wrap">
      <canvas id="cv"></canvas>
      <div id="overlay">Ожидание кадра…</div>
    </div>
    <div id="stats">
      <div class="stat">
        <label>Ширина (мм)</label>
        <span id="s-width" class="na">—</span>
      </div>
      <div class="stat">
        <label>Ожид. ширина</label>
        <span id="s-expected" class="na">—</span>
      </div>
      <div class="stat">
        <label>Допуск (мм)</label>
        <span id="s-bounds" class="na">—</span>
      </div>
      <div class="stat">
        <label>Уверенность</label>
        <span id="s-conf" class="na">—</span>
      </div>
      <div class="stat">
        <label>FPS</label>
        <span id="s-fps" class="na">—</span>
      </div>
      <div class="stat">
        <label>Статус</label>
        <span id="s-ok" class="na">—</span>
      </div>
    </div>
  </main>

  <script>
    const canvas   = document.getElementById('cv');
    const ctx      = canvas.getContext('2d');
    const overlay  = document.getElementById('overlay');
    const dot      = document.getElementById('dot');
    const statusText = document.getElementById('status-text');

    const sWidth    = document.getElementById('s-width');
    const sExpected = document.getElementById('s-expected');
    const sBounds   = document.getElementById('s-bounds');
    const sConf     = document.getElementById('s-conf');
    const sFps      = document.getElementById('s-fps');
    const sOk       = document.getElementById('s-ok');

    const alertBanner  = document.getElementById('alert-banner');
    const confirmBanner = document.getElementById('confirm-banner');
    const confirmText  = document.getElementById('confirm-text');
    const btnYes       = document.getElementById('btn-yes');
    const btnNo        = document.getElementById('btn-no');
    const inpWidth     = document.getElementById('inp-width');
    const btnSetWidth  = document.getElementById('btn-set-width');
    const btnReset     = document.getElementById('btn-reset');
    const monitorStatusLabel = document.getElementById('monitor-status-label');

    let frameCount = 0;
    let lastFpsTime = performance.now();
    let ws = null;
    let pendingConfirmMm = null;   // значение, ожидающее подтверждения
    let alertHideTimer = null;

    // ── Утилиты ──────────────────────────────────────────────────────────────

    function showAlert(text, cssClass, autohideMs = 0) {
      clearTimeout(alertHideTimer);
      alertBanner.textContent = text;
      alertBanner.className = cssClass;
      alertBanner.style.display = 'block';
      if (autohideMs > 0) {
        alertHideTimer = setTimeout(() => { alertBanner.style.display = 'none'; }, autohideMs);
      }
    }

    function hideAlert() {
      clearTimeout(alertHideTimer);
      alertBanner.style.display = 'none';
    }

    function showConfirm(text, pendingMm) {
      pendingConfirmMm = pendingMm;
      confirmText.textContent = text;
      confirmBanner.classList.add('visible');
    }

    function hideConfirm() {
      pendingConfirmMm = null;
      confirmBanner.classList.remove('visible');
    }

    const STATE_LABELS = {
      idle:       'Ожидание стабильного сигнала…',
      confirming: 'Ожидаем подтверждения ширины…',
      monitoring: 'Контроль активен',
    };

    function applyMonitorState(data) {
      const s = data.state || 'idle';
      monitorStatusLabel.textContent = 'Состояние: ' + (STATE_LABELS[s] || s);

      if (data.expected_mm != null) {
        sExpected.textContent = data.expected_mm.toFixed(0) + ' мм';
        sExpected.className = '';
        if (data.bounds) {
          sBounds.textContent = data.bounds[0].toFixed(0) + '–' + data.bounds[1].toFixed(0);
          sBounds.className = '';
          inpWidth.value = data.expected_mm;
        }
      } else {
        sExpected.textContent = '—';
        sExpected.className = 'na';
        sBounds.textContent = '—';
        sBounds.className = 'na';
      }

      // Если состояние сменилось с confirming — скрываем диалог
      if (s !== 'confirming') {
        hideConfirm();
      }
    }

    // ── Обработка сообщений ───────────────────────────────────────────────────

    function handleMessage(msg) {
      switch (msg.type) {

        case 'frame': {
          if (!msg.data) break;
          overlay.style.display = 'none';

          const img = new Image();
          img.onload = () => {
            canvas.width  = img.naturalWidth;
            canvas.height = img.naturalHeight;
            ctx.drawImage(img, 0, 0);
          };
          img.src = 'data:image/jpeg;base64,' + msg.data;

          // FPS
          frameCount++;
          const now = performance.now();
          if (now - lastFpsTime >= 1000) {
            sFps.textContent = frameCount;
            sFps.className = '';
            frameCount = 0;
            lastFpsTime = now;
          }

          // Метаданные
          const meta = msg.meta || {};
          if (meta.ok === true) {
            const w = meta.width_mm_2dp ?? meta.width_mm;
            sWidth.textContent = w != null ? w.toFixed(2) : '—';
            sWidth.className = '';

            const c = meta.confidence;
            sConf.textContent = c != null ? (c * 100).toFixed(0) + '%' : '—';
            sConf.className = '';

            sOk.textContent = 'OK';
            sOk.className = '';
          } else if (meta.ok === false) {
            sOk.textContent = meta.reason || 'ошибка';
            sOk.className = 'warn';
          }
          break;
        }

        case 'no_frame':
          overlay.style.display = 'flex';
          overlay.textContent = 'Нет кадра…';
          break;

        // Сервер спрашивает: «Сейчас ширина металла XXX мм?»
        case 'width_confirm_request': {
          const suggested = msg.suggested_mm;
          const measured  = msg.measured_mm;
          showConfirm(
            `Сервер видит ширину ~${measured} мм. Подтвердить норму ${suggested} мм?`,
            suggested
          );
          break;
        }

        // Металл вышел за пределы
        case 'width_alert': {
          const dir  = msg.direction === 'wider' ? 'шире нормы' : 'уже нормы';
          const cls  = msg.direction === 'wider' ? 'alert-wider' : 'alert-narrower';
          const text = `⚠ Металл ${dir}: ${msg.width_mm} мм`
                     + ` (норма ${msg.bounds[0]}–${msg.bounds[1]} мм)`;
          showAlert(text, cls);
          canvas.classList.add('flashing');
          break;
        }

        // Металл вернулся в норму
        case 'width_back_in_bounds': {
          const text = `✔ Металл в норме: ${msg.width_mm} мм`
                     + ` (${msg.bounds[0]}–${msg.bounds[1]} мм)`;
          showAlert(text, 'alert-ok', 4000);
          canvas.classList.remove('flashing');
          break;
        }

        // Обновление состояния монитора (после confirm / set / reset)
        case 'width_monitor_state':
          applyMonitorState(msg);
          if (msg.state === 'monitoring') {
            canvas.classList.remove('flashing');
            hideAlert();
          }
          break;
      }
    }

    // ── WebSocket ─────────────────────────────────────────────────────────────

    function connect() {
      ws = new WebSocket(`ws://${location.host}/video/ws`);

      ws.onopen = () => {
        dot.className = 'connected';
        statusText.textContent = 'Подключено';
      };

      ws.onmessage = (evt) => {
        try { handleMessage(JSON.parse(evt.data)); }
        catch(e) { console.error('parse error', e); }
      };

      ws.onerror = () => {
        dot.className = 'error';
        statusText.textContent = 'Ошибка соединения';
      };

      ws.onclose = () => {
        dot.className = '';
        statusText.textContent = 'Отключено, повтор через 3 сек…';
        overlay.style.display = 'flex';
        overlay.textContent = 'Переподключение…';
        setTimeout(connect, 3000);
      };
    }

    function sendMsg(obj) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(obj));
      }
    }

    // ── Кнопки подтверждения ──────────────────────────────────────────────────

    btnYes.addEventListener('click', () => {
      sendMsg({ type: 'confirm_width', confirmed: true, expected_mm: pendingConfirmMm });
      hideConfirm();
    });

    btnNo.addEventListener('click', () => {
      sendMsg({ type: 'confirm_width', confirmed: false });
      hideConfirm();
    });

    // ── Ручная установка ширины ───────────────────────────────────────────────

    btnSetWidth.addEventListener('click', () => {
      const val = parseFloat(inpWidth.value);
      if (!isNaN(val) && val > 0) {
        sendMsg({ type: 'set_width', expected_mm: val });
      }
    });

    inpWidth.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') btnSetWidth.click();
    });

    btnReset.addEventListener('click', () => {
      sendMsg({ type: 'reset_monitor' });
      hideAlert();
      canvas.classList.remove('flashing');
    });

    connect();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
