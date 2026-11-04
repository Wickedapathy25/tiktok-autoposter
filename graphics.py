import json, os, random
from PIL import Image, ImageDraw, ImageFont
import config as C

D = "/usr/share/fonts/truetype/dejavu/"
SANS_B, SANS = D + "DejaVuSans-Bold.ttf", D + "DejaVuSans.ttf"
SERIF_B, SERIF = D + "DejaVuSerif-Bold.ttf", D + "DejaVuSerif.ttf"
DESIGN_LOG = "design_log.json"
W = C.SIZE

# Colour palettes (the first one is your core brand look, so it is picked most often)
PALETTES = {
    "navy_gold":     dict(panel=(11, 31, 58),  text=(255, 255, 255), sub=(225, 230, 240), accent=(212, 175, 55),
                          cta_bg=(212, 175, 55), cta_text=(11, 31, 58),  plate=(255, 255, 255), foot=(212, 175, 55)),
    "cream_navy":    dict(panel=(248, 243, 232), text=(11, 31, 58),    sub=(52, 66, 90),    accent=(184, 134, 11),
                          cta_bg=(11, 31, 58),   cta_text=(248, 243, 232), plate=(255, 255, 255), foot=(11, 31, 58)),
    "slate_amber":   dict(panel=(36, 48, 56),  text=(255, 255, 255), sub=(215, 222, 228), accent=(244, 176, 40),
                          cta_bg=(244, 176, 40), cta_text=(36, 48, 56),  plate=(255, 255, 255), foot=(244, 176, 40)),
    "teal_sand":     dict(panel=(14, 82, 92),  text=(250, 245, 235), sub=(220, 235, 232), accent=(238, 190, 100),
                          cta_bg=(250, 245, 235), cta_text=(14, 82, 92), plate=(255, 255, 255), foot=(238, 190, 100)),
    "burgundy_gold": dict(panel=(86, 24, 40),  text=(255, 255, 255), sub=(240, 220, 225), accent=(212, 175, 55),
                          cta_bg=(212, 175, 55), cta_text=(86, 24, 40),  plate=(255, 255, 255), foot=(212, 175, 55)),
    "forest_cream":  dict(panel=(24, 62, 48),  text=(250, 246, 236), sub=(214, 230, 220), accent=(226, 188, 96),
                          cta_bg=(250, 246, 236), cta_text=(24, 62, 48), plate=(255, 255, 255), foot=(226, 188, 96)),
}
PALETTE_WEIGHTS = {"navy_gold": 4, "cream_navy": 2, "slate_amber": 2, "teal_sand": 2, "burgundy_gold": 1, "forest_cream": 1}

