#!/usr/bin/env python3
"""
WeChat Sticker Open Platform (sticker.weixin.qq.com) One-Click Compliance Packager.

Takes raw 320x320 transparent animated GIFs (from GPT-Image-2.6) + cover + banner,
and outputs a ready-to-upload folder (`wechat_upload/`) adhering strictly to WeChat specs:
  1. main/01..N.gif  : 240x240px, GIF89a, loop=0, disposal=2, safe margin, <= 500KB
  2. thumb/01..N.png : 120x120px, RGBA PNG, NO outer white sticker border, <= 200KB
  3. cover.png       : 240x240px, RGBA PNG, transparent bg, no text, no white border, <= 500KB
  4. icon.png        : 50x50px, RGBA PNG, tight head/upper-body crop, transparent bg, <= 100KB
  5. banner.png      : 750x400px, RGB (opaque, non-white, no text), <= 500KB
  6. preview.html    : Side-by-side WeChat Light (#EDEDED) & Dark (#191919) mode QA sheet
"""

import argparse
import json
from collections import deque
from pathlib import Path
from PIL import Image, ImageFilter, ImageSequence


def strip_outer_white_border(im_rgba: Image.Image, max_erode_px: int = 7) -> Image.Image:
    """
    WeChat requires thumbnails (120x120), cover (240x240), and icon (50x50)
    to NOT have a white sticker outline.
    This flood-fills from the exterior transparent boundary through near-white pixels
    within `max_erode_px` of the outer edge and makes them transparent.
    """
    im = im_rgba.convert("RGBA").copy()
    w, h = im.size
    px = im.load()

    visited = [[False] * h for _ in range(w)]
    q = deque()

    # Seed queue with all transparent pixels bordering non-transparent pixels, plus image edges
    for x in range(w):
        for y in range(h):
            r, g, b, a = px[x, y]
            if a < 32:
                visited[x][y] = True
                q.append((x, y, 0))

    while q:
        x, y, dist = q.popleft()
        if dist >= max_erode_px:
            continue
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny]:
                r, g, b, a = px[nx, ny]
                # Check if pixel is white / light gray sticker outline
                if a >= 32 and r > 215 and g > 215 and b > 210 and max(r, g, b) - min(r, g, b) < 30:
                    visited[nx][ny] = True
                    px[nx, ny] = (0, 0, 0, 0)
                    q.append((nx, ny, dist + 1))

    return im


