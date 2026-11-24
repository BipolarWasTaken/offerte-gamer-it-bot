#!/usr/bin/env python3
"""Pubblica su Telegram le righe di queue.csv con status=pending e send_at <= ora (Europe/Rome).

Uso:
  python post.py            un solo passaggio
  python post.py loop 58    resta attivo ~58 minuti, controlla la coda ogni minuto (git pull a ogni giro)
  python post.py check      verifica bot e canale
"""
import csv, os, sys, json, time, html, subprocess, urllib.parse, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "@OfferteGamerIT")
TAG = os.environ.get("AFFILIATE_TAG", "offertegameri-21")
FIELDS = ["id", "send_at", "category", "emoji", "title", "asin", "status", "note", "source", "sent_at", "hook", "deal",
          "price", "old_price", "priced_at", "img"]
PRICE_MAX_AGE_H = 10      # prezzi più vecchi di così non vengono mostrati
MAX_PER_PASS = 3          # massimo post per controllo (evita raffiche)
GRACE_HOURS = 12          # oltre questo ritardo il post viene scartato come "scaduto"
SHARE_URL = "https://t.me/share/url?url=https%3A%2F%2Ft.me%2FOfferteGamerIT&text=Offerte%20Amazon%20verificate%20ogni%20giorno"

LABEL = {
    "giochi": "GAMING", "console": "CONSOLE", "controller": "GAMING", "cuffie": "AUDIO", "storage": "PC & STORAGE",
    "pc": "PC", "laptop": "PC & LAPTOP", "monitor": "MONITOR", "tv": "TV", "smartphone": "SMARTPHONE",
    "audio": "AUDIO", "gadget": "GADGET", "casa": "CASA", "altro": "TECH",
}
HASHTAGS = {
    "giochi": "#Gaming #PS5 #Xbox", "console": "#Gaming #PS5 #Xbox", "controller": "#Gaming #PS5",
    "cuffie": "#Audio #Gaming", "storage": "#SSD #PC", "pc": "#PC #Tech", "laptop": "#PC #Tech",
    "monitor": "#Monitor #PC", "tv": "#TV #Tech", "smartphone": "#Smartphone #Tech",
    "audio": "#Audio #Tech", "gadget": "#Gadget #Tech", "casa": "#Casa #Tech", "altro": "#Tech",
    "bellezza": "#Bellezza #Cura", "giocattoli": "#LEGO #Giocattoli", "tablet": "#Tablet #Tech",
    "cucina": "#Cucina #Casa", "utensili": "#Bricolage #FaiDaTe", "fai da te": "#Bricolage #FaiDaTe",
}
BASE_TAGS = "#BlackFriday #OfferteAmazon #Sconti"
HOOK_DEFAULT = "Sconto attivo adesso su Amazon: il prezzo aggiornato lo vedi nella pagina del prodotto."
DEAL_DEFAULT = "OFFERTA BLACK FRIDAY"


def link(r):
    return f"https://www.amazon.it/dp/{r['asin'].strip()}?tag={TAG}"


def num(v):
    try:
        return float(str(v).replace("€", "").replace(".", "").replace(",", ".")) if "," in str(v) else float(str(v))
    except (TypeError, ValueError):
        return None


def price_info(r):
    """(prezzo, vecchio, pct, rilevato_alle) solo se il dato è fresco e coerente, altrimenti None."""
    p, o = num(r.get("price")), num(r.get("old_price"))
    if not p:
        return None
    try:
        at = datetime.strptime((r.get("priced_at") or "").strip(), "%Y-%m-%d %H:%M")
        if datetime.now(ROME).replace(tzinfo=None) - at > timedelta(hours=PRICE_MAX_AGE_H):
            return None
    except ValueError:
        return None
    pct = round((1 - p / o) * 100) if o and o > p else None
    return p, (o if pct else None), pct, at


def short_title(t, n=70):
    t = t.strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def message(r):
    title = html.escape(short_title(r["title"]))
    url = link(r)
    pi = price_info(r)
    lines = [f"{r['emoji'].strip()} <b>{title}</b>", ""]
    if pi:
        p, o, pct, at = pi
        if o:
            lines.append(f"💥 <b>-{pct}%</b>  ·  <b>{fmt(p)}€</b>  invece di  <s>{fmt(o)}€</s>")
        else:
            lines.append(f"💶 <b>{fmt(p)}€</b>")
    else:
        lines.append(f"💥 <b>{html.escape((r.get('deal') or DEAL_DEFAULT).strip())}</b>")
    if (r.get("hook") or "").strip():
        lines.append(f"✅ {html.escape(r['hook'].strip())}")
    lines += ["", f"👉 <a href=\"{url}\"><b>APRI SU AMAZON</b></a>", ""]
    foot = "#adv"
    if pi:
        foot += f" · prezzo del {pi[3].strftime('%d/%m %H:%M')}, può variare"
    lines.append(f"<i>{foot}</i>")
    tags = f"{BASE_TAGS} {HASHTAGS.get((r.get('category') or '').strip().lower(), '#Tech')}"
    lines.append(tags)
    return "\n".join(lines)


