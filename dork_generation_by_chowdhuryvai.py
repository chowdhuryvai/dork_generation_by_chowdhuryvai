"""
DorkGenaration - Google Dork Generator & Search Tool
==============================================
DEVELOP BY : CHOWDHURY-VAI
GITHUB     : https://github.com/chowdhuryvai

Just run: python dork_generation_by_chowdhuryvai.py
"""

import re
import os
import json
import html
import time
import threading
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from base64 import b64decode
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
APP_NAME = "DorkGen"
APP_VERSION = "2.0.0"
APP_AUTHOR = "CHOWDHURY-VAI"
APP_GITHUB = "https://github.com/chowdhuryvai"
API_KEY_FILE = "zyte_api_key.txt"

STOP_WORDS = {
    "the", "is", "at", "which", "on", "a", "an", "and", "or", "but", "in",
    "with", "to", "for", "of", "not", "no", "can", "had", "has", "have",
    "been", "was", "were", "are", "be", "this", "that", "it", "as", "by",
    "from", "you", "your", "we", "our", "their", "its", "my", "me", "he",
    "she", "they", "them", "his", "her", "who", "what", "when", "where",
    "how", "all", "each", "than", "them", "then", "so", "if", "about",
    "up", "out", "do", "did", "just", "also", "more", "some", "any",
    "very", "one", "two", "new", "like", "over", "such", "only", "other",
    "into", "page", "here", "there", "would", "could", "should", "may",
    "will", "shall", "get", "got", "make", "made", "see", "own",
    "use", "used", "using", "via", "http", "https", "www", "com", "org",
    "net", "html", "php", "asp", "jsp",
}

# ---------------------------------------------------------------------------
# Minimal HTML Parser (replaces BeautifulSoup)
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
    """Extract visible text, title, meta info, headings, and anchor hrefs."""

    def __init__(self):
        super().__init__()
        self._text_chunks = []
        self._skip = False
        self.title = ""
        self._in_title = False
        self.meta_desc = ""
        self.meta_keys = ""
        self.headings = []      # h1, h2, h3 text
        self._heading_tag = None
        self.anchor_texts = []
        self.anchor_hrefs = []
        self._in_a = False
        self._a_text = []
        self._a_href = ""
        self._in_script_style = False

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        tag_l = tag.lower()
        if tag_l in ("script", "style", "noscript"):
            self._in_script_style = True
            return
        if tag_l == "title":
            self._in_title = True
        if tag_l == "meta":
            name = (attrs_d.get("name") or "").lower()
            content = attrs_d.get("content", "")
            if name == "description":
                self.meta_desc = content
            elif name == "keywords":
                self.meta_keys = content
        if tag_l in ("h1", "h2", "h3"):
            self._heading_tag = tag_l
            self._text_chunks.append(" ")
        if tag_l == "a":
            self._in_a = True
            self._a_text = []
            self._a_href = attrs_d.get("href", "")

    def handle_endtag(self, tag):
        tag_l = tag.lower()
        if tag_l in ("script", "style", "noscript"):
            self._in_script_style = False
            return
        if tag_l == "title":
            self._in_title = False
        if self._heading_tag and tag_l == self._heading_tag:
            self.headings.append("".join(self._text_chunks[-3:]).strip())
            self._heading_tag = None
        if tag_l == "a" and self._in_a:
            self._in_a = False
            text = "".join(self._a_text).strip()
            if text:
                self.anchor_texts.append(text)
            if self._a_href:
                self.anchor_hrefs.append(self._a_href)

    def handle_data(self, data):
        if self._in_script_style:
            return
        if self._in_title:
            self.title += data
        if self._in_a:
            self._a_text.append(data)
        self._text_chunks.append(data)

    def get_text(self):
        return " ".join(self._text_chunks)


def _parse_html(raw_html):
    """Parse HTML and return the extractor instance."""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(raw_html)
    except Exception:
        pass
    return parser


# ---------------------------------------------------------------------------
# Dork Generation Logic (stdlib only)
# ---------------------------------------------------------------------------

def extract_words(raw_html):
    parser = _parse_html(raw_html)
    text = parser.get_text()
    words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", text)
    return words


def extract_keywords(raw_html):
    parser = _parse_html(raw_html)
    keywords = []
    if parser.title:
        keywords.extend(parser.title.split())
    if parser.meta_desc:
        keywords.extend(parser.meta_desc.split())
    if parser.meta_keys:
        keywords.extend(parser.meta_keys.split())
    for h in parser.headings:
        keywords.extend(h.split())
    for at in parser.anchor_texts:
        keywords.extend(at.split())
    return keywords


