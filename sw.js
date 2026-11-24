/* sw.js — 只缓存“外壳”，视频一律走网络原样透传
   原因：视频请求带 Range，被 SW 拦截容易导致 seek 失败、进度条跳不回来。
   外壳同时覆盖旧版与 v2（播放器 / 片库），两条入口装上桌面后断网都能开。 */
const SHELL = "drama-shell-v2";
const SHELL_FILES = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icons/icon.svg",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  // ── v2：播放器、片库、两份清单、片库图标、已发布集数的封面 ──
  "./player-v2.html",
  "./library-v2.html",
  "./v2-manifest.json",
  "./library-v2-manifest.json",
  "./icons-lib/lib-180.png",
  "./icons-lib/lib-192.png",
  "./icons-lib/lib-512.png",
  "./icons-lib/lib-512-maskable.png",
  "./posters/e01.jpg",
  "./posters/e02.jpg",
];

self.addEventListener("install", (event) => {
  // 用逐个 add：任何一个文件缺失都不会把整个安装拖死，装不上就下次再补
  event.waitUntil(
    caches.open(SHELL).then((c) =>
      Promise.all(SHELL_FILES.map((f) =>
        c.add(new Request(f, { cache: "no-cache" })).catch(() => {})
      ))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  const isMedia = /\.(mp4|webm|mov|m4v|m3u8|ts)(\?|$)/i.test(url.pathname) || req.headers.get("range");

  // 视频与本机剧库代理：完全不拦截，交给浏览器原生流式加载
  if (isMedia || url.pathname.includes("/qj/")) return;

  // 页面外壳：网络优先，断网回落缓存；回落时按入口选对应的页
  const isShell = req.mode === "navigate" ||
    (sameOrigin && SHELL_FILES.some((f) => url.pathname.endsWith(f.replace("./", "/"))));
  if (isShell) {
    const fallback = url.pathname.includes("library-v2") ? "./library-v2.html" : "./index.html";
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match(req).then((r) => r || caches.match(fallback)))
    );
    return;
  }

  // 其他静态资源：缓存优先
  if (sameOrigin) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }))
    );
  }
});
