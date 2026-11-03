"""Step 2: send the pending post to Buffer (queue), remember it, then email a report."""
import difflib, json, os, time
import requests
from common import *


def wait_for_url(url, tries=12):
    for _ in range(tries):
        try:
            r = requests.head(url, timeout=20, allow_redirects=False)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(10)
    return False


def already_posted(p, history):
    for h in history[-300:]:
        if h.get("image_path") == p.get("image_path"):
            return True
        a, b = h.get("headline", "").lower(), p.get("headline", "").lower()
        if a and difflib.SequenceMatcher(None, a, b).ratio() > 0.9:
            return True
    return False


def main():
    if not os.path.exists(PENDING):
        print("Nothing pending.")
        return
    p = load_json(PENDING, {})
    history = load_json(HISTORY, [])
    if already_posted(p, history):
        print("This post was already sent before. Skipping it so nothing is posted twice.")
        os.remove(PENDING)
        return

    repo = env("GITHUB_REPOSITORY")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{p['image_path']}"
    if not wait_for_url(url):
        raise RuntimeError(f"Image link never became reachable: {url}")

    text = f"{p['caption']} {p['hashtags']}".strip()
    q = f"""mutation CreatePost {{
  createPost(input: {{
    text: {json.dumps(text)}
    channelId: {json.dumps(env('BUFFER_CHANNEL_ID'))}
    schedulingType: automatic
    mode: addToQueue
    assets: [{{ image: {{ url: {json.dumps(url)} }} }}]
  }}) {{
    ... on PostActionSuccess {{ post {{ id text }} }}
    ... on MutationError {{ message }}
  }}
}}"""
    res = buffer(q)
    data = (res.get("data") or {}).get("createPost") or {}
    post = data.get("post")
    if not post:
        raise RuntimeError(f"Buffer did not accept the post: {json.dumps(res)[:500]}")

    # Remember the post IMMEDIATELY, before anything else can go wrong (such as email)
    history.append({**p, "image_url": url, "buffer_post_id": post.get("id"), "status": "queued in Buffer",
                    "created_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())})
    save_json(HISTORY, history)
    os.remove(PENDING)
    print("Queued in Buffer and saved to history.")

    body = (f"Your TikTok image post has been queued in Buffer. It will publish at your next Buffer posting time.\n\n"
            f"Slot: {p.get('slot', '')}\nAudience: {p['audience']}\nTopic: {p['topic']}\nHeadline: {p['headline']}\n\n"
            f"Caption:\n{text}\n\nImage: {url}\nBuffer post ID: {post.get('id')}\n")
    try:
        send_email(f"TikTok post queued: {p['headline']}", body)
        print("Report emailed.")
    except Exception as e:  # an email problem must never stop or repeat a post
        print(f"WARNING: post was queued, but the report email failed: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        notify_error("publishing the post", e)
        raise
