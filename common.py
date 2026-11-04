import base64, json, os, re, smtplib, sys, time
from datetime import datetime, timezone
from email.mime.text import MIMEText

import requests

HISTORY = "history.json"
PENDING = "pending.json"


def env(name, required=True, default=""):
    v = os.environ.get(name, default).strip()
    if required and not v:
        raise RuntimeError(f"Missing secret: {name}")
    return v


def today_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text, n=40):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].strip("-") or "post"


# ---------- Gemini (writing) ----------
def _discover_models(key):
    """Ask Google which Flash models exist right now (model names change over time)."""
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                         headers={"x-goog-api-key": key}, timeout=30)
        names = []
        for m in r.json().get("models", []):
            n = m.get("name", "").replace("models/", "")
            if "flash" not in n or "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            if any(x in n for x in ("image", "tts", "audio", "live", "native", "embedding", "robotics", "computer")):
                continue
            names.append(n)
        # newest first, "lite" versions last
        return sorted(names, key=lambda n: ("lite" in n, [-ord(c) for c in n]))[:6]
    except Exception as e:
        print(f"  (could not list Gemini models: {e})")
        return []


def gemini_json(prompt, temperature=0.9):
    key = env("GEMINI_API_KEY")
    candidates = [os.environ.get("GEMINI_MODEL", "").strip(), "gemini-3.0-flash", "gemini-flash-latest"]
    tried, last = set(), None
    discovered = False
    queue = [m for m in candidates if m]
    while queue:
        model = queue.pop(0)
        if model in tried:
            continue
        tried.add(model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
        }
        try:
            r = requests.post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                              json=body, timeout=60)
        except Exception as e:
            last = f"{model}: {type(e).__name__}"
            print(f"  Gemini model {model} failed: {last}")
        else:
            if r.status_code == 200:
                try:
                    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
                    return json.loads(text)
                except Exception as e:
                    last = f"{model}: could not read answer ({e})"
            else:
                last = f"{model}: HTTP {r.status_code} {r.text[:120]}"
            print(f"  Gemini model {model} failed: {last}")
        if not queue and not discovered:
            discovered = True
            queue = _discover_models(key)
            print(f"  Trying models found on your account: {queue}")
    raise RuntimeError("Gemini failed. " + str(last))


# ---------- Cloudflare FLUX (images) ----------
def cloudflare_image(prompt, out_path):
    acct = env("CLOUDFLARE_ACCOUNT_ID")
    token = env("CLOUDFLARE_API_TOKEN")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"},
                      json={"prompt": prompt[:1900], "steps": 6}, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"Cloudflare image failed: HTTP {r.status_code} {r.text[:200]}")
    data = r.json()
    b64 = (data.get("result") or {}).get("image")
    if not b64:
        raise RuntimeError(f"Cloudflare returned no image: {str(data)[:200]}")
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))


# ---------- Buffer ----------
def buffer(query):
    key = env("BUFFER_API_KEY")
    r = requests.post("https://api.buffer.com",
                      headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                      json={"query": query}, timeout=60)
    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"Buffer HTTP {r.status_code}: {r.text[:300]}")
    return data


# ---------- Email ----------
def send_email(subject, body):
    to = env("REPORT_EMAIL", required=False) or env("GMAIL_ADDRESS", required=False)
    resend_key = env("RESEND_API_KEY", required=False)

    # Preferred: Resend (sends over the web, so GitHub's servers are not blocked)
    if resend_key:
        if not to:
            raise RuntimeError("Set GMAIL_ADDRESS or REPORT_EMAIL to the email you signed up to Resend with.")
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json",
                     "User-Agent": "next-level-autoposter/1.0"},
            json={"from": "Autoposter <onboarding@resend.dev>", "to": [to], "subject": subject, "text": body},
            timeout=60)
        if r.status_code in (200, 201):
            return
        raise RuntimeError(f"Resend refused the email: HTTP {r.status_code} {r.text[:300]}")

    # Backup: Gmail
    user = env("GMAIL_ADDRESS")
    pw = env("GMAIL_APP_PASSWORD").replace(" ", "")
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to or user
    errors = []
    for mode in ("ssl465", "starttls587"):
        try:
            if mode == "ssl465":
                s = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60)
            else:
                s = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
                s.ehlo()
                s.starttls()
                s.ehlo()
            s.login(user, pw)
            s.send_message(msg)
            s.quit()
            return
        except smtplib.SMTPAuthenticationError as e:
            raise RuntimeError(f"Gmail refused the login (code {e.smtp_code}). Check the app password.")
        except Exception as e:
            errors.append(f"{mode}: {type(e).__name__}: {e}")
    raise RuntimeError("Could not send email through Gmail: " + " | ".join(errors))


def notify_error(title, err):
    print(f"ERROR: {title}: {err}", file=sys.stderr)
    try:
        send_email(f"Autoposter problem: {title}", f"{title}\n\n{err}\n\nNothing was posted for this run.")
    except Exception as e:
        print(f"(could not send error email: {e})", file=sys.stderr)
