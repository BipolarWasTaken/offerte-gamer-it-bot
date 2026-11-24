"""Genera l'immagine dell'offerta: foto prodotto + badge sconto + prezzo."""
import io, re, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

ANTON = "fonts/Anton-Regular.ttf"
POP = "fonts/Poppins-Bold.ttf"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


TAG = "offertegameri-21"


def widget_url(asin, size=500):
    """Immagine prodotto tramite il widget immagini del programma Affiliazione Amazon."""
    return ("https://ws-eu.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN=%s&Format=_SL%d_"
            "&ID=AsinImage&MarketPlace=IT&ServiceVersion=20070822&WS=1&tag=%s" % (asin, size, TAG))


def _try(u, log):
    try:
        im = Image.open(io.BytesIO(fetch(u))).convert("RGB")
        log.append("%s -> %sx%s" % (u[:70], im.width, im.height))
        if im.width >= 200 and im.height >= 200:
            return im
    except Exception as e:
        log.append("%s -> ERRORE %s" % (u[:70], str(e)[:60]))
    return None


def product_image(asin, img_url="", log=None):
    """Prova: URL fornito, widget Affiliazione Amazon, pagina prodotto Amazon.it."""
    log = log if log is not None else []
    if img_url:
        im = _try(img_url, log)
        if im:
            return im
    for attempt in range(3):
        try:
            page = fetch("https://www.amazon.it/dp/%s" % asin).decode("utf-8", "ignore")
        except Exception as e:
            log.append("pagina dp -> ERRORE %s" % str(e)[:60]); time.sleep(2); continue
        for pat in (r'"hiRes":"(https://[^"]+?\.jpg)"', r'"large":"(https://[^"]+?\.jpg)"',
                    r'<meta property="og:image" content="(https://[^"]+)"',
                    r'id="landingImage"[^>]+src="(https://[^"]+)"'):
            m = re.search(pat, page)
            if m:
                im = _try(m.group(1), log)
                if im:
                    return im
        time.sleep(2)
    return None


def F(p, s):
    return ImageFont.truetype(p, s)


def fmt(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").replace(",00", "")


def make_card(title, price=None, old=None, pct=None, photo=None, deal=""):
    W = H = 1080
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    # fascia alta gialla con brand
    d.rectangle([0, 0, W, 96], fill=(255, 214, 10))
    d.text((40, 22), "OFFERTE GAMER IT", font=F(POP, 44), fill=(17, 17, 17))
    tag = deal.upper() if deal else "BLACK FRIDAY"
    tw = d.textlength(tag, font=F(POP, 34))
    d.text((W - 40 - tw, 30), tag, font=F(POP, 34), fill=(17, 17, 17))
    # area foto
    top, bottom = 120, 800
    if photo:
        box_w, box_h = W - 120, bottom - top
        ph = photo.copy(); ph.thumbnail((box_w, box_h), Image.LANCZOS)
        img.paste(ph, ((W - ph.width) // 2, top + (box_h - ph.height) // 2))
    else:
        d.rounded_rectangle([60, top + 20, W - 60, bottom - 20], radius=40, fill=(245, 245, 247))
        words, lines, cur = title.upper().split(), [], ""
        f = F(ANTON, 90)
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= W - 200: cur = t
            else: lines.append(cur); cur = w
        if cur: lines.append(cur)
        n = len(lines[:3])
        y = 450 + max(0, (310 - n * 105) // 2) if pct else top + 40 + max(0, (bottom - top - 80 - n * 105) // 2)
        for ln in lines[:3]:
            d.text(((W - d.textlength(ln, font=f)) / 2, y), ln, font=f, fill=(17, 17, 17)); y += 105
    # badge sconto
    if pct:
        cx, cy, r = 190, 290, 140
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(230, 57, 70), outline=(255, 255, 255), width=8)
        d.text((cx, cy + 4), f"-{pct}%", font=F(ANTON, 96 if pct < 100 else 80), fill=(255, 255, 255), anchor="mm")
    # barra prezzo
    d.rectangle([0, 820, W, H], fill=(17, 17, 17))
    st = title if len(title) <= 40 else title[:38].rstrip() + "…"
    d.text((40, 872), st, font=F(POP, 38), fill=(255, 255, 255), anchor="lm")
    if price:
        p = f"{fmt(price)}€"
        fp = F(ANTON, 130)
        d.text((40, 1030), p, font=fp, fill=(255, 214, 10), anchor="ls")
        if old:
            o = f"{fmt(old)}€"
            fo = F(POP, 54)
            x = 40 + d.textlength(p, font=fp) + 40
            d.text((x, 1030), o, font=fo, fill=(170, 170, 170), anchor="ls")
            ow = d.textlength(o, font=fo)
            d.line([x - 4, 1030 - 24, x + ow + 4, 1030 - 24], fill=(230, 57, 70), width=6)
    else:
        d.text((40, 1020), "OFFERTA ATTIVA SU AMAZON", font=F(ANTON, 86), fill=(255, 214, 10), anchor="ls")
    out = io.BytesIO(); img.save(out, "JPEG", quality=90)
    return out.getvalue()
