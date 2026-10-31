"""Step 1: write the post and build the image. Saves pending.json for publish.py."""
import difflib, os, random, time
from datetime import datetime, timezone

import config as C
import graphics
from common import *

STYLES = [
    "myth vs. fact", "a costly mistake to avoid", "a short checklist", "questions to ask before you commit",
    "a before-you-sign warning", "what most new owners overlook", "a simple 3-step next move",
    "a reality check on cost or timing", "a common misunderstanding", "a decision many owners face",
]
VISUALS = [
    "bright natural-light documentary photo", "clean overhead desk scene with documents and a laptop",
    "warm interior of a welcoming home environment", "professional office meeting room, shallow depth of field",
    "exterior of a modest residential street at golden hour", "close-up of hands organizing paperwork and folders",
    "calm professional workspace with a calendar and notes", "abstract navy and gold geometric background, no objects",
]

BRIEF = """You write TikTok photo posts for Next Level Care Biz Group, a U.S. care-business consulting firm
(tagline: Strategic Growth for Care Businesses). Services: startup planning, licensing and compliance preparation,
property and zoning research, policies and procedures, staffing and operations, referral systems and client acquisition,
government contracting preparation, financial operations. The firm gives consulting and preparation support. It does
NOT give legal advice and does NOT guarantee approvals or results."""


def read_audiences():
    out = []
    for line in open("audiences.txt", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split("|")]
        while len(p) < 3:
            p.append("United States")
        out.append({"audience": p[0], "type": p[1], "location": p[2]})
    if not out:
        raise RuntimeError("audiences.txt has no audiences")
    return out


def pick_audience(history, audiences):
    counts = {a["audience"]: 0 for a in audiences}
    for h in history[-60:]:
        if h.get("audience") in counts:
            counts[h["audience"]] += 1
    low = min(counts.values())
    return random.choice([a for a in audiences if counts[a["audience"]] == low])


def write_post(a, recent, style):
    prompt = f"""{BRIEF}

TARGET AUDIENCE: {a['audience']}. BUSINESS TYPE: {a['type']}. LOCATION: {a['location']}.
FORMAT FOR THIS POST: {style}.
RECENT HEADLINES (do not repeat or closely resemble): {recent}

Write ONE post about a specific problem, mistake, question or decision this audience really faces. Choose an angle
that differs from the recent headlines. Professional, direct, practical, specific to the care industry. No hype, no
guarantees, no invented statistics, no invented testimonials, no generic motivation.

FACT RULES: never state a specific state licensing rule, fee, deadline, law number, capacity limit, or contract
requirement. Where the topic depends on those, phrase it as a question to verify with the state agency or the
official solicitation. Never say or imply you can guarantee a license, approval or contract.

Return ONLY JSON with exactly these keys:
topic (short), headline (max 9 words, strong hook), subline (max 14 words),
caption (max 300 characters, ONE paragraph, no line breaks, ends with a call to action like "Comment ZONING and tell me your state."),
hashtags (array of 3 or 4 strings each starting with #), cta_keyword (ONE uppercase word that matches the topic),
image_prompt (a vivid description of a background photo that fits the topic, max 60 words; NOT always a building,
caregiver, clipboard or meeting; contains no text, letters, numbers, logos or people's faces in close-up)."""
    return gemini_json(prompt)


def review_post(p):
    prompt = f"""You are a strict compliance reviewer for marketing posts by a care-business consulting firm.
POST: {p}
Reject (ok=false) if the post: states a specific state rule, fee, deadline, law, capacity or contract requirement as
fact; guarantees licensing, approval, contracts, funding or results; gives legal or tax advice; uses invented
statistics or testimonials; makes medical claims; or is misleading. Otherwise ok=true.
Return ONLY JSON: {{"ok": true or false, "reason": "short reason"}}"""
    return gemini_json(prompt, temperature=0.1)


def too_similar(headline, history):
    for h in history[-60:]:
        if difflib.SequenceMatcher(None, headline.lower(), h.get("headline", "").lower()).ratio() > 0.75:
            return True
    return False


def clean_old_images():
    cutoff = time.time() - C.KEEP_IMAGES_DAYS * 86400
    for f in os.listdir("posts"):
        p = os.path.join("posts", f)
        if f.endswith(".jpg") and os.path.getmtime(p) < cutoff:
            os.remove(p)


def main():
    if os.path.exists(PENDING):
        print("A post is already waiting to publish; publish.py will handle it.")
        return
    history = load_json(HISTORY, [])
    done_today = [h for h in history if h.get("date") == today_utc() and h.get("kind") == "image"]
    if len(done_today) >= C.IMAGE_POSTS_PER_DAY:
        print("Today's image post is already done. Nothing to do.")
        return

    audiences = read_audiences()
    recent = [h.get("headline", "") for h in history[-25:]]
    post, why = None, ""
    for attempt in range(4):
        a = pick_audience(history, audiences)
        p = write_post(a, recent, random.choice(STYLES))
        need = ["topic", "headline", "subline", "caption", "hashtags", "cta_keyword", "image_prompt"]
        if any(k not in p for k in need):
            why = "missing fields"
            continue
        if too_similar(p["headline"], history):
            why = "too similar to a recent headline"
            continue
        r = review_post(p)
        if not r.get("ok"):
            why = f"review rejected: {r.get('reason')}"
            print("Rejected draft:", why)
            continue
        post = p
        break
    if not post:
        raise RuntimeError(f"No acceptable post after 4 tries ({why}). Skipped today.")

    slug = f"{today_utc()}-{slugify(post['headline'])}"
    bg, out = f"/tmp/{slug}-bg.jpg", f"posts/{slug}.jpg"
    prompt = f"{post['image_prompt']}. Style: {random.choice(VISUALS)}. High quality, realistic, no text, no letters, no watermark, no logos."
    cloudflare_image(prompt, bg)
    graphics.compose(bg, post["headline"], post["subline"], post["cta_keyword"], out)
    tags = " ".join(h if h.startswith("#") else "#" + h for h in post["hashtags"][:4])
    save_json(PENDING, {
        "kind": "image", "date": today_utc(), "audience": a["audience"], "topic": post["topic"],
        "headline": post["headline"], "caption": post["caption"].replace("\n", " ").strip(),
        "hashtags": tags, "image_path": out,
    })
    clean_old_images()
    print("Generated:", post["headline"])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        notify_error("generating the post", e)
        raise