def fmt(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").replace(",00", "")


def keyboard(r):
    return json.dumps({"inline_keyboard": [
        [{"text": "🛒 VAI ALL'OFFERTA", "url": link(r)}],
    ]})


def api(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def multipart(fields, files):
    boundary = "----offerte" + str(int(time.time() * 1000))
    body = b""
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, (name, data, ctype) in files.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{name}\"\r\n"
                 f"Content-Type: {ctype}\r\n\r\n").encode() + data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def send(r):
    pi = price_info(r)
    try:
        import card
        photo = card.product_image(r["asin"].strip(), (r.get("img") or "").strip())
        jpg = card.make_card(short_title(r["title"], 60), *(pi[:3] if pi else (None, None, None)),
                             photo=photo, deal=(r.get("deal") or "").strip())
    except Exception as e:
        print("card non generata:", type(e).__name__)
        jpg = None
    if jpg:
        body, ctype = multipart(
            {"chat_id": CHAT, "caption": message(r), "parse_mode": "HTML", "reply_markup": keyboard(r)},
            {"photo": ("offerta.jpg", jpg, "image/jpeg")})
        req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", data=body,
                                     headers={"Content-Type": ctype})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    preview = json.dumps({"url": link(r), "prefer_large_media": True, "show_above_text": True})
    return api("sendMessage", chat_id=CHAT, text=message(r), parse_mode="HTML",
               reply_markup=keyboard(r), link_preview_options=preview)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def load():
    with open("queue.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(rows):
    with open("queue.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") or "" for k in FIELDS})


def one_pass():
    rows = load()
    now = datetime.now(ROME).replace(tzinfo=None)
    sent = 0
    changed = False
    for r in rows:
        if (r.get("status") or "").strip().lower() != "pending":
            continue
        try:
            when = datetime.strptime(r["send_at"].strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            r["status"] = "errore-data"; changed = True; continue
        if when > now:
            continue
        if now - when > timedelta(hours=GRACE_HOURS):
            r["status"] = "scaduto"; changed = True; continue
        if len((r.get("asin") or "").strip()) != 10:
            r["status"] = "errore-asin"; changed = True; continue
        if sent >= MAX_PER_PASS:
            continue
        try:
            res = send(r)
            r["status"] = "sent" if res.get("ok") else "errore-api"
            r["sent_at"] = now.strftime("%Y-%m-%d %H:%M")
            sent += 1
        except Exception as e:  # non stampare mai il token
            r["status"] = "errore-rete"
            print("errore invio", r["id"], type(e).__name__)
        changed = True
        time.sleep(2)
    if changed:
        save(rows)
    return sent, changed


def commit_queue():
    git("config", "user.name", "offerte-bot")
    git("config", "user.email", "bot@users.noreply.github.com")
    git("add", "queue.csv")
    if git("diff", "--cached", "--quiet").returncode == 0:
        return
    git("commit", "-m", "coda aggiornata")
    for _ in range(3):
        if git("push").returncode == 0:
            return
        git("pull", "--rebase", "--autostash")


def main():
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN mancante"); return 1
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "check":
        me = api("getMe")["result"]
        mem = api("getChatMember", chat_id=CHAT, user_id=me["id"])["result"]
        print("bot:", me["username"], "| stato nel canale:", mem["status"], "| può pubblicare:", mem.get("can_post_messages"))
        return 0
    if mode == "imgtest":
        import card
        for a in sys.argv[2:]:
            lg = []
            im = card.product_image(a, log=lg)
            print(a, "foto:", (im.size if im else "NON TROVATA"))
            for l in lg:
                print("   ", l)
        return 0
    if mode == "loop":
        minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 58
        end = time.time() + minutes * 60
        while time.time() < end:
            git("pull", "--rebase", "--autostash")
            sent, changed = one_pass()
            if changed:
                commit_queue()
            print(datetime.now(ROME).strftime("%H:%M"), "inviati:", sent, flush=True)
            time.sleep(60)
        return 0
    sent, changed = one_pass()
    print("inviati:", sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
