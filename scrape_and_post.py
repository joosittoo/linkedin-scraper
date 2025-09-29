from playwright.sync_api import sync_playwright
import os, time, random, json, hashlib, requests
from urllib.parse import urljoin

def normalize_text(s): return " ".join(s.split()) if s else ""

def extract_post_from_article(article):
    out = {"url": None, "text": "", "author": None, "time": None, "likes": None}
    try:
        a = article.query_selector('a[href*="/activity/"], a[href*="/feed/update/"], a[href*="/posts/"]')
        if a:
            href = a.get_attribute('href'); out['url'] = urljoin("https://www.linkedin.com", href) if href else None
        text_selectors = ['div.feed-shared-update-v2__description','div.feed-shared-text','span.break-words','div[dir="ltr"]']
        longest = ""
        for sel in text_selectors:
            e = article.query_selector(sel)
            if e:
                t = e.inner_text().strip()
                if len(t) > len(longest): longest = t
        out['text'] = normalize_text(longest)
        a2 = article.query_selector('a[href*="/in/"], a[href*="/company/"]')
        if a2: out['author'] = a2.inner_text().strip()
        time_el = article.query_selector('time')
        if time_el: out['time'] = time_el.get_attribute('datetime') or time_el.inner_text().strip()
        import re
        m = re.search(r'(\d[\d.,]*)\s*(likes|me gusta|reacciones|reaction|reacciones)', article.inner_text(), re.I)
        if m: out['likes'] = m.group(1).replace('.', '').replace(',', '')
    except Exception as e:
        print("extract error:", e)
    return out

def scrape_profile(profile_url, li_at, max_posts=60):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies([{"name":"li_at","value":li_at,"domain":".linkedin.com","path":"/"}])
        page = context.new_page(); page.set_default_timeout(60000)
        page.goto(profile_url)
        page.wait_for_selector('article, div.feed-shared-update-v2', timeout=20000)
        seen, results, tries = set(), [], 0
        while len(results) < max_posts and tries < 80:
            for art in page.query_selector_all('article, div.feed-shared-update-v2'):
                d = extract_post_from_article(art)
                uid = d.get('url') or hashlib.sha1((d.get('text') or "")[:200].encode()).hexdigest()
                if uid in seen: continue
                raw = (art.inner_text() or "").lower()
                if any(w in raw for w in ['reshared','volvió a compartir','compartió','repost']): continue
                seen.add(uid); results.append(d)
                if len(results) >= max_posts: break
            if len(results) >= max_posts: break
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(1.6 + random.random()*1.8); tries += 1
        browser.close()
        return results

def post_to_make(webhook_url, payload):
    headers = {"Content-Type": "application/json"}
    r = requests.post(webhook_url, json=payload, headers=headers, timeout=60)
    print("Webhook status:", r.status_code)
    print("Webhook response (first 200):", (r.text or "")[:200])
    r.raise_for_status()

if __name__ == "__main__":
    LI_AT = os.getenv("LI_AT")
    MAKE_WEBHOOK = os.getenv("MAKE_WEBHOOK")
    PROFILE_URL = os.getenv("LD_PROFILE_URL")
    MAX_POSTS = int(os.getenv("MAX_POSTS", "60"))
    if not LI_AT or not MAKE_WEBHOOK:
        raise SystemExit("Set LI_AT and MAKE_WEBHOOK secrets.")
    rows = scrape_profile(PROFILE_URL, LI_AT, MAX_POSTS)
    print(f"Scraped {len(rows)} posts")
    post_to_make(MAKE_WEBHOOK, {"profile": PROFILE_URL, "count": len(rows), "items": rows})
