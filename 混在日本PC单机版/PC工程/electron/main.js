/**
 * ============================================================================
 * 《混在日本》PC 单机版 · Electron 主进程
 * ============================================================================
 * 职责
 *   1. 创建无边框/可全屏的游戏窗口（竖屏比例）
 *   2. 实现 JS ↔ 原生 桥（对应原 APK 的 jsbridge_android 协议）
 *   3. 彻底的离线保障：拦截一切外部网络请求
 *   4. 本地存档落盘（localStorage 之外的双保险，防清缓存丢档）
 * ============================================================================
 */
const { app, BrowserWindow, ipcMain, dialog, shell, screen, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

// ============================ 常量 ============================
const APP_NAME = '混在日本';
const APP_VERSION = '4.0.0';
const CHANNEL = 'pc';
const MARKET_CHANNEL = 'windows';
const APP_LG = 'zh';
const PK_NAME = 'com.hao.hun2';

const IS_DEV = process.argv.includes('--dev');

// ============================ 启动开关（离线强化）============================
// 说明：Electron/Chromium 自身会做一些后台网络活动（组件更新检查、指标上报、
// SSL 会话恢复等）。这些流量与游戏无关，但在「完全离线」的验收标准下必须消除。
// 下面这批开关直接关闭这些能力，配合 session.webRequest 拦截，做到真正的零外联。
app.commandLine.appendSwitch('disable-background-networking');       // 关闭后台联网
app.commandLine.appendSwitch('disable-component-update');            // 关闭组件更新
app.commandLine.appendSwitch('disable-domain-reliability');          // 关闭域名可靠性探测
app.commandLine.appendSwitch('disable-client-side-phishing-detection'); // 关闭钓鱼检测上报
app.commandLine.appendSwitch('disable-sync');                        // 关闭同步
app.commandLine.appendSwitch('disable-default-apps');
app.commandLine.appendSwitch('no-first-run');
app.commandLine.appendSwitch('no-default-browser-check');
app.commandLine.appendSwitch('disable-features',
    'Translate,OptimizationHints,MediaRouter,CalculateNativeWinOcclusion,AutofillServerCommunication,NetworkTimeServiceQuerying,InterestFeedContentSuggestions');
app.commandLine.appendSwitch('metrics-recording-only');
app.commandLine.appendSwitch('force-fieldtrials', '');

// 存档目录（用户数据目录，卸载不丢）
const USER_DATA = app.getPath('userData');
const SAVE_DIR = path.join(USER_DATA, 'saves');
const SETTINGS_FILE = path.join(USER_DATA, 'settings.json');

let mainWindow = null;

// ============================ 离线保障 ============================
/**
 * 允许的协议：仅本地文件。
 * 任何 http/https/ws/wss 请求一律拒绝，确保「完全离线」。
 */
function isBlocked(url) {
    if (!url) return false;
    if (url.startsWith('file://')) return false;
    if (url.startsWith('devtools://')) return false;
    if (url.startsWith('chrome-extension://')) return false;
    if (url.startsWith('blob:') || url.startsWith('data:')) return false;
    if (url.startsWith('about:')) return false;
    if (IS_DEV && url.startsWith('http://localhost')) return false;
    return /^(https?|wss?|ftp):/i.test(url);
}

function installOfflineGuard(session) {
    // 拦截所有网络请求
    session.webRequest.onBeforeRequest({ urls: ['*://*/*'] }, (details, callback) => {
        if (isBlocked(details.url)) {
            console.log('[离线保障] 已拦截外网请求:', details.url);
            return callback({ cancel: true });
        }
        callback({ cancel: false });
    });
}

// ============================ 窗口 ============================
function createWindow() {
    const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;

    // 竖屏游戏：按 9:16 计算窗口尺寸，高度取屏幕 92%
    let winH = Math.floor(sh * 0.92);
    let winW = Math.floor(winH * 9 / 16);
    if (winW > sw * 0.92) {
        winW = Math.floor(sw * 0.92);
        winH = Math.floor(winW * 16 / 9);
    }

    mainWindow = new BrowserWindow({
        width: winW,
        height: winH,
        minWidth: 420,
        minHeight: 746,
        backgroundColor: '#000000',
        title: APP_NAME,
        show: false,
        autoHideMenuBar: true,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: false,
            webSecurity: true,
            backgroundThrottling: false,
            // 允许 webview 内的 autoplay（游戏音频）
            autoplayPolicy: 'no-user-gesture-required'
        }
    });

    // 菜单栏（保留少量必要项）
    Menu.setApplicationMenu(Menu.buildFromTemplate([
        {
            label: '游戏',
            submenu: [
                { label: '重新开始', click: () => mainWindow.webContents.send('menu-restart') },
                { label: '存档目录', click: () => shell.openPath(SAVE_DIR) },
                { type: 'separator' },
                { label: '退出', role: 'quit' }
            ]
        },
        {
            label: '视图',
            submenu: [
                { label: '全屏 (F11)', role: 'togglefullscreen' },
                { label: '放大', role: 'zoomIn' },
                { label: '缩小', role: 'zoomOut' },
                { label: '重置缩放', role: 'resetZoom' },
                { type: 'separator' },
                { label: '开发者工具 (F12)', role: 'toggleDevTools', visible: IS_DEV }
            ]
        },
        {
            label: '帮助',
            submenu: [
                { label: `关于 ${APP_NAME}`, click: showAbout },
                { label: '操作说明', click: () => shell.openPath(path.join(__dirname, '..', 'README.md')) }
            ]
        }
    ]));

    // 离线保障
    installOfflineGuard(mainWindow.webContents.session);

    // 阻止新窗口 / 外链跳转
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        console.log('[离线保障] 阻止新窗口:', url);
        return { action: 'deny' };
    });
    mainWindow.webContents.on('will-navigate', (e, url) => {
        if (isBlocked(url)) {
            console.log('[离线保障] 阻止导航:', url);
            e.preventDefault();
        }
    });

    // 禁用拖拽打开文件
    mainWindow.webContents.on('will-navigate', (e) => e.preventDefault());

    mainWindow.loadFile(path.join(__dirname, '..', 'www', 'index.html'));

    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        if (IS_DEV) mainWindow.webContents.openDevTools({ mode: 'detach' });
    });

    mainWindow.on('closed', () => { mainWindow = null; });
}

