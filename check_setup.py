"""One-click check: tests each service and lists your Buffer channels."""
import os, json
from common import *

ok = True
def step(name, fn):
    global ok
    try:
        print(f"[OK]   {name}: {fn() or ''}")
    except Exception as e:
        ok = False
        print(f"[FAIL] {name}: {e}")

need = ["GEMINI_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "BUFFER_API_KEY",
        "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"]
print("Secrets present:", {n: bool(os.environ.get(n, "").strip()) for n in need + ["BUFFER_CHANNEL_ID"]})

step("Gemini writing", lambda: gemini_json('Return ONLY JSON: {"hello": "world"}'))
step("Cloudflare image", lambda: (cloudflare_image("a simple navy blue and gold abstract background", "/tmp/t.jpg"), "image created")[1])

def buf():
    r = buffer("query { account { organizations { id name } } }")
    orgs = r["data"]["account"]["organizations"]
    lines = []
    for o in orgs:
        c = buffer('query { channels(input: { organizationId: %s }) { id name service } }' % json.dumps(o["id"]))
        for ch in c["data"]["channels"]:
            lines.append(f"channel {ch['service']} | {ch['name']} | ID: {ch['id']}")
    return "\n        " + "\n        ".join(lines)
step("Buffer channels (copy the TikTok channel ID)", buf)
step("Email", lambda: (send_email("Autoposter setup test", "If you can read this, email reports work."), "test email sent")[1])
print("\nALL GOOD" if ok else "\nSOMETHING FAILED - copy the [FAIL] lines to Claude")