def generate_single_word_dorks(words):
    seen = set()
    dorks = []
    for w in words:
        wl = w.lower()
        if wl not in seen and wl not in STOP_WORDS:
            seen.add(wl)
            dorks.append('intext:"%s"' % w)
    return dorks


def generate_chained_dorks(words, max_chain=10):
    unique = list(dict.fromkeys(w for w in words if w.lower() not in STOP_WORDS))
    unique = unique[:max_chain]
    if not unique:
        return []
    and_dork = " AND ".join('intext:"%s"' % w for w in unique)
    or_dork = " OR ".join('intext:"%s"' % w for w in unique)
    return [and_dork, or_dork]


def generate_advanced_dorks(words):
    seen = set()
    dorks = []
    for w in words:
        wl = w.lower()
        if wl in STOP_WORDS or wl in seen or len(w) < 3:
            continue
        seen.add(wl)
        dorks.append("site:%s.com" % w)
        dorks.append("inurl:%s" % w)
        dorks.append('intitle:"%s"' % w)
        dorks.append('site:%s.com intitle:"%s"' % (w, w))
        dorks.append("site:%s.com inurl:%s" % (w, w))
        dorks.append('inurl:%s intitle:"%s"' % (w, w))
    return dorks


def generate_composite_dorks(words):
    seen = set()
    dorks = []
    for w in words:
        wl = w.lower()
        if wl in STOP_WORDS or wl in seen or len(w) < 3:
            continue
        seen.add(wl)
        dorks.append('intitle:"%s" intext:"%s"' % (w, w))
    return dorks


def create_dorks(raw_html):
    words = extract_words(raw_html)
    keywords = extract_keywords(raw_html)
    all_words = list(dict.fromkeys(keywords + words))
    dorks = []
    dorks.extend(generate_single_word_dorks(all_words))
    dorks.extend(generate_chained_dorks(all_words))
    dorks.extend(generate_advanced_dorks(all_words))
    dorks.extend(generate_composite_dorks(all_words))
    return dorks


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only - urllib)
# ---------------------------------------------------------------------------

_SSL_CTX = ssl.create_default_context()


def _zyte_post(api_key, payload):
    """POST to Zyte API and return parsed JSON dict."""
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        "https://api.zyte.com/v1/extract",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # Basic auth: key + empty password
    import base64
    cred = base64.b64encode(("%s:" % api_key).encode()).decode()
    req.add_header("Authorization", "Basic " + cred)

    resp = urlopen(req, timeout=60, context=_SSL_CTX)
    body = resp.read()
    return json.loads(body)


def fetch_html_via_zyte(api_key, url):
    """Fetch a page's HTML through Zyte API. Returns str or None."""
    payload = {"url": url, "httpResponseBody": True}
    result = _zyte_post(api_key, payload)
    raw = b64decode(result["httpResponseBody"])
    return raw.decode("utf-8", errors="replace")


def parse_google_results(raw_html):
    """Extract result URLs from Google search HTML (stdlib parser)."""
    parser = _parse_html(raw_html)
    urls = []
    seen = set()
    for href in parser.anchor_hrefs:
        if href.startswith("http") and "google.com" not in href and href not in seen:
            seen.add(href)
            urls.append(href)
    # Regex fallback for links inside complex markup
    for m in re.finditer(r'href="(https?://[^"]+)"', raw_html):
        u = m.group(1)
        if "google.com" not in u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


# ---------------------------------------------------------------------------
# API Key Helpers
# ---------------------------------------------------------------------------

def read_api_key():
    try:
        with open(API_KEY_FILE, "r") as f:
            return f.read().strip()
    except (FileNotFoundError, OSError):
        return ""