function showAbout() {
    dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: `关于 ${APP_NAME}`,
        message: `${APP_NAME}  PC 单机版`,
        detail:
            `版本：${APP_VERSION}\n` +
            `运行模式：完全离线单机\n` +
            `存档位置：${SAVE_DIR}\n\n` +
            `本游戏为单机版，无需联网即可游玩。`,
        buttons: ['确定']
    });
}

// ============================ JS ↔ 原生 桥 ============================
/**
 * 对应原 APK 的 jsbridge_android.callbackJs(cmd&key=value) 协议。
 * renderer 侧通过 preload 暴露的 window.hunNative 调用。
 */
function setupBridge() {
    // ---- 存档落盘 ----
    ipcMain.handle('native:save', (_e, payload) => {
        try {
            fs.mkdirSync(SAVE_DIR, { recursive: true });
            const file = path.join(SAVE_DIR, 'save.json');
            const tmp = file + '.tmp';
            fs.writeFileSync(tmp, JSON.stringify(payload), 'utf-8');
            fs.renameSync(tmp, file);
            return { ok: true, path: file };
        } catch (e) {
            return { ok: false, error: String(e) };
        }
    });

    ipcMain.handle('native:load', () => {
        try {
            const file = path.join(SAVE_DIR, 'save.json');
            if (!fs.existsSync(file)) return { ok: false, empty: true };
            const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
            return { ok: true, data };
        } catch (e) {
            return { ok: false, error: String(e) };
        }
    });

    ipcMain.handle('native:hasSave', () => {
        try {
            return fs.existsSync(path.join(SAVE_DIR, 'save.json'));
        } catch (e) { return false; }
    });

    ipcMain.handle('native:clearSave', () => {
        try {
            const file = path.join(SAVE_DIR, 'save.json');
            if (fs.existsSync(file)) fs.unlinkSync(file);
            return { ok: true };
        } catch (e) { return { ok: false, error: String(e) }; }
    });

    // ---- 设置持久化 ----
    ipcMain.handle('native:saveSettings', (_e, s) => {
        try {
            fs.writeFileSync(SETTINGS_FILE, JSON.stringify(s, null, 2), 'utf-8');
            return { ok: true };
        } catch (e) { return { ok: false, error: String(e) }; }
    });

    ipcMain.handle('native:loadSettings', () => {
        try {
            if (!fs.existsSync(SETTINGS_FILE)) return { ok: false, empty: true };
            return { ok: true, data: JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf-8')) };
        } catch (e) { return { ok: false, error: String(e) }; }
    });

    // ---- 设备/系统信息（对应原 getSystemMemory / uuid / base_url 等）----
    ipcMain.handle('native:sysinfo', () => ({
        uuid: getStableUuid(),
        channel: CHANNEL,
        market_channel: MARKET_CHANNEL,
        app_version: APP_VERSION,
        app_lg: APP_LG,
        pkname: PK_NAME,
        platform: process.platform,
        arch: process.arch,
        totalMemory: os.totalmem(),
        freeMemory: os.freemem(),
        hostname: os.hostname(),
        isOffline: true
    }));

    // ---- 外链（离线模式下仅打开纯文本提示，不允许真实跳转）----
    ipcMain.handle('native:outlink', async (_e, url) => {
        if (isBlocked(url)) {
            await dialog.showMessageBox(mainWindow, {
                type: 'info',
                title: '离线模式',
                message: '当前为完全离线版本，无法打开外部链接。',
                detail: String(url || ''),
                buttons: ['确定']
            });
            return { ok: false, blocked: true };
        }
        return { ok: false, blocked: true };
    });

    // ---- 支付（D1：暂删，仅预留框架）----
    ipcMain.handle('native:pay', async (_e, productId) => {
        console.log('[支付] 收到购买请求（未启用）:', productId);
        return { ok: false, code: 'IAP_NOT_AVAILABLE' };
    });

    // ---- 窗口控制 ----
    ipcMain.handle('native:toggleFullscreen', () => {
        if (!mainWindow) return false;
        const next = !mainWindow.isFullScreen();
        mainWindow.setFullScreen(next);
        return next;
    });

    ipcMain.handle('native:quit', () => app.quit());

    // ---- 列表 ----
    ipcMain.handle('native:listSaves', () => {
        try {
            fs.mkdirSync(SAVE_DIR, { recursive: true });
            return fs.readdirSync(SAVE_DIR).filter(f => f.endsWith('.json'));
        } catch (e) { return []; }
    });

    ipcMain.handle('native:openSaveDir', () => shell.openPath(SAVE_DIR));
    ipcMain.handle('native:appInfo', () => ({
        name: APP_NAME, version: APP_VERSION, offline: true, saveDir: SAVE_DIR
    }));

    // ---- jsbridge_android 协议解析 ----
    ipcMain.handle('hun:bridge', async (_e, cmdStr) => {
        const parts = String(cmdStr || '').split('&');
        const cmd = (parts.shift() || '').trim();
        const kv = {};
        for (const p of parts) {
            const i = p.indexOf('=');
            if (i > 0) kv[p.slice(0, i)] = decodeURIComponent(p.slice(i + 1));
            else if (p) kv[p] = '';
        }

        switch (cmd) {
            case 'uuid':
                return { cmd, uuid: getStableUuid() };
            case 'base_url':
                return { cmd, base_url: 'file://' };
            case 'audiovibrate':
                return { cmd, ok: true };          // 桌面端无振动，静默成功
            case 'remove_splash':
            case 'show_splash':
            case 'remove_reloadbutton':
            case 'reset_label_text':
                return { cmd, ok: true };
            case 'getSystemMemory':
            case 'getAppMaxMemory':
            case 'getAppTotalMemory':
            case 'getAppFreeMemory':
                return { cmd, ok: true, value: String(os.freemem()) };
            case 'checkRoot':
                return { cmd, ok: true, rooted: false };
            case 'saveKY':
                try {
                    fs.mkdirSync(SAVE_DIR, { recursive: true });
                    fs.writeFileSync(path.join(SAVE_DIR, 'ky_' + (kv.key || 'default') + '.txt'),
                        kv.value || '', 'utf-8');
                    await _e.sender.executeJavaScript(
                        `window.fromAndroid_saveKYResult && window.fromAndroid_saveKYResult("OK")`);
                } catch (err) { }
                return { cmd, ok: true };
            case 'getKY':
                try {
                    const f = path.join(SAVE_DIR, 'ky_' + (kv.key || 'default') + '.txt');
                    const v = fs.existsSync(f) ? fs.readFileSync(f, 'utf-8') : '';
                    await _e.sender.executeJavaScript(
                        `window.fromAndroid_getKYResult && window.fromAndroid_getKYResult(${JSON.stringify(v)})`);
                    return { cmd, ok: true, value: v };
                } catch (err) { return { cmd, ok: true, value: '' }; }
            case 'deleteKY':
                try {
                    const f = path.join(SAVE_DIR, 'ky_' + (kv.key || 'default') + '.txt');
                    if (fs.existsSync(f)) fs.unlinkSync(f);
                } catch (err) { }
                return { cmd, ok: true };
            case 'outlink':
                // 离线模式：不打开外链
                return { cmd, ok: false, blocked: true };
            case 'googleplay':
            case 'googleplayReview':
                // 单机版无应用商店，静默成功避免卡流程
                await _e.sender.executeJavaScript(
                    `window.fromAndroid_GooglePlayResult && window.fromAndroid_GooglePlayResult("CANCEL")`);
                return { cmd, ok: true };
            default:
                console.log('[桥接] 未处理命令:', cmd);
                return { cmd, ok: false, unknown: true };
        }
    });
}

/** 稳定的设备标识（替代原 DeviceUtils.getUniqueId） */
function getStableUuid() {
    const f = path.join(USER_DATA, '.device_id');
    try {
        if (fs.existsSync(f)) return fs.readFileSync(f, 'utf-8').trim();
    } catch (e) { }
    const crypto = require('crypto');
    const id = crypto.createHash('md5')
        .update(os.hostname() + os.platform() + os.arch() + Date.now() + Math.random())
        .digest('hex');
    try { fs.writeFileSync(f, id, 'utf-8'); } catch (e) { }
    return id;
}

// ============================ 生命周期 ============================
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
    app.quit();
} else {
    app.on('second-instance', () => {
        if (mainWindow) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            mainWindow.focus();
        }
    });

    app.whenReady().then(() => {
        fs.mkdirSync(SAVE_DIR, { recursive: true });
        setupBridge();
        createWindow();

        app.on('activate', () => {
            if (BrowserWindow.getAllWindows().length === 0) createWindow();
        });
    });

    app.on('window-all-closed', () => {
        if (process.platform !== 'darwin') app.quit();
    });
}