def fit_with_safe_margin(frames_rgba: list[Image.Image], target_px: int = 240, margin_px: int = 8) -> list[Image.Image]:
    """
    Compute the union bounding box across all frames so motion is preserved,
    then scale and center into `target_px x target_px` with at least `margin_px` safe padding
    (WeChat rejects stickers that touch the canvas edges).
    """
    w0, h0 = frames_rgba[0].size
    union_bbox = None
    for f in frames_rgba:
        mask = f.getchannel("A").point(lambda a: 255 if a > 24 else 0)
        bb = mask.getbbox()
        if bb:
            if union_bbox is None:
                union_bbox = list(bb)
            else:
                union_bbox[0] = min(union_bbox[0], bb[0])
                union_bbox[1] = min(union_bbox[1], bb[1])
                union_bbox[2] = max(union_bbox[2], bb[2])
                union_bbox[3] = max(union_bbox[3], bb[3])

    if not union_bbox:
        union_bbox = [0, 0, w0, h0]

    bw = max(1, union_bbox[2] - union_bbox[0])
    bh = max(1, union_bbox[3] - union_bbox[1])

    # Detect whether the bottom edge of union_bbox is a flat half-body horizontal cut (半身截断像).
    # WeChat review rules require half-body cut edges to sit flush against the bottom canvas edge (y = target_px),
    # never floating in mid-air with a transparent gap underneath!
    bot_y1 = max(0, union_bbox[3] - 1)
    bot_y2 = max(0, union_bbox[3] - 2)
    max_bot_opaque = 0
    for f in frames_rgba:
        apx = f.getchannel("A").load()
        cnt = sum(1 for x in range(union_bbox[0], union_bbox[2]) if apx[x, bot_y1] > 80 or apx[x, bot_y2] > 80)
        if cnt > max_bot_opaque:
            max_bot_opaque = cnt
    bottom_flush = max_bot_opaque >= max(24, int(bw * 0.30))

    avail_w = target_px - 2 * margin_px
    avail_h = (target_px - margin_px) if bottom_flush else (target_px - 2 * margin_px)
    scale = min(avail_w / bw, avail_h / bh)

    nw = max(1, int(round(bw * scale)))
    nh = max(1, int(round(bh * scale)))
    ox = (target_px - nw) // 2
    oy = (target_px - nh) if bottom_flush else ((target_px - nh) // 2)

    out = []
    for f in frames_rgba:
        crop = f.crop(tuple(union_bbox)).resize((nw, nh), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (target_px, target_px), (0, 0, 0, 0))
        canvas.paste(crop, (ox, oy), crop)
        out.append(canvas)
    return out


def save_transparent_gif(frames_rgba: list[Image.Image], out_path: Path, duration_ms: int = 110, max_kb: int = 490):
    """
    Convert RGBA frames to a clean transparent GIF89a with zero white halo fringe on dark mode and file size <= max_kb.
    """
    for n_colors in (255, 192, 128, 96, 64):
        p_frames = []
        for f in frames_rgba:
            rgba = f.copy().convert("RGBA")
            alpha = rgba.getchannel("A")
            # Zero out RGB of transparent pixels before quantizing so transparent garbage doesn't pollute the palette,
            # while keeping true unbleached foreground RGB on semi-transparent edge pixels (alpha >= 145).
            clean_rgb = Image.new("RGB", rgba.size, (128, 128, 128))
            fg_mask = alpha.point(lambda a: 255 if a >= 145 else 0)
            clean_rgb.paste(rgba.convert("RGB"), mask=fg_mask)
            quant = clean_rgb.quantize(colors=n_colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
            # Reserve palette index 255 for transparency
            trans_mask = alpha.point(lambda a: 255 if a < 145 else 0)
            quant.paste(255, mask=trans_mask)
            p_frames.append(quant)

        p_frames[0].save(
            out_path,
            save_all=True,
            append_images=p_frames[1:],
            loop=0,
            duration=duration_ms,
            disposal=2,
            transparency=255,
            optimize=True,
        )
        size_kb = out_path.stat().st_size / 1024.0
        if size_kb <= max_kb:
            return round(size_kb, 1), n_colors

    return round(out_path.stat().st_size / 1024.0, 1), 64


def make_head_icon(cover_rgba: Image.Image, target_px: int = 50, strip_white: bool = False) -> Image.Image:
    """
    Crop the upper 68% (head/face focus) of the clean character so 50x50 chat tab icon is super legible.
    """
    clean = strip_outer_white_border(cover_rgba, max_erode_px=8) if strip_white else cover_rgba.convert("RGBA")
    mask = clean.getchannel("A").point(lambda a: 255 if a > 24 else 0)
    bb = mask.getbbox()
    if bb:
        clean = clean.crop(bb)
    w, h = clean.size
    head_h = max(1, int(round(h * 0.68)))
    head_crop = clean.crop((0, 0, w, head_h))

    avail_w = target_px - 4
    avail_h = target_px - 3
    scale = min(avail_w / max(head_crop.size[0], 1), avail_h / max(head_crop.size[1], 1))
    nw = max(1, int(round(head_crop.size[0] * scale)))
    nh = max(1, int(round(head_crop.size[1] * scale)))
    resized = head_crop.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (target_px, target_px), (0, 0, 0, 0))
    # Flush against bottom edge (y = target_px) so half-body neck/chest cut never floats in mid-air
    canvas.paste(resized, ((target_px - nw) // 2, target_px - nh), resized)
    return canvas


def make_banner(banner_src: Path, out_path: Path):
    """
    Crop and resize banner to exact 750x400 opaque PNG/JPEG <= 500KB.
    """
    im = Image.open(banner_src).convert("RGBA")
    bg = Image.new("RGBA", im.size, (245, 238, 225, 255))
    rgb = Image.alpha_composite(bg, im).convert("RGB")
    w, h = rgb.size
    target_ratio = 750 / 400
    cur_ratio = w / h
    if cur_ratio > target_ratio:
        new_w = int(round(h * target_ratio))
        x0 = (w - new_w) // 2
        rgb = rgb.crop((x0, 0, x0 + new_w, h))
    else:
        new_h = int(round(w / target_ratio))
        y0 = (h - new_h) // 2
        rgb = rgb.crop((0, y0, w, y0 + new_h))

    banner = rgb.resize((750, 400), Image.Resampling.LANCZOS)
    banner.save(out_path, format="PNG", optimize=True)
    if out_path.stat().st_size > 380 * 1024:
        banner.quantize(colors=256, method=Image.Quantize.FASTOCTREE).save(out_path, format="PNG", optimize=True)


def _extract_island_mask(im_rgba: Image.Image, seed_box: tuple[int, int, int, int]) -> tuple[Image.Image, tuple[int, int, int, int] | None]:
    """
    Flood-fill connected non-transparent pixels (`alpha > 20`) starting from any opaque pixel inside `seed_box`.
    Because both the top placard and the corner seal float in transparent air, this isolates ONLY the badge island
    without ever touching ear tips, hat wings, flags, or scrolls!
    """
    w, h = im_rgba.size
    alpha = im_rgba.getchannel("A")
    apx = alpha.load()
    sx0, sy0, sx1, sy1 = seed_box

    visited = [[False] * h for _ in range(w)]
    q = deque()
    for x in range(max(0, sx0), min(w, sx1)):
        for y in range(max(0, sy0), min(h, sy1)):
            if apx[x, y] > 20:
                visited[x][y] = True
                q.append((x, y))

    if not q:
        return Image.new("L", (w, h), 0), None

    mask = Image.new("L", (w, h), 0)
    mpx = mask.load()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    while q:
        x, y = q.popleft()
        mpx[x, y] = 255
        if x < min_x: min_x = x
        if y < min_y: min_y = y
        if x > max_x: max_x = x
        if y > max_y: max_y = y
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny] and apx[nx, ny] > 16:
                visited[nx][ny] = True
                q.append((nx, ny))

    return mask, (min_x, min_y, max_x + 1, max_y + 1)


def _sharpen_rgb_only(im_rgba: Image.Image) -> Image.Image:
    """Sharpen RGB channels without causing UnsharpMask ringing on the Alpha channel or outer boundary."""
    r, g, b, a = im_rgba.split()
    rgb = Image.merge("RGB", (r, g, b)).filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=3))
    sr, sg, sb = rgb.split()
    return Image.merge("RGBA", (sr, sg, sb, a))


