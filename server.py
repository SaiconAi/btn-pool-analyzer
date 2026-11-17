import json, os, re, time, threading, urllib.parse, urllib.request, urllib.error, http.cookiejar, webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HOST, PORT = "127.0.0.1", 8765
BTN = "0x6C417845fACc97ebCE84FBfEE9A7460b0E5cfCf3"
BASESCAN = "https://basescan.org"
POOL_WORKER = "https://btn-pool-api.luisedt.workers.dev"

cookiejar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))
request_lock = threading.Lock()
last_request = 0.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

def throttle(gap=0.18):
    global last_request
    with request_lock:
        now = time.time()
        wait = gap - (now - last_request)
        if wait > 0:
            time.sleep(wait)
        last_request = time.time()

def fetch_html(url, referer=None, retries=5):
    last = ""
    for attempt in range(retries):
        throttle()
        try:
            h = dict(HEADERS)
            if referer:
                h["Referer"] = referer
            req = urllib.request.Request(url, headers=h, method="GET")
            with opener.open(req, timeout=30) as resp:
                raw = resp.read()
            text = raw.decode("utf-8", "replace")

            low = text.lower()
            if "just a moment" in low and "cloudflare" in low:
                raise RuntimeError("BaseScan Cloudflare challenge received")
            if "access denied" in low:
                raise RuntimeError("BaseScan denied the request")
            return text
        except Exception as e:
            last = str(e)
            time.sleep(min(8, 0.8 * (attempt + 1)))
    raise RuntimeError(last or "BaseScan request failed")

def init_session(wallet):
    url = f"{BASESCAN}/token/{BTN}?a={urllib.parse.quote(wallet)}"
    html = fetch_html(url)

    patterns = [
        r"var\s+sid\s*=\s*['\"]([^'\"]+)['\"]",
        r"\bsid\s*=\s*['\"]([^'\"]+)['\"]",
        r"[?&]sid=([A-Za-z0-9_-]+)",
    ]
    sid = ""
    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m:
            sid = m.group(1)
            break

    if not sid:
        raise RuntimeError("Could not obtain BaseScan session SID. BaseScan may have changed its page format.")

    return sid, url

def fetch_transfer_page(wallet, sid, page, page_size=100):
    params = {
        "m": "normal",
        "contractAddress": BTN,
        "a": wallet,
        "sid": sid,
        "p": str(page),
        "ps": str(page_size),
    }
    url = BASESCAN + "/token/generic-tokentxns2?" + urllib.parse.urlencode(params)
    referer = f"{BASESCAN}/token/{BTN}?a={wallet}"
    return fetch_html(url, referer=referer)

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[HTTP]", fmt % args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def send_json(self, obj, code=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)

        if p.path == "/health":
            self.send_json({"ok": True, "source": "BaseScan direct table"})
            return

        if p.path == "/pool-api":
            # Forward pool queries from the local server so the Worker URL
            # is not displayed in the app or exposed in browser-side code.
            allowed = ("start", "end", "limit", "cursor")
            forwarded = {
                key: (q.get(key) or [""])[0]
                for key in allowed
                if (q.get(key) or [""])[0] != ""
            }
            target = POOL_WORKER + "?" + urllib.parse.urlencode(forwarded)
            try:
                req = urllib.request.Request(
                    target,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": HEADERS["User-Agent"],
                    },
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = resp.read()
                    status = resp.status
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except urllib.error.HTTPError as e:
                body = e.read()
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_json({"ok": False, "error": f"Pool Worker proxy error: {e}"}, 502)
            return

        if p.path == "/basescan-init":
            wallet = (q.get("wallet") or [""])[0].strip()
            if not (wallet.startswith("0x") and len(wallet) == 42):
                self.send_json({"ok": False, "error": "Invalid wallet"}, 400)
                return
            try:
                sid, referer = init_session(wallet)
                self.send_json({"ok": True, "sid": sid})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 502)
            return

        if p.path == "/basescan-page":
            wallet = (q.get("wallet") or [""])[0].strip()
            sid = (q.get("sid") or [""])[0].strip()
            try:
                page = max(1, int((q.get("page") or ["1"])[0]))
            except:
                page = 1
            try:
                html = fetch_transfer_page(wallet, sid, page, 100)

                # BaseScan/Etherscan's internal table fragment commonly embeds:
                # var totaltxns = '12345'
                total = None
                patterns = [
                    r"var\s+totaltxns\s*=\s*['\"]([\d,]+)['\"]",
                    r"\btotaltxns\s*=\s*['\"]([\d,]+)['\"]",
                    r"id=['\"]totaltxns['\"][^>]*>\s*([\d,]+)",
                    r"total\s+of\s+([\d,]+)\s+transactions",
                ]
                for pat in patterns:
                    m = re.search(pat, html, re.I)
                    if m:
                        try:
                            total = int(m.group(1).replace(",", ""))
                            break
                        except:
                            pass

                # Also expose any page-count variable BaseScan may embed.
                total_pages = None
                for pat in [
                    r"var\s+totalpages\s*=\s*['\"]?(\d+)",
                    r"\btotalpages\s*=\s*['\"]?(\d+)",
                    r"var\s+totalPages\s*=\s*['\"]?(\d+)",
                ]:
                    m = re.search(pat, html, re.I)
                    if m:
                        try:
                            total_pages = int(m.group(1))
                            break
                        except:
                            pass

                self.send_json({
                    "ok": True,
                    "page": page,
                    "html": html,
                    "total_txns": total,
                    "total_pages": total_pages,
                })
            except Exception as e:
                self.send_json({"ok": False, "error": str(e), "page": page}, 502)
            return

        return super().do_GET()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    url = f"http://{HOST}:{PORT}/index.html"
    print("=" * 78)
    print(" BTN POOL & WALLET ANALYZER V34 - SAICON")
    print(" No Blockscout. No RPC scan. No API key.")
    print(" Pool requests are proxied locally; wallet history paginates BaseScan's transfer table.")
    print(" URL:", url)
    print("=" * 78)

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
