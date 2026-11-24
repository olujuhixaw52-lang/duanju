# -*- coding: utf-8 -*-
"""
check_pwa.py — 发布前的 PWA 自检（本地与 CI 共用）
==================================================
检查项：
  1. 必需文件是否齐全（index.html / manifest.json / sw.js / icons / .nojekyll）
  2. manifest 字段与图标：name、start_url、display、icons 尺寸是否与真实 PNG 匹配
  3. 图标真实尺寸（读 PNG IHDR，不信文件名）
  4. index.html 必须的 meta / link / script 是否在
  5. 相对引用是否都存在（manifest、sw、图标、dramaList 里的本地视频）
  6. 是否误用绝对路径（/xxx），GitHub Pages 子路径会 404
  7. 视频源是否看起来可公开访问（http/https 且带扩展名或 obvious 直链）

用法：
  python scripts/check_pwa.py            # 在发布目录里跑
  python tools/check_pwa.py --dir deploy/drama-pages
退出码：0 = 全部通过；1 = 有 error
"""
import argparse
import io
import json
import os
import re
import struct
import sys

REQUIRED = ["index.html", "manifest.json", "sw.js", "icons", ".nojekyll"]
ICON_SIZES = {"icons/icon-180.png": (180, 180), "icons/icon-192.png": (192, 192),
              "icons/icon-512.png": (512, 512), "icons/icon-512-maskable.png": (512, 512)}

errors = []
warns = []


def err(msg): errors.append(msg)
def warn(msg): warns.append(msg)