def _trim_placard_outer_fringe(sign_rgba: Image.Image) -> Image.Image:
    """
    Remove the 1px outer warm/gray anti-aliasing fringe outside the placard's black border (`raw y=46` etc.)
    so resizing + sharpening never produces a 1px horizontal line underneath the placard.
    """
    out = sign_rgba.copy()
    w, h = out.size
    px = out.load()
    to_clear = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            # Check if on the outer 1px boundary adjacent to transparency
            is_edge = (
                x == 0 or y == 0 or x == w - 1 or y == h - 1
                or px[x - 1, y][3] < 40 or px[x + 1, y][3] < 40
                or px[x, y - 1][3] < 40 or px[x, y + 1][3] < 40
            )
            if is_edge:
                # The placard outer border is black (r,g,b < 45). Any lighter/warmer pixel on the outer edge is fringe.
                if max(r, g, b) > 42 or (r - b) > 18:
                    to_clear.append((x, y))
    for x, y in to_clear:
        px[x, y] = (0, 0, 0, 0)
    return out


def enlarge_badge_frames(frames: list[Image.Image], mode: str | None) -> list[Image.Image]:
    """
    Isolate the floating top placard (`mode="top_placard"`) or top-right vermilion seal (`mode="corner_seal"`)
    via exact alpha-island connected components, and scale it up by ~1.5x so the text is ~2.25x larger in area
    without ever clipping ears, hats, flags, or props.
    """
    if not mode:
        return frames
    w, h = frames[0].size

    if mode == "top_placard":
        # Seed inside top-center where the placard always sits: x in [120..200], y in [4..36]
        masks_bbs = [_extract_island_mask(f, (120, 4, 200, 36)) for f in frames]
        if not any(bb for _, bb in masks_bbs):
            return frames
        body_min_y = h
        out_frames = []
        ub = None
        for f, (m, bb) in zip(frames, masks_bbs):
            if bb and (bb[3] - bb[1]) <= 68:
                ub = list(bb) if ub is None else [min(ub[0], bb[0]), min(ub[1], bb[1]), max(ub[2], bb[2]), max(ub[3], bb[3])]
        if not ub:
            return frames

        erase_box = (max(0, ub[0] - 2), max(0, ub[1] - 2), min(w, ub[2] + 2), min(h, ub[3] + 2))
        for f in frames:
            body_only = f.copy()
            body_only.paste((0, 0, 0, 0), erase_box)
            bbb = body_only.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
            if bbb:
                body_min_y = min(body_min_y, bbb[1])

        sw, sh = ub[2] - ub[0], ub[3] - ub[1]
        eff_scale = min(1.52, 266.0 / max(sw, 1), 60.0 / max(sh, 1))
        nw, nh = int(round(sw * eff_scale)), int(round(sh * eff_scale))
        ox = (w - nw) // 2
        oy = 3
        shift_down = max(0, (oy + nh + 6) - body_min_y)
        cw, ch = w, h + shift_down

        for f, (m, _) in zip(frames, masks_bbs):
            sign_only = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sign_only.paste(f, mask=m)
            sign_clean = _trim_placard_outer_fringe(sign_only.crop(tuple(ub)))
            sign_crop = _sharpen_rgb_only(sign_clean.resize((nw, nh), Image.Resampling.LANCZOS))
            body_only = f.copy()
            body_only.paste((0, 0, 0, 0), erase_box)
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            canvas.paste(body_only, (0, shift_down), body_only)
            canvas.alpha_composite(sign_crop, (ox, oy))
            out_frames.append(canvas)
        return out_frames

    if mode == "corner_seal":
        # Seed inside top-right corner where the vermilion seal sits: x in [245..305], y in [8..55]
        masks_bbs = [_extract_island_mask(f, (245, 8, 305, 55)) for f in frames]
        if not any(bb for _, bb in masks_bbs):
            return frames
        ub = None
        for _, bb in masks_bbs:
            if bb and (bb[2] - bb[0]) <= 105 and (bb[3] - bb[1]) <= 130:
                ub = list(bb) if ub is None else [min(ub[0], bb[0]), min(ub[1], bb[1]), max(ub[2], bb[2]), max(ub[3], bb[3])]
        if not ub:
            return frames
        sw, sh = ub[2] - ub[0], ub[3] - ub[1]
        eff_scale = min(1.45, 102.0 / max(sw, 1), 112.0 / max(sh, 1))
        nw, nh = int(round(sw * eff_scale)), int(round(sh * eff_scale))
        erase_box = (max(0, ub[0] - 1), max(0, ub[1] - 1), min(w, ub[2] + 1), min(h, ub[3] + 1))

        # Find minimal diagonal expansion `d` so the enlarged top-right seal has >= 5px clearance from body/props
        best_d = 0
        for d in range(0, 44, 2):
            sx0 = w + d - nw - 3 - 5
            sy1 = 3 + nh - d + 5
            overlap = False
            if sy1 > 0 and sx0 < w:
                for f in frames:
                    body = f.copy()
                    body.paste((0, 0, 0, 0), erase_box)
                    crop = body.crop((max(0, sx0), 0, w, min(h, sy1)))
                    if crop.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox():
                        overlap = True
                        break
            if not overlap:
                best_d = d
                break

        cw, ch = w + best_d, h + best_d
        out_frames = []
        for f in frames:
            seal_crop_raw = f.crop(tuple(ub))
            seal_crop = _sharpen_rgb_only(seal_crop_raw.resize((nw, nh), Image.Resampling.LANCZOS))
            body_only = f.copy()
            body_only.paste((0, 0, 0, 0), erase_box)
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            canvas.paste(body_only, (0, best_d), body_only)
            canvas.alpha_composite(seal_crop, (cw - nw - 3, 3))
            out_frames.append(canvas)
        return out_frames

    return frames


