/*!
 * ============================================================================
 * 离线引导 · boot.js
 * ============================================================================
 * 职责：在页面内联脚本定义完路径函数之后、hun_min.js 加载之前，
 *      强制把资源路径指向本地目录，并跳过版本探测的远程请求。
 *
 * 注意：本脚本在 <body> 开头加载，晚于 <head> 中的路径覆写占位脚本、
 *      早于 game_main.html 内联脚本的执行。因此采用「轮询应用」策略：
 *      内联脚本一完成定义，立即覆写。
 * ============================================================================
 */
(function (global) {
    'use strict';

    var applied = false;

    // ============================ 本地 COS 存根 ============================
    /**
     * 原版页面与游戏核心通过腾讯云 COS SDK 读写存档。
     * 单机版必须尽早提供同名构造器，否则 new COS({...}) 会抛错。
     * 这里在最早的时机（boot.js 位于 <body> 开头）安装。
     */
    function installCosShim() {
        if (global.COS && global.COS.__offline) return;
        function LocalCOS() {
            this.putObject = function (opts, cb) {
                try {
                    if (opts && typeof opts.Body === 'string' && global.HUN_PC &&
                        global.HUN_PC.SaveEngine) {
                        global.HUN_PC.SaveEngine.save(JSON.parse(opts.Body));
                    }
                } catch (e) { }
                if (cb) setTimeout(function () { cb(null, { Body: '' }); }, 0);
            };
            this.getObject = function (opts, cb) {
                var s = (global.HUN_PC && global.HUN_PC.SaveEngine)
                    ? global.HUN_PC.SaveEngine.load() : null;
                if (!s) { if (cb) cb({ statusCode: 404, error: 'Not Found' }, null); return; }
                if (cb) cb(null, { Body: JSON.stringify(s) });
            };
            this.deleteObject = function (opts, cb) { if (cb) cb(null, {}); };
        }
        LocalCOS.__offline = true;
        global.COS = LocalCOS;
        console.log('[离线引导] 本地 COS 存根已安装（早期）');
    }
    installCosShim();

    function applyOnce() {
        if (applied) return true;
        var ok = false;

        // ---- 1. 资源根路径 → 本地 ----
        if (typeof global.getResPath_CORS_Web === 'function') {
            global.getResPath_CORS_Web = function () { return '.'; };
            ok = true;
        }
        if (typeof global.getResPath_UNCORS_Web === 'function') {
            global.getResPath_UNCORS_Web = function () { return '.'; };
            ok = true;
        }
        if (typeof global.getResPath_By_CDN === 'function') {
            global.getResPath_By_CDN = function () { return '.'; };
            ok = true;
        }

        // ---- 2. 版本信息 → 本地文件（不再请求远程）----
        if (typeof global.getVersionInfo === 'function') {
            global.getVersionInfo = function () { return 'json/version.json'; };
            ok = true;
        }

        // ---- 3. 强制非开发环境（保证走生产分支，但路径已被上面覆盖）----
        if (typeof global.hasGameEnv_Dev === 'function') {
            global.hasGameEnv_Dev = function () { return false; };
            ok = true;
        }

        // ---- 4. 环境标识：PC 渠道（自动启用 HD 图集）----
        if (!global.channel) {
            try { global.channel = 'pc'; } catch (e) { }
        }

        if (ok) {
            applied = true;
            console.log('[离线引导] 资源路径已本地化');
        }
        return applied;
    }

    // 立即尝试；未就绪则轮询（页面内联脚本同步执行，通常几十毫秒内完成）
    if (!applyOnce()) {
        var n = 0;
        var t = setInterval(function () {
            if (applyOnce() || ++n > 300) clearInterval(t);
        }, 10);
    }

    // 暴露给 start.js
    global.__offlineApplyPaths = applyOnce;
})(window);