def png_size(path):
    with io.open(path, "rb") as f:
        head = f.read(33)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    a = ap.parse_args()
    root = os.path.abspath(a.dir)

    # 1. 必需文件
    for name in REQUIRED:
        p = os.path.join(root, name)
        if not os.path.exists(p):
            err(f"缺少 {name}")
    if os.path.exists(os.path.join(root, "README.md")) is False:
        warn("没有 README.md，仓库首页会空")

    # 2. manifest
    mpath = os.path.join(root, "manifest.json")
    if os.path.exists(mpath):
        try:
            m = json.load(io.open(mpath, encoding="utf-8"))
        except ValueError as e:
            err(f"manifest.json 不是合法 JSON：{e}")
            m = {}
        for k in ("name", "short_name", "start_url", "display", "icons", "theme_color"):
            if k not in m:
                err(f"manifest 缺字段 {k}")
        if m.get("display") not in ("standalone", "fullscreen", "minimal-ui"):
            err("manifest display 建议用 standalone / fullscreen")
        icons = m.get("icons", [])
        if not any(i.get("sizes") == "192x192" for i in icons):
            err("manifest 缺 192x192 图标（Chrome 安装提示要求）")
        if not any(i.get("sizes") == "512x512" for i in icons):
            err("manifest 缺 512x512 图标")
        if not any(i.get("purpose") == "maskable" for i in icons):
            warn("没有 maskable 图标，Android 可能给图标加白底")

    # 3. 图标真实尺寸
    for rel, expect in ICON_SIZES.items():
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            err(f"缺图标 {rel}")
            continue
        got = png_size(p)
        if got is None:
            err(f"{rel} 不是合法 PNG")
        elif tuple(got) != expect:
            err(f"{rel} 实际 {got[0]}x{got[1]}，manifest/命名要求 {expect[0]}x{expect[1]}")
        if os.path.getsize(p) > 400 * 1024:
            warn(f"{rel} 体积偏大（{os.path.getsize(p)//1024} KB），建议压到 200 KB 内")

    # 4/5/6. index.html
    ipath = os.path.join(root, "index.html")
    if os.path.exists(ipath):
        html = io.open(ipath, encoding="utf-8").read()
        must = ['rel="manifest"', 'apple-mobile-web-app-capable',
                'name="viewport"', 'serviceWorker', 'const dramaList']
        for s in must:
            if s not in html:
                err(f"index.html 缺少 {s}")
        refs = re.findall(r'(?:src|href)="([^"]+)"', html)
        for r in refs:
            if r.startswith(("http://", "https://", "data:", "#", "mailto:")):
                continue
            if r.startswith("/"):
                err(f"用了绝对路径 {r}，GitHub Pages 子路径下会 404")
                continue
            if not os.path.exists(os.path.join(root, r)):
                err(f"引用的文件不存在：{r}")
        eps = re.findall(r'"videoUrl"\s*:\s*"([^"]+)"', html)
        if not eps:
            err("index.html 里没找到 videoUrl")
        for v in eps:
            if v.startswith(("http://", "https://")):
                if not re.search(r"\.(mp4|webm|m4v)(\?|$)", v, re.I):
                    warn(f"视频直链不像 mp4：{v[:60]}")
            elif not os.path.exists(os.path.join(root, v)):
                err(f"本地视频不存在：{v}")
        if "maximum-scale=1" in html and "user-scalable=no" in html:
            warn("禁止了缩放，视力不佳的用户无法放大文字（可接受但要知道）")

    # 片源授权：进公开仓库的素材必须能说明来源，否则等于对外分发
    vdir = os.path.join(root, "videos")
    if os.path.isdir(vdir):
        media = sorted(f for f in os.listdir(vdir) if f.lower().endswith((".mp4", ".webm", ".m4v")))
        if media:
            lic = os.path.join(vdir, "LICENSES.md")
            if not os.path.exists(lic):
                warn(f"videos/ 有 {len(media)} 个片源但没有 LICENSES.md：Pages 是公开可下载的，等于对外分发")
            elif "待填" in io.open(lic, encoding="utf-8").read():
                warn("videos/LICENSES.md 还有「待填」项：对外宣传/投放前先补齐来源与授权")

    # sw.js 基本检查
    spath = os.path.join(root, "sw.js")
    if os.path.exists(spath):
        sw = io.open(spath, encoding="utf-8").read()
        if "addEventListener(\"install\"" not in sw and "addEventListener('install'" not in sw:
            err("sw.js 没有 install 事件，无法预缓存外壳")
        if "(mp4|webm" not in sw:
            warn("sw.js 没有放行视频扩展名，Range 请求可能被接管")
        # 预缓存清单里的每个文件都得真的存在，否则安装时会 404
        m = re.search(r"SHELL_FILES\s*=\s*\[(.*?)\]", sw, re.S)
        if not m:
            err("sw.js 里没找到 SHELL_FILES 清单")
        else:
            listed = re.findall(r'"(\./[^"]*)"', m.group(1))
            for item in listed:
                rel = item[2:]
                if rel and not os.path.exists(os.path.join(root, rel)):
                    if rel == "" or rel.endswith("/"):
                        continue
                    err(f"sw.js 预缓存的文件不存在：{item}")

    # 前端 v2（一起发布）：页面、清单、封面、片库数据
    v2 = os.path.join(root, "player-v2.html")
    if not os.path.exists(v2):
        warn("没有 player-v2.html（新版播放器未随包发布）")
    else:
        html2 = io.open(v2, encoding="utf-8").read()
        if 'rel="manifest"' not in html2:
            err("player-v2.html 缺 manifest 链接")
        for rel in re.findall(r'(?:src|href)="([^"]+)"', html2):
            if rel.startswith(("http://", "https://", "data:", "#")):
                continue
            if not os.path.exists(os.path.join(root, rel)):
                err(f"player-v2.html 引用的文件不存在：{rel}")
        llib = os.path.join(root, "local-library.json")
        if not os.path.exists(llib):
            err("缺 local-library.json（v2 播放器没数据源）")
        else:
            try:
                data = json.load(io.open(llib, encoding="utf-8"))
            except ValueError as e:
                err(f"local-library.json 不是合法 JSON：{e}")
                data = {}
            items = data.get("items", [])
            if not items:
                err("local-library.json 里没有 items")
            for it in items:
                src = it.get("src", "")
                if src and not os.path.exists(os.path.join(root, src)):
                    err(f"v2 片源不存在：{src}")
                if not it.get("exists"):
                    warn(f"v2 里有一集标记不存在：{it.get('title')}")
        for man in ("v2-manifest.json", "library-v2-manifest.json"):
            p = os.path.join(root, man)
            if not os.path.exists(p):
                err(f"缺 {man}")
                continue
            try:
                mm = json.load(io.open(p, encoding="utf-8"))
            except ValueError as e:
                err(f"{man} 不是合法 JSON：{e}")
                continue
            su = mm.get("start_url", "")
            target = su.split("?")[0].lstrip("./")
            if not target or not os.path.exists(os.path.join(root, target)):
                err(f"{man} 的 start_url 指向不存在的 {su}")
            for ic in mm.get("icons", []):
                if not os.path.exists(os.path.join(root, ic["src"])):
                    err(f"{man} 图标不存在：{ic['src']}")

    # 输出
    for w in warns:
        print(f"  warn  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    if errors:
        print(f"\n[check] 失败：{len(errors)} 个 error，{len(warns)} 个 warn")
        return 1
    print(f"[check] 通过：0 error，{len(warns)} 个 warn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
