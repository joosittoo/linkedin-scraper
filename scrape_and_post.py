from playwright.sync_api import sync_playwright
import os, time, random, json, hashlib, requests
from urllib.parse import urljoin

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

def dbg_env():
    li = os.getenv("LI_AT") or ""
    print("DEBUG env:",
          "LI_AT_len=", len(li),
          "MAKE_WEBHOOK_set=", bool(os.getenv("MAKE_WEBHOOK")),
          "LD_PROFILE_URL=", os.getenv("LD_PROFILE_URL"),
          "MAX_POSTS=", os.getenv("MAX_POSTS"))

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
    if not profile_url.endswith("/details/posts/"):
        profile_url = profile_url.rstrip("/") + "/details/posts/"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-dev-shm-usage"])
        context = browser.new_context(user_agent=UA, locale="es-ES", timezone_id="Europe/Madrid", viewport={"width":1366,"height":900})
        context.add_cookies([{"name":"li_at","value":li_at,"domain":".linkedin.com","path":"/","httpOnly":True,"secure":True}])
        page = context.new_page(); page.set_default_timeout(60000)
        print("NAV 1: /feed")
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        print("NAV 1 URL:", page.url)
        time.sleep(1.0)
        if any(x in page.url for x in ["/checkpoint","/login","/authwall"]):
            raise SystemExit("LI_AT inválida o expirada")
        print("NAV 2:", profile_url)
        page.goto(profile_url, wait_until="domcontentloaded")
        print("NAV 2 URL:", page.url)
        try:
            page.wait_for_selector('article, div.feed-shared-update-v2', timeout=20000)
        except:
            print("No posts yet, scroll init"); page.evaluate("window.scrollBy(0, document.body.scrollHeight)"); time.sleep(2.0)
            page.wait_for_selector('article, div.feed-shared-update-v2', timeout=20000)
        seen, results, tries = set(), [], 0
        while len(results)<max_posts and tries<80:
            arts = page.query_selector_all('article, div.feed-shared-update-v2')
            print(f"LOOP {tries}: {len(arts)} nodos")
            for art in arts:
                d = extract_post_from_article(art)
                uid = d.get('url') or hashlib.sha1((d.get('text') or "")[:200].encode()).hexdigest()
                if uid in seen: continue
                raw = (art.inner_text() or "").lower()
                if any(w in raw for w in ['reshared','volvió a compartir','compartió','repost']): continue
                seen.add(uid); results.append(d)
                if len(results)>=max_posts: break
            if len(results)>=max_posts: break
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)"); time.sleep(1.6+random.random()*1.8); tries+=1
        browser.close(); return results

