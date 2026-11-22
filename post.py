#!/usr/bin/env python3
"""Pubblica su Telegram le righe di queue.csv con status=pending e send_at <= ora (Europe/Rome)."""
import csv, os, sys, json, urllib.parse, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "@OfferteGamerIT")
TAG = os.environ.get("AFFILIATE_TAG", "offertegameri-21")
FIELDS = ["id", "send_at", "category", "emoji", "title", "asin", "status", "note", "source", "sent_at"]
HASHTAGS = {
    "giochi": "#Gaming #PS5 #Xbox", "console": "#Gaming #PS5 #Xbox", "controller": "#Gaming #PS5",
    "cuffie": "#Audio #Gaming", "storage": "#SSD #PC", "pc": "#PC #Tech", "laptop": "#PC #Tech",
    "monitor": "#Monitor #PC", "tv": "#TV #Tech", "smartphone": "#Smartphone #Tech",
    "audio": "#Audio #Tech", "gadget": "#Gadget #Tech", "casa": "#Casa #Tech", "altro": "#Tech",
}
NOTE_DEFAULT = "In promo nella Settimana del Black Friday Amazon (fino al 30/11, fino a esaurimento scorte)."


def message(r):
    note = (r.get("note") or NOTE_DEFAULT).strip()
    tags = HASHTAGS.get(r["category"].strip().lower(), "#Tech")
    return (
        f"{r['emoji'].strip()} {r['title'].strip()}\n\n"
        f"📝 {note}\n\n"
        f"👉 https://www.amazon.it/dp/{r['asin'].strip()}?tag={TAG}\n\n"
        "In qualità di Affiliato Amazon io ricevo un guadagno dagli acquisti idonei.\n"
        "Prezzi e disponibilità possono variare: controlla sempre la pagina del prodotto.\n"
        f"#BlackFriday #Offerte {tags}\n#adv\n"
        "📲 Condividi il canale su WhatsApp: https://wa.me/?text=https%3A%2F%2Ft.me%2FOfferteGamerIT"
    )


def send(text):
    data = urllib.parse.urlencode({"chat_id": CHAT, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def api(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN mancante"); return 1
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        me = api("getMe")["result"]
        mem = api("getChatMember", chat_id=CHAT, user_id=me["id"])["result"]
        print("bot:", me["username"], "| stato nel canale:", mem["status"], "| può pubblicare:", mem.get("can_post_messages"))
        return 0
    with open("queue.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    now = datetime.now(ROME).replace(tzinfo=None)
    sent = 0
    for r in rows:
        if (r.get("status") or "").strip().lower() != "pending":
            continue
        try:
            when = datetime.strptime(r["send_at"].strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            r["status"] = "errore-data"; continue
        if when > now:
            continue
        if now - when > timedelta(hours=6):
            r["status"] = "scaduto"; continue
        if len(r["asin"].strip()) != 10:
            r["status"] = "errore-asin"; continue
        try:
            res = send(message(r))
            r["status"] = "sent" if res.get("ok") else "errore-api"
            r["sent_at"] = now.strftime("%Y-%m-%d %H:%M")
            sent += 1
        except Exception as e:  # non stampare mai il token
            r["status"] = "errore-rete"
            print("errore invio", r["id"], type(e).__name__)
    with open("queue.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print("inviati:", sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
