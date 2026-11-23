/* sw.js — 只缓存“外壳”，视频一律走网络原样透传
   原因：视频请求带 Range，被 SW 拦截容易导致 seek 失败、进度条跳不回来。 */
const SHELL = "drama-shell-v1";
const SHELL_FILES = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icons/icon.svg",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting())
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

  // 视频：完全不拦截，交给浏览器原生流式加载
  if (isMedia) return;

  // 页面外壳：网络优先，断网回落缓存
  if (req.mode === "navigate" || (sameOrigin && SHELL_FILES.some((f) => url.pathname.endsWith(f.replace("./", "/"))))) {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match(req).then((r) => r || caches.match("./index.html")))
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