def post_to_make(webhook_url, payload):
    r = requests.post(webhook_url, json=payload, headers={"Content-Type": "appli_

cat > .github/workflows/scrape.yml << 'YAML'
name: LinkedIn Scrape and Post

on:
  workflow_dispatch:
  schedule:
    - cron: '0 8 * * *'

jobs:
  build-and-run:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Upgrade pip
        run: python -m pip install --upgrade pip

      - name: Install Python deps
        run: pip install playwright requests

      - name: Install Chromium for Playwright
        run: python -m playwright install --with-deps chromium

      - name: Ping Make webhook (diagnóstico)
        env:
          MAKE_WEBHOOK: ${{ secrets.MAKE_WEBHOOK }}
        run: |
          echo "PING → MAKE_WEBHOOK"
          curl -s -o - -w "\nHTTP %{http_code}\n" -X POST "$MAKE_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d '{"ping":"ok","source":"github-actions","note":"diagnostic"}'

      - name: Run scraper (unbuffered)
        env:
          PYTHONUNBUFFERED: "1"
          LI_AT: ${{ secrets.LI_AT }}
          MAKE_WEBHOOK: ${{ secrets.MAKE_WEBHOOK }}
          LD_PROFILE_URL: ${{ secrets.LD_PROFILE_URL }}
          MAX_POSTS: ${{ secrets.MAX_POSTS }}
        run: |
          echo "=== START SCRAPER ==="
          python -u scrape_and_post.py
          echo "=== END SCRAPER ==="
YAML

git add .github/workflows/scrape.yml
git commit -m "chore: forzar logs (-u) y echos en Run scraper"
git push

cd ~/linkedin-scraper
cat scrape_and_post.py | head -20


cd ~/linkedin-scraper
cat scrape_and_post.py | head -20

cat > scrape_and_post.py << 'PY'
from playwright.sync_api import sync_playwright
import os, time, random, hashlib, requests
from urllib.parse import urljoin

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

def dbg_env():
    li = os.getenv("LI_AT") or ""
    print("DEBUG env:",
          "LI_AT_len=", len(li),
          "MAKE_WEBHOOK_set=", bool(os.getenv("MAKE_WEBHOOK")),
          "LD_PROFILE_URL=", os.getenv("LD_PROFILE_URL"),
          "MAX_POSTS=", os.getenv("MAX_POSTS"))

def normalize_text(s): 
    return " ".join(s.split()) if s else ""

def extract_post_from_article(article):
    out = {"url": None, "text": "", "author": None, "time": None, "likes": None}
    try:
        a = article.query_selector('a[href*="/activity/"], a[href*="/feed/update/"], a[href*="/posts/"]')
        if a:
            href = a.get_attribute('href')
            out['url'] = urljoin("https://www.linkedin.com", href) if href else None

        text_selectors = [
            'div.feed-shared-update-v2__description',
            'div.feed-shared-text',
            'span.break-words',
            'div[dir="ltr"]'
        ]
        longest = ""
        for sel in text_selectors:
            e = article.query_selector(sel)
            if e:
                t = e.inner_text().strip()
                if len(t) > len(longest): 
                    longest = t
        out['text'] = normalize_text(longest)

        a2 = article.query_selector('a[href*="/in/"], a[href*="/company/"]')
        if a2:
            out['author'] = a2.inner_text().strip()

        time_el = article.query_selector('time')
        if time_el:
            out['time'] = time_el.get_attribute('datetime') or time_el.inner_text().strip()

        import re
        m = re.search(r'(\d[\d.,]*)\s*(likes|me gusta|reacciones|reaction|reacciones)', article.inner_text(), re.I)
        if m:
            out['likes'] = m.group(1).replace('.', '').replace(',', '')
    except Exception as e:
        print("extract error:", e)
    return out

def scrape_profile(profile_url, li_at, max_posts=60):
    # fuerza /details/posts/
    if not profile_url.endswith("/details/posts/"):
        profile_url = profile_url.rstrip("/") + "/details/posts/"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent=UA,
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={"width": 1366, "height": 900}
        )
        # cookie de sesión
        context.add_cookies([{
            "name":"li_at","value":li_at,"domain":".linkedin.com","path":"/",
            "httpOnly":True,"secure":True
        }])

        page = context.new_page()
        page.set_default_timeout(60000)

        print("NAV 1: /feed")
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        print("NAV 1 URL:", page.url)
        time.sleep(1.0)
        if any(x in page.url for x in ["/checkpoint", "/login", "/authwall"]):
            raise SystemExit("LI_AT inválida o expirada")

        print("NAV 2:", profile_url)
        page.goto(profile_url, wait_until="domcontentloaded")
        print("NAV 2 URL:", page.url)

        try:
            page.wait_for_selector('article, div.feed-shared-update-v2', timeout=20000)
        except:
            print("No posts yet, scroll init")
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(2.0)
            page.wait_for_selector('article, div.feed-shared-update-v2', timeout=20000)

        seen, results, tries = set(), [], 0
        while len(results) < max_posts and tries < 80:
            arts = page.query_selector_all('article, div.feed-shared-update-v2')
            print(f"LOOP {tries}: {len(arts)} nodos")
            for art in arts:
                d = extract_post_from_article(art)
                uid = d.get('url') or hashlib.sha1((d.get('text') or "")[:200].encode()).hexdigest()
                if uid in seen:
                    continue
                raw = (art.inner_text() or "").lower()
                if any(w in raw for w in ['reshared','volvió a compartir','compartió','repost']):
                    continue
                seen.add(uid)
                results.append(d)
                if len(results) >= max_posts:
                    break
            if len(results) >= max_posts:
                break
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(1.6 + random.random()*1.8)
            tries += 1

        browser.close()
        return results

def post_to_make(webhook_url, payload):
    headers = {"Content-Type": "application/json"}
    r = requests.post(webhook_url, json=payload, headers=headers, timeout=60)
    print("Webhook status:", r.status_code)
    print("Webhook response (first 200):", (r.text or "")[:200])
    r.raise_for_status()

if __name__ == "__main__":
    print("== SCRAPER START ==")
    dbg_env()
    LI_AT = os.getenv("LI_AT")
    MAKE_WEBHOOK = os.getenv("MAKE_WEBHOOK")
    PROFILE_URL = os.getenv("LD_PROFILE_URL")
    MAX_POSTS = int(os.getenv("MAX_POSTS", "60"))
    if not LI_AT or not MAKE_WEBHOOK or not PROFILE_URL:
        raise SystemExit("Faltan secrets: LI_AT, MAKE_WEBHOOK o LD_PROFILE_URL.")
    rows = scrape_profile(PROFILE_URL, LI_AT, MAX_POSTS)
    print(f"Scraped {len(rows)} posts")
    post_to_make(MAKE_WEBHOOK, {"profile": PROFILE_URL, "count": len(rows), "items": rows})
    print("== SCRAPER END ==")
