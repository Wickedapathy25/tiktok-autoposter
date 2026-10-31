import os
from PIL import Image, ImageDraw, ImageFont
import config as C

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


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


def compose(bg_path, headline, subline, cta_keyword, out_path, logo_path="assets/logo.png"):
    W = C.SIZE
    img = Image.open(bg_path).convert("RGB")
    w, h = img.size
    s = min(w, h)
    left, top = (w - s) // 2, (h - s) // 2
    img = img.crop((left, top, left + s, top + s)).resize((W, W), Image.LANCZOS)

    # navy gradient (transparent at top, strong at bottom) so text is always readable
    mask = Image.new("L", (1, W))
    for y in range(W):
        t = max(0.0, (y - W * 0.22) / (W * 0.78))
        mask.putpixel((0, y), int(238 * min(1.0, t ** 0.85)))
    mask = mask.resize((W, W))
    img.paste(Image.new("RGB", (W, W), C.NAVY), (0, 0), mask)
    d = ImageDraw.Draw(img)

    margin = 64
    max_w = W - 2 * margin

    # headline: shrink until it fits in 4 lines
    head = headline.upper() if len(headline) <= 60 else headline
    size = 88
    while size >= 52:
        hf = font(BOLD, size)
        lines = wrap(d, head, hf, max_w)
        if len(lines) <= 4:
            break
        size -= 4
    line_h = int(size * 1.18)
    head_h = line_h * len(lines)

    sub_f = font(REG, 34)
    sub_lines = wrap(d, subline, sub_f, max_w)[:3]
    sub_h = int(34 * 1.35) * len(sub_lines)

    cta_text = f"COMMENT {cta_keyword.upper()}"
    cta_f = font(BOLD, 38)
    cta_w = int(d.textlength(cta_text, font=cta_f)) + 64
    cta_h = 72

    foot_f = font(REG, 26)
    foot_y = W - 52

    y_cta = foot_y - 30 - cta_h
    y_sub = y_cta - 28 - sub_h
    y_head = y_sub - 22 - head_h
    y_line = y_head - 22

    d.rectangle([margin, y_line, margin + 130, y_line + 6], fill=C.GOLD)
    y = y_head
    for ln in lines:
        d.text((margin, y), ln, font=hf, fill=C.WHITE)
        y += line_h
    y = y_sub
    for ln in sub_lines:
        d.text((margin, y), ln, font=sub_f, fill=(225, 230, 240))
        y += int(34 * 1.35)

    d.rounded_rectangle([margin, y_cta, margin + cta_w, y_cta + cta_h], radius=36, fill=C.GOLD)
    d.text((margin + 32, y_cta + 15), cta_text, font=cta_f, fill=C.NAVY)

    d.text((margin, foot_y), f"{C.WEBSITE}", font=foot_f, fill=C.GOLD)

    # logo (unchanged) top-left; if no file, draw the business name as text
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((300, 130))
        img.paste(logo, (margin - 6, 40), logo)
    else:
        nf = font(BOLD, 26)
        d.text((margin, 52), C.BUSINESS_NAME, font=nf, fill=C.GOLD)

    img.save(out_path, "JPEG", quality=92)
    return out_path
