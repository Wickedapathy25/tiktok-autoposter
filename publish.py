"""Step 2: send the pending post to Buffer (queue) and email you a report."""
import json, os, time
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


def main():
    if not os.path.exists(PENDING):
        print("Nothing pending.")
        return
    p = load_json(PENDING, {})
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

    history = load_json(HISTORY, [])
    history.append({**p, "image_url": url, "buffer_post_id": post.get("id"), "status": "queued in Buffer",
                    "created_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())})
    save_json(HISTORY, history)
    os.remove(PENDING)

    body = (f"Your TikTok image post has been queued in Buffer. It will publish at your next Buffer posting time.\n\n"
            f"Audience: {p['audience']}\nTopic: {p['topic']}\nHeadline: {p['headline']}\n\n"
            f"Caption:\n{text}\n\nImage: {url}\nBuffer post ID: {post.get('id')}\n")
    send_email(f"TikTok post queued: {p['headline']}", body)
    print("Queued and emailed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        notify_error("publishing the post", e)
        raise