def package_album(raw_dir: Path, out_dir: Path, meta_list: list[dict], duration_ms: int = 110, strip_white: bool = False, album_title: str = "微信动态表情包专辑", enlarge_mode: str | None = None):
    main_dir = out_dir / "main"
    thumb_dir = out_dir / "thumb"
    main_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)

    report_items = []
    for idx, item in enumerate(meta_list, start=1):
        code = f"{idx:02d}"
        raw_gif = raw_dir / f"{item['slug']}.gif"
        im = Image.open(raw_gif)
        frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(im)]
        frames = enlarge_badge_frames(frames, enlarge_mode)

        # 1. Main GIF (240x240)
        fitted_240 = fit_with_safe_margin(frames, target_px=240, margin_px=6)
        out_gif = main_dir / f"{code}.gif"
        size_kb, colors = save_transparent_gif(fitted_240, out_gif, duration_ms=duration_ms)

        # 2. Static Thumbnail (120x120 PNG)
        key_idx = min(len(frames) // 2, len(frames) - 1)
        clean_frame = strip_outer_white_border(frames[key_idx], max_erode_px=6) if strip_white else frames[key_idx]
        fitted_120 = fit_with_safe_margin([clean_frame], target_px=120, margin_px=6)[0]
        out_thumb = thumb_dir / f"{code}.png"
        fitted_120.save(out_thumb, format="PNG", optimize=True)
        thumb_kb = round(out_thumb.stat().st_size / 1024.0, 1)

        report_items.append({
            "code": code,
            "caption": item["caption"],
            "meaning": item.get("meaning", item["caption"].rstrip("！!？?")),
            "slug": item["slug"],
            "frames": len(frames),
            "gif_kb": size_kb,
            "thumb_kb": thumb_kb,
        })

    # 3. Cover (240x240 transparent PNG, no text, no white border) & Icon (50x50)
    cover_raw = raw_dir / "cover_raw.png"
    if cover_raw.exists():
        cov_im = Image.open(cover_raw).convert("RGBA")
    else:
        im0 = Image.open(raw_dir / f"{meta_list[0]['slug']}.gif")
        im0.seek(0)
        cov_im = im0.convert("RGBA")

    cov_clean = strip_outer_white_border(cov_im, max_erode_px=7) if strip_white else cov_im
    cov_240 = fit_with_safe_margin([cov_clean], target_px=240, margin_px=10)[0]
    cov_path = out_dir / "cover.png"
    cov_240.save(cov_path, format="PNG", optimize=True)

    icon_50 = make_head_icon(cov_clean, target_px=50, strip_white=strip_white)
    icon_path = out_dir / "icon.png"
    icon_50.save(icon_path, format="PNG", optimize=True)

    # 4. Banner (750x400 opaque PNG, no text)
    banner_raw = raw_dir / "banner_raw.png"
    banner_path = out_dir / "banner.png"
    if banner_raw.exists():
        make_banner(banner_raw, banner_path)

    # 5. Generate HTML QA Preview (WeChat Light #EDEDED & Dark #191919)
    cards_html = "\n".join(
        f"""
        <div class="card">
          <div class="title">#{it['code']} · 图面：「{it['caption']}」 <span style="color:#007aff;font-weight:500;font-size:13px;">[后台含义词填：{it['meaning']}]</span></div>
          <div class="pair">
            <div class="bg light"><img src="main/{it['code']}.gif" width="120" height="120"><span class="tag">微信浅色 240px GIF ({it['gif_kb']}KB)</span></div>
            <div class="bg dark"><img src="main/{it['code']}.gif" width="120" height="120"><span class="tag">微信深色 240px GIF</span></div>
            <div class="bg checker"><img src="thumb/{it['code']}.png" width="80" height="80"><span class="tag">缩略图 120px 无白边 ({it['thumb_kb']}KB)</span></div>
          </div>
        </div>
        """
        for it in report_items
    )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>微信表情包合规打包预览</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif; background: #f5f5f7; margin: 24px; color: #1d1d1f; }}
  h1 {{ font-size: 22px; margin-bottom: 8px; }}
  .meta {{ display: flex; gap: 20px; align-items: center; background: #fff; padding: 16px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 16px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
  .title {{ font-weight: 600; margin-bottom: 10px; font-size: 15px; }}
  .pair {{ display: flex; gap: 10px; align-items: center; }}
  .bg {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px; border-radius: 8px; min-height: 145px; }}
  .light {{ background: #EDEDED; color: #333; }}
  .dark {{ background: #191919; color: #ccc; }}
  .checker {{ background: repeating-conic-gradient(#e0e0e0 0% 25%, #ffffff 0% 50%) 50% / 16px 16px; color: #333; }}
  .tag {{ font-size: 11px; margin-top: 6px; opacity: 0.8; text-align: center; }}
</style>
</head>
<body>
  <h1>微信动态表情包一键合规包预览（共 {len(report_items)} 张）</h1>
  <div class="meta">
    <div><strong>详情页横幅 (750×400 不透明无字)</strong><br><img src="banner.png" height="110" style="border-radius:6px;margin-top:6px;"></div>
    <div class="bg checker" style="min-height:110px;flex:0 0 130px;"><img src="cover.png" width="90" height="90"><span class="tag">封面 240×240 无白边</span></div>
    <div class="bg checker" style="min-height:110px;flex:0 0 100px;"><img src="icon.png" width="50" height="50"><span class="tag">图标 50×50</span></div>
  </div>
  <div class="grid">
    {cards_html}
  </div>
</body>
</html>
"""
    (out_dir / "preview.html").write_text(html, encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(report_items, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_items