def save_api_key_to_file(key):
    with open(API_KEY_FILE, "w") as f:
        f.write(key)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class DorkGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("%s v%s - by %s" % (APP_NAME, APP_VERSION, APP_AUTHOR))
        self.root.geometry("1100x820")
        self.root.minsize(900, 650)
        self.root.configure(bg="#0d1117")

        self.api_key_var = tk.StringVar(value=read_api_key())
        self.dorks = []
        self.filtered_dorks = []
        self.searching = False
        self.paused_index = 0

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        BG  = "#0d1117"
        BG2 = "#161b22"
        BG3 = "#21262d"
        FG  = "#c9d1d9"
        FD  = "#8b949e"
        GRN = "#238636"
        GRNH= "#2ea043"
        BLU = "#1f6feb"
        RED = "#da3633"
        YEL = "#d29922"
        BDR = "#30363d"

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TProgressbar", troughcolor=BG3, background=GRN,
                         borderwidth=0, lightcolor=GRN, darkcolor=GRN)

        # -- Branding Bar --
        brand = tk.Frame(self.root, bg=BG2, height=48)
        brand.pack(fill=tk.X, side=tk.TOP)
        brand.pack_propagate(False)
        tk.Label(brand, text="  %s" % APP_NAME, font=("Consolas", 16, "bold"),
                 bg=BG2, fg=GRN).pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(brand, text="v%s" % APP_VERSION, font=("Consolas", 10),
                 bg=BG2, fg=FD).pack(side=tk.LEFT, padx=4)
        tk.Label(brand, text="by %s" % APP_AUTHOR, font=("Consolas", 10, "italic"),
                 bg=BG2, fg=YEL).pack(side=tk.RIGHT, padx=8)
        tk.Label(brand, text=APP_GITHUB, font=("Consolas", 9),
                 bg=BG2, fg=BLU).pack(side=tk.RIGHT)

        # -- Scrollable Canvas --
        canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        v_scroll = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=canvas.yview)
        self.main_frame = tk.Frame(canvas, bg=BG)
        self.main_frame.bind("<Configure>",
                             lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        pad = dict(padx=10, pady=4)

        # ---- TARGET URL ----
        self._section("TARGET", self.main_frame)
        uf = tk.Frame(self.main_frame, bg=BG2, bd=1, relief="flat")
        uf.pack(fill=tk.X, **pad)
        tk.Label(uf, text="Site URL:", font=("Consolas", 10),
                 bg=BG2, fg=FG).pack(side=tk.LEFT, padx=(8, 4), pady=6)
        self.entry = tk.Entry(uf, font=("Consolas", 11), bg=BG3, fg="white",
                              insertbackground="white", relief="flat", bd=0)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=6, ipady=4)
        self.gen_btn = tk.Button(uf, text="Generate Dorks", font=("Consolas", 10, "bold"),
                                  bg=GRN, fg="white", activebackground=GRNH,
                                  activeforeground="white", relief="flat", bd=0,
                                  cursor="hand2", command=self.generate_dorks)
        self.gen_btn.pack(side=tk.LEFT, padx=(4, 8), pady=6, ipadx=10, ipady=4)

        # ---- CONTROLS ----
        cf = tk.Frame(self.main_frame, bg=BG2, bd=1, relief="flat")
        cf.pack(fill=tk.X, **pad)
        self.run_btn = tk.Button(cf, text="Run Search", font=("Consolas", 10, "bold"),
                                  bg=BLU, fg="white", activebackground="#388bfd",
                                  activeforeground="white", relief="flat", bd=0,
                                  cursor="hand2", state=tk.DISABLED,
                                  command=self.run_search)
        self.run_btn.pack(side=tk.LEFT, padx=(8, 4), pady=6, ipadx=10, ipady=4)
        self.pause_btn = tk.Button(cf, text="Pause", font=("Consolas", 10),
                                    bg=YEL, fg="black", activebackground="#e3b341",
                                    relief="flat", bd=0, cursor="hand2",
                                    state=tk.DISABLED, command=self.pause_search)
        self.pause_btn.pack(side=tk.LEFT, padx=4, pady=6, ipadx=8, ipady=4)
        self.progress = ttk.Progressbar(cf, orient="horizontal", length=300,
                                         mode="determinate", style="TProgressbar")
        self.progress.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True, pady=6)
        self.prog_lbl = tk.Label(cf, text="0 / 0", font=("Consolas", 9),
                                  bg=BG2, fg=FD)
        self.prog_lbl.pack(side=tk.LEFT, padx=4)

        # ---- FILTER ----
        ff = tk.Frame(self.main_frame, bg=BG2, bd=1, relief="flat")
        ff.pack(fill=tk.X, **pad)
        tk.Label(ff, text="Filter:", font=("Consolas", 10),
                 bg=BG2, fg=FG).pack(side=tk.LEFT, padx=(8, 4), pady=6)
        self.filt_ent = tk.Entry(ff, font=("Consolas", 10), bg=BG3, fg="white",
                                  insertbackground="white", relief="flat", bd=0)
        self.filt_ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=6, ipady=4)
        tk.Button(ff, text="Apply", font=("Consolas", 9), bg=BLU, fg="white",
                  relief="flat", bd=0, cursor="hand2",
                  command=self.apply_filter).pack(side=tk.LEFT, padx=4, pady=6, ipadx=6, ipady=2)
        tk.Button(ff, text="Remove", font=("Consolas", 9), bg=BG3, fg=FG,
                  activebackground=BDR, relief="flat", bd=0, cursor="hand2",
                  command=self.remove_filter).pack(side=tk.LEFT, padx=(0, 8), pady=6, ipadx=6, ipady=2)

        # ---- DORKS ----
        self._section("GENERATED DORKS", self.main_frame)
        do = tk.Frame(self.main_frame, bg=BG2, bd=1, relief="flat")
        do.pack(fill=tk.BOTH, expand=True, **pad)
        self.dorks_lbl = tk.Label(do, text="Dorks: 0", font=("Consolas", 10, "bold"),
                                   bg=BG2, fg=FG)
        self.dorks_lbl.pack(anchor="w", padx=8, pady=(6, 0))
        dc = tk.Frame(do, bg=BG2)
        dc.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        self.dorks_txt = tk.Text(dc, font=("Consolas", 9), bg=BG3, fg=FG,
                                  insertbackground="white", selectbackground=BLU,
                                  selectforeground="white", relief="flat", bd=0,
                                  wrap=tk.NONE, undo=True)
        ds = ttk.Scrollbar(dc, orient=tk.VERTICAL, command=self.dorks_txt.yview)
        self.dorks_txt.configure(yscrollcommand=ds.set)
        ds.pack(side=tk.RIGHT, fill=tk.Y)
        self.dorks_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        db = tk.Frame(do, bg=BG2)
        db.pack(fill=tk.X, padx=8, pady=(0, 6))
        for t, c in [("Save", self.save_dorks_to_file),
                      ("De-Dup", self.remove_dorks_duplicates),
                      ("Cleanup", self.cleanup_dorks),
                      ("Remove Sel", self.remove_selected_dorks)]:
            tk.Button(db, text=t, font=("Consolas", 9), bg=BG3, fg=FG,
                      activebackground=BDR, relief="flat", bd=0, cursor="hand2",
                      command=c).pack(side=tk.LEFT, padx=3, ipadx=6, ipady=3)

        # ---- RESULTS ----
        self._section("SEARCH RESULTS", self.main_frame)
        ro = tk.Frame(self.main_frame, bg=BG2, bd=1, relief="flat")
        ro.pack(fill=tk.BOTH, expand=True, **pad)
        self.res_lbl = tk.Label(ro, text="Results: 0", font=("Consolas", 10, "bold"),
                                 bg=BG2, fg=FG)
        self.res_lbl.pack(anchor="w", padx=8, pady=(6, 0))
        rc = tk.Frame(ro, bg=BG2)
        rc.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        self.res_txt = tk.Text(rc, font=("Consolas", 9), bg=BG3, fg=FG,
                                insertbackground="white", selectbackground=BLU,
                                selectforeground="white", relief="flat", bd=0,
                                wrap=tk.NONE, undo=True)
        rs = ttk.Scrollbar(rc, orient=tk.VERTICAL, command=self.res_txt.yview)
        self.res_txt.configure(yscrollcommand=rs.set)
        rs.pack(side=tk.RIGHT, fill=tk.Y)
        self.res_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rb = tk.Frame(ro, bg=BG2)
        rb.pack(fill=tk.X, padx=8, pady=(0, 6))
        for t, c in [("Save", self.save_results_to_file),
                      ("De-Dup", self.remove_results_duplicates),
                      ("Remove Sel", self.remove_selected_results)]:
            tk.Button(rb, text=t, font=("Consolas", 9), bg=BG3, fg=FG,
                      activebackground=BDR, relief="flat", bd=0, cursor="hand2",
                      command=c).pack(side=tk.LEFT, padx=3, ipadx=6, ipady=3)

        # ---- LOG ----
        self._section("LOG", self.main_frame)
        lo = tk.Frame(self.main_frame, bg=BG2, bd=1, relief="flat")
        lo.pack(fill=tk.BOTH, **pad)
        lc = tk.Frame(lo, bg=BG2)
        lc.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.log_txt = tk.Text(lc, font=("Consolas", 9), bg=BG, fg=FD,
                                insertbackground="white", relief="flat", bd=0, height=8)
        ls = ttk.Scrollbar(lc, orient=tk.VERTICAL, command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=ls.set)
        ls.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_txt.tag_config("info", foreground=FD)
        self.log_txt.tag_config("success", foreground=GRN)
        self.log_txt.tag_config("warning", foreground=YEL)
        self.log_txt.tag_config("error", foreground=RED)

        # ---- API KEY ----
        af = tk.Frame(self.main_frame, bg=BG2, bd=1, relief="flat")
        af.pack(fill=tk.X, **pad)
        tk.Label(af, text="Zyte API Key:", font=("Consolas", 10),
                 bg=BG2, fg=FG).pack(side=tk.LEFT, padx=(8, 4), pady=6)
        self.api_ent = tk.Entry(af, textvariable=self.api_key_var,
                                 font=("Consolas", 10), bg=BG3, fg="white",
                                 show="*", insertbackground="white",
                                 relief="flat", bd=0)
        self.api_ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=6, ipady=4)
        tk.Button(af, text="Show", font=("Consolas", 9), bg=BG3, fg=FG,
                  activebackground=BDR, relief="flat", bd=0, cursor="hand2",
                  command=self._toggle_key).pack(side=tk.LEFT, padx=2, pady=6, ipadx=4, ipady=2)
        tk.Button(af, text="Save Key", font=("Consolas", 9, "bold"), bg=GRN, fg="white",
                  activebackground=GRNH, relief="flat", bd=0, cursor="hand2",
                  command=self.save_api_key).pack(side=tk.LEFT, padx=(2, 8), pady=6, ipadx=6, ipady=2)

        # -- Footer --
        ft = tk.Frame(self.root, bg=BG2, height=28)
        ft.pack(fill=tk.X, side=tk.BOTTOM)
        ft.pack_propagate(False)
        tk.Label(ft, text="Developed by %s  |  %s" % (APP_AUTHOR, APP_GITHUB),
                 font=("Consolas", 9), bg=BG2, fg=FD).pack(side=tk.LEFT, padx=10)
        tk.Label(ft, text="Google Dork Generator & Search Tool",
                 font=("Consolas", 9), bg=BG2, fg=FD).pack(side=tk.RIGHT, padx=10)

    def _section(self, text, parent):
        tk.Label(parent, text="  %s" % text, font=("Consolas", 9, "bold"),
                 bg="#0d1117", fg="#8b949e", anchor="w").pack(fill=tk.X, padx=10, pady=(6, 0))

    def _toggle_key(self):
        self.api_ent.configure(show="" if self.api_ent.cget("show") == "*" else "*")

    # ------------------------------------------------------------------
    # Thread-safe helpers
    # ------------------------------------------------------------------
    def _ui(self, func, *a):
        self.root.after(0, lambda: func(*a))

    def log(self, msg, level="info"):
        def _d():
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_txt.insert(tk.END, "[%s] %s\n" % (ts, msg), level)
            self.log_txt.see(tk.END)
        self._ui(_d)

    def _upd_dorks_lbl(self):
        lines = self.dorks_txt.get("1.0", tk.END).splitlines()
        c = len([l for l in lines if l.strip()])
        self.dorks_lbl.config(text="Dorks: %d" % c)

    def _upd_res_lbl(self):
        lines = self.res_txt.get("1.0", tk.END).splitlines()
        c = len([l for l in lines if l.strip()])
        self.res_lbl.config(text="Results: %d" % c)

    def _upd_prog(self, cur, tot):
        def _d():
            self.progress["maximum"] = tot
            self.progress["value"] = cur
            self.prog_lbl.config(text="%d / %d" % (cur, tot))
        self._ui(_d)

    # ------------------------------------------------------------------
    # Generate Dorks
    # ------------------------------------------------------------------
    def generate_dorks(self):
        url = self.entry.get().strip()
        if not url:
            messagebox.showerror("Input Error", "Please enter a target site URL.")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.entry.delete(0, tk.END)
            self.entry.insert(0, url)

        self.log("Fetching site HTML & generating dorks...", "info")
        self.gen_btn.config(state=tk.DISABLED, text="Working...")
        self.run_btn.config(state=tk.DISABLED)

        def _worker():
            try:
                key = self.api_key_var.get().strip()
                if not key:
                    self._ui(lambda: messagebox.showerror("API Key",
                              "Please enter your Zyte API key."))
                    self.log("No API key provided.", "error")
                    self._ui(lambda: self.gen_btn.config(state=tk.NORMAL, text="Generate Dorks"))
                    return

                self.log("Fetching HTML for: %s" % url, "info")
                html_src = fetch_html_via_zyte(key, url)
                self.log("HTML fetched successfully.", "success")

                self.dorks = create_dorks(html_src)
                self.filtered_dorks = self.dorks[:]

                def _upd():
                    self.dorks_txt.delete("1.0", tk.END)
                    if self.dorks:
                        self.dorks_txt.insert(tk.END, "\n".join(self.dorks) + "\n")
                    self._upd_dorks_lbl()
                    self.run_btn.config(state=tk.NORMAL)
                    self.gen_btn.config(state=tk.NORMAL, text="Generate Dorks")
                    self.log("Generated %d dorks." % len(self.dorks), "success")
                self._ui(_upd)

            except (HTTPError, URLError, OSError) as e:
                self.log("Fetch failed: %s" % e, "error")
                self._ui(lambda: messagebox.showerror("Fetch Error", str(e)))
                self._ui(lambda: self.gen_btn.config(state=tk.NORMAL, text="Generate Dorks"))
            except Exception as e:
                self.log("Unexpected error: %s" % e, "error")
                self._ui(lambda: self.gen_btn.config(state=tk.NORMAL, text="Generate Dorks"))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def run_search(self):
        if not self.filtered_dorks:
            messagebox.showinfo("Info", "No dorks to search. Generate dorks first.")
            return
        self.log("Starting Google search...", "info")
        self.searching = True
        self.paused_index = 0
        self.run_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.progress["maximum"] = len(self.filtered_dorks)
        self.progress["value"] = 0
        threading.Thread(target=self._search_worker, daemon=True).start()

    def pause_search(self):
        self.searching = False
        self.log("Search paused.", "warning")
        self.pause_btn.config(state=tk.DISABLED)
        self.run_btn.config(state=tk.NORMAL, text="Continue Search")

    def _search_worker(self):
        key = self.api_key_var.get().strip()
        total = len(self.filtered_dorks)
        found = False

        for idx in range(self.paused_index, total):
            if not self.searching:
                self.paused_index = idx
                return

            dork = self.filtered_dorks[idx]
            self._upd_prog(idx + 1, total)
            self.log("[%d/%d] %s" % (idx + 1, total, dork), "info")

            try:
                g_url = "https://www.google.com/search?q=%s" % quote(dork)
                result_json = _zyte_post(key, {"url": g_url, "httpResponseBody": True})
                html_src = b64decode(result_json["httpResponseBody"]).decode("utf-8", errors="replace")
                results = parse_google_results(html_src)

                if results:
                    found = True
                    def _add(rlist=results):
                        for r in rlist:
                            self.res_txt.insert(tk.END, r + "\n")
                        self.res_txt.see(tk.END)
                        self._upd_res_lbl()
                    self._ui(_add)

                self.log("  -> %d result(s)" % len(results),
                         "success" if results else "info")

            except (HTTPError, URLError, OSError) as e:
                self.log("  -> API Error: %s" % e, "error")
            except Exception as e:
                self.log("  -> Error: %s" % e, "error")

            time.sleep(1)

        self.paused_index = 0
        self._upd_prog(total, total)
        self.log("Search completed." if found else "Search completed (no results).",
                 "success" if found else "warning")
        self._ui(lambda: self.pause_btn.config(state=tk.DISABLED))
        self._ui(lambda: self.run_btn.config(state=tk.NORMAL, text="Run Search"))

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def save_dorks_to_file(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt",
                                          filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.dorks_txt.get("1.0", tk.END))
            self.log("Dorks saved -> %s" % p, "success")

    def save_results_to_file(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt",
                                          filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.res_txt.get("1.0", tk.END))
            self.log("Results saved -> %s" % p, "success")

    # ------------------------------------------------------------------
    # Dork Management
    # ------------------------------------------------------------------
    def remove_dorks_duplicates(self):
        lines = self.dorks_txt.get("1.0", tk.END).splitlines()
        unique = list(dict.fromkeys(l for l in lines if l.strip()))
        rem = len([l for l in lines if l.strip()]) - len(unique)
        self.dorks_txt.delete("1.0", tk.END)
        if unique:
            self.dorks_txt.insert(tk.END, "\n".join(unique) + "\n")
        self.filtered_dorks = unique
        self._upd_dorks_lbl()
        self.log("Removed %d duplicate dork(s)." % rem, "success")

    def remove_results_duplicates(self):
        lines = self.res_txt.get("1.0", tk.END).splitlines()
        unique = list(dict.fromkeys(l for l in lines if l.strip()))
        rem = len([l for l in lines if l.strip()]) - len(unique)
        self.res_txt.delete("1.0", tk.END)
        if unique:
            self.res_txt.insert(tk.END, "\n".join(unique) + "\n")
        self._upd_res_lbl()
        self.log("Removed %d duplicate result(s)." % rem, "success")

    def cleanup_dorks(self):
        lines = self.dorks_txt.get("1.0", tk.END).splitlines()
        cleaned = []
        for d in lines:
            d = d.strip()
            if not d:
                continue
            if len(d) >= 10 and any(op in d for op in
                                     ("site:", "inurl:", "intitle:", "intext:", "AND", "OR")):
                cleaned.append(d)
        rem = len([l for l in lines if l.strip()]) - len(cleaned)
        self.dorks_txt.delete("1.0", tk.END)
        if cleaned:
            self.dorks_txt.insert(tk.END, "\n".join(cleaned) + "\n")
        self.filtered_dorks = cleaned
        self._upd_dorks_lbl()
        self.log("Cleaned %d invalid dork(s)." % rem, "success")

    def apply_filter(self):
        crit = self.filt_ent.get().strip()
        if not crit:
            return
        self.filtered_dorks = [d for d in self.dorks if crit.lower() in d.lower()]
        self.dorks_txt.delete("1.0", tk.END)
        if self.filtered_dorks:
            self.dorks_txt.insert(tk.END, "\n".join(self.filtered_dorks) + "\n")
        self._upd_dorks_lbl()
        self.log("Filter '%s': %d match(es)." % (crit, len(self.filtered_dorks)), "info")

    def remove_filter(self):
        self.filtered_dorks = self.dorks[:]
        self.dorks_txt.delete("1.0", tk.END)
        if self.filtered_dorks:
            self.dorks_txt.insert(tk.END, "\n".join(self.filtered_dorks) + "\n")
        self._upd_dorks_lbl()
        self.log("Filter removed.", "info")

    def remove_selected_dorks(self):
        try:
            sel = self.dorks_txt.tag_ranges(tk.SEL)
            if not sel:
                messagebox.showinfo("Info", "Select text in the dorks area first.")
                return
            s = int(self.dorks_txt.index(sel[0]).split(".")[0])
            e = int(self.dorks_txt.index(sel[1]).split(".")[0])
            slines = set(range(s, e + 1))
            lines = self.dorks_txt.get("1.0", tk.END).splitlines()
            rem = [l for i, l in enumerate(lines, 1) if i not in slines and l.strip()]
            self.filtered_dorks = rem
            self.dorks_txt.delete("1.0", tk.END)
            if rem:
                self.dorks_txt.insert(tk.END, "\n".join(rem) + "\n")
            self._upd_dorks_lbl()
            self.log("Removed %d selected line(s)." % len(slines), "info")
        except Exception as ex:
            self.log("Selection error: %s" % ex, "error")

    def remove_selected_results(self):
        try:
            sel = self.res_txt.tag_ranges(tk.SEL)
            if not sel:
                messagebox.showinfo("Info", "Select text in the results area first.")
                return
            s = int(self.res_txt.index(sel[0]).split(".")[0])
            e = int(self.res_txt.index(sel[1]).split(".")[0])
            slines = set(range(s, e + 1))
            lines = self.res_txt.get("1.0", tk.END).splitlines()
            rem = [l for i, l in enumerate(lines, 1) if i not in slines and l.strip()]
            self.res_txt.delete("1.0", tk.END)
            if rem:
                self.res_txt.insert(tk.END, "\n".join(rem) + "\n")
            self._upd_res_lbl()
            self.log("Removed %d selected result(s)." % len(slines), "info")
        except Exception as ex:
            self.log("Selection error: %s" % ex, "error")

    def save_api_key(self):
        save_api_key_to_file(self.api_key_var.get().strip())
        self.log("API key saved.", "success")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    DorkGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