# Layouts and where the logo may sit in each (so it never collides with text)
LAYOUTS = {
    "bottom_fade": ["TL", "TR", "TC"],
    "top_fade":    ["BL", "BR"],
    "center_card": ["TL", "TR", "TC", "BL", "BR"],
    "split_left":  ["TR", "BR"],
    "band_bottom": ["TL", "TR"],
    "frame":       ["TC", "TL", "TR"],
}


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def cover(img, w, h):
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    img = img.resize((int(iw * scale) + 1, int(ih * scale) + 1), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def fade(img, color, top=False, start=0.2, max_alpha=238, region=(0, W)):
    """Gradient of `color` over the image. top=True is solid at the top edge, else solid at the bottom edge."""
    y0, y1 = region
    h = y1 - y0
    mask = Image.new("L", (1, h))
    for y in range(h):
        t = 1 - y / h if top else y / h
        t = max(0.0, min(1.0, (t - start) / (1 - start)))
        mask.putpixel((0, y), int(max_alpha * (t ** 0.85)))
    mask = mask.resize((W, h))
    base = img.crop((0, y0, W, y1))
    base.paste(Image.new("RGB", (W, h), color), (0, 0), mask)
    img.paste(base, (0, y0))


def tint(img, color, alpha):
    return Image.blend(img, Image.new("RGB", img.size, color), alpha)


# ---------- text stack (accent bar, headline, subline, call-to-action) ----------
def build_stack(d, S, text, width, max_lines, max_h, start, min_size, sub_size=34, sub_lines_max=3, bar=True):
    head = text["headline"].upper() if S["upper"] else text["headline"]
    size = start
    while True:
        hf = font(S["bold"], size)
        lines = wrap(d, head, hf, width)
        lh = int(size * 1.18)
        if (len(lines) <= max_lines and lh * len(lines) <= max_h) or size <= min_size:
            break
        size -= 4
    sf = font(S["reg"], sub_size)
    sub = wrap(d, text["subline"], sf, width)[:sub_lines_max]
    slh = int(sub_size * 1.35)
    cf = font(S["bold"], 36)
    cta = f"COMMENT {text['cta'].upper()}"
    cw = int(d.textlength(cta, font=cf)) + 60
    ch = 68
    total = (28 if bar else 0) + lh * len(lines) + 22 + slh * len(sub) + 28 + ch
    return dict(hf=hf, lines=lines, lh=lh, sf=sf, sub=sub, slh=slh, cf=cf, cta=cta, cw=cw, ch=ch,
                total=total, bar=bar, width=width)


def draw_stack(d, st, P, x, y, align="left"):
    def px(tw):
        return x if align == "left" else x + (st["width"] - tw) // 2
    if st["bar"]:
        bx = px(130)
        d.rectangle([bx, y, bx + 130, y + 6], fill=P["accent"])
        y += 28
    for ln in st["lines"]:
        d.text((px(d.textlength(ln, font=st["hf"])), y), ln, font=st["hf"], fill=P["text"])
        y += st["lh"]
    y += 22
    for ln in st["sub"]:
        d.text((px(d.textlength(ln, font=st["sf"])), y), ln, font=st["sf"], fill=P["sub"])
        y += st["slh"]
    y += 28
    cx = px(st["cw"])
    d.rounded_rectangle([cx, y, cx + st["cw"], y + st["ch"]], radius=34, fill=P["cta_bg"])
    d.text((cx + 30, y + 14), st["cta"], font=st["cf"], fill=P["cta_text"])
    return y + st["ch"]


def website(d, P, x, y, align="left", right_edge=None):
    f = font(SANS, 25)
    t = C.WEBSITE
    if align == "right":
        x = right_edge - d.textlength(t, font=f)
    elif align == "center":
        x = (W - d.textlength(t, font=f)) / 2
    d.text((x, y), t, font=f, fill=P["foot"])


# ---------- logo (always the original file, never recoloured) ----------
def place_logo(img, P, pos, logo_path):
    d = ImageDraw.Draw(img)
    pad = 14
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((250, 96))
        lw, lh = logo.size
    else:
        logo, lf = None, font(SANS_B, 24)
        lw, lh = int(d.textlength(C.BUSINESS_NAME, font=lf)), 30
    pw, ph = lw + 2 * pad, lh + 2 * pad
    m = 36
    x = {"L": m, "R": W - m - pw, "C": (W - pw) // 2}[pos[1]]
    y = m if pos[0] == "T" else W - m - ph
    d.rounded_rectangle([x, y, x + pw, y + ph], radius=16, fill=P["plate"])
    if logo is not None:
        img.paste(logo, (x + pad, y + pad), logo)
    else:
        d.text((x + pad, y + pad - 2), C.BUSINESS_NAME, font=lf, fill=(11, 31, 58))


# ---------- the six layouts ----------
def L_bottom_fade(img, P, S, text, logo_pos):
    fade(img, P["panel"], top=False, start=0.22)
    d = ImageDraw.Draw(img)
    st = build_stack(d, S, text, W - 128, 4, 380, 88, 52)
    draw_stack(d, st, P, 64, W - 52 - 34 - st["total"])
    website(d, P, 64, W - 52)


def L_top_fade(img, P, S, text, logo_pos):
    fade(img, P["panel"], top=True, start=0.15)
    fade(img, P["panel"], top=False, start=0.55, max_alpha=215, region=(W - 260, W))
    d = ImageDraw.Draw(img)
    st = build_stack(d, S, text, W - 128, 4, 330, 80, 52)
    draw_stack(d, st, P, 64, 64)
    if logo_pos == "BR":
        website(d, P, 64, W - 70)
    else:
        website(d, P, 0, W - 70, align="right", right_edge=W - 64)


def L_center_card(img, P, S, text, logo_pos):
    img.paste(tint(img, P["panel"], 0.38))
    d = ImageDraw.Draw(img)
    st = build_stack(d, S, text, 740, 4, 300, 70, 46, sub_size=32, sub_lines_max=2)
    card_h = st["total"] + 2 * 48 + 44
    top = max(150, (W - card_h) // 2)
    card = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([70, top, W - 70, top + card_h], radius=30, fill=P["panel"] + (238,))
    img.paste(card, (0, 0), card)
    d = ImageDraw.Draw(img)
    draw_stack(d, st, P, 120, top + 48, align="center")
    website(d, P, 0, top + card_h - 58, align="center")


def L_split_left(img, P, S, text, logo_pos):
    px_w = 540
    photo = cover(img, W - px_w, W)
    img.paste(Image.new("RGB", (W, W), P["panel"]))
    img.paste(photo, (px_w, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([px_w - 8, 0, px_w, W], fill=P["accent"])
    st = build_stack(d, S, text, px_w - 100, 6, 430, 64, 40, sub_size=30, sub_lines_max=4)
    draw_stack(d, st, P, 50, max(60, (W - st["total"]) // 2 - 20))
    website(d, P, 50, W - 70)


def L_band_bottom(img, P, S, text, logo_pos):
    top_h = 400
    photo = cover(img, W, top_h)
    img.paste(Image.new("RGB", (W, W), P["panel"]))
    img.paste(photo, (0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, top_h, W, top_h + 8], fill=P["accent"])
    st = build_stack(d, S, text, W - 128, 3, 250, 72, 46, bar=False)
    y = top_h + 8 + max(30, (W - top_h - 8 - 52 - st["total"]) // 2)
    draw_stack(d, st, P, 64, y)
    website(d, P, 0, W - 62, align="right", right_edge=W - 64)


def L_frame(img, P, S, text, logo_pos):
    img.paste(tint(img, P["panel"], 0.62))
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, W - 30, W - 30], outline=P["accent"], width=5)
    st = build_stack(d, S, text, 760, 4, 300, 74, 46, sub_size=32, sub_lines_max=2)
    draw_stack(d, st, P, 110, max(190, (W - st["total"]) // 2 + 10), align="center")
    website(d, P, 0, W - 84, align="center")


LAYOUT_FUNCS = {"bottom_fade": L_bottom_fade, "top_fade": L_top_fade, "center_card": L_center_card,
                "split_left": L_split_left, "band_bottom": L_band_bottom, "frame": L_frame}


# ---------- choose a design that does not repeat recent ones ----------
def choose_design():
    try:
        log = json.load(open(DESIGN_LOG, encoding="utf-8"))
    except Exception:
        log = []
    last = log[-3:]
    layouts = [l for l in LAYOUTS if l not in [x.get("layout") for x in last[-2:]]]
    palettes = [p for p in PALETTES if p != (last[-1].get("palette") if last else None)]
    layout = random.choice(layouts or list(LAYOUTS))
    palette = random.choices(palettes, weights=[PALETTE_WEIGHTS[p] for p in palettes])[0]
    logo = random.choice(LAYOUTS[layout])
    if last and logo == last[-1].get("logo") and len(LAYOUTS[layout]) > 1:
        logo = random.choice([p for p in LAYOUTS[layout] if p != logo])
    design = {"layout": layout, "palette": palette, "logo": logo, "serif": random.random() < 0.35}
    json.dump((log + [design])[-40:], open(DESIGN_LOG, "w", encoding="utf-8"), indent=2)
    return design


def compose(bg_path, headline, subline, cta_keyword, out_path, logo_path="assets/logo.png", design=None):
    design = design or choose_design()
    P = PALETTES[design["palette"]]
    S = {"bold": SERIF_B if design["serif"] else SANS_B, "reg": SERIF if design["serif"] else SANS,
         "upper": not design["serif"]}
    img = cover(Image.open(bg_path).convert("RGB"), W, W)
    text = {"headline": headline, "subline": subline, "cta": cta_keyword}
    LAYOUT_FUNCS[design["layout"]](img, P, S, text, design["logo"])
    place_logo(img, P, design["logo"], logo_path)
    img.save(out_path, "JPEG", quality=92)
    print("Design:", design)
    return out_path
