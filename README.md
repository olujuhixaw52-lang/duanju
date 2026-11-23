# 创世录短剧 · 竖屏剧场

竖屏沉浸式短剧播放器（PWA）：单文件前端 + 清单 + Service Worker，无后端、无构建。

## 在线体验

https://<你的用户名>.github.io/mini-short-drama/

## 安装到手机桌面

- iPhone：Safari 打开上面地址 → 分享 → 添加到主屏幕
- Android：Chrome 打开 → ⋮ → 安装应用 / 添加到主屏幕

装完点开图标：无地址栏、无浏览器框，全屏即开。

## 换片源

改 index.html 顶部 dramaList 的 videoUrl。三条硬要求：支持 Range(206)、公开直链、跨域放行。
视频放在本仓库 videos/ 时用相对路径即可（单文件上限 100 MB）。

## 目录

| 文件 | 作用 |
| --- | --- |
| index.html | 播放器全部逻辑 |
| manifest.json | PWA 清单（standalone / 竖屏 / 图标） |
| sw.js | 只缓存外壳，视频请求原样透传（保证可拖进度） |
| icons/ | 180 / 192 / 512 / 512-maskable |
| .nojekyll | 关闭 Jekyll |
| checksums.json | 发布文件 sha256 清单 |

公开演示默认用 Google 官方公开测试片源；换成自己的片子时，把 videoUrl 改成本仓库 videos/ 下的相对路径，或用对象存储直链。
