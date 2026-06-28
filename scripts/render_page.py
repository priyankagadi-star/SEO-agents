#!/usr/bin/env python3
"""Generic production renderer: run_dir + inputs.json -> page.html + content.md.

Data-driven (no per-page hardcoding): reads the pipeline's state/package, lays
the sections out in outline order, auto-detecting step lists and capability
cards, and renders byline + JSON-LD (with author sameAs) + sources + FAQ.
Usage: python scripts/render_page.py <run_dir> <inputs.json>
"""
import html as _html
import json
import re
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
INPUTS = Path(sys.argv[2])
state = json.loads((RUN / "state.json").read_text())
pkg = json.loads((RUN / "package_out.json").read_text())
inp = json.loads(INPUTS.read_text())
rd = inp.get("research_dossier", {})
state["brand_assets"] = json.loads(Path("brands/siftly.ai/brand_assets.json").read_text())

H1 = rd.get("suggested_h1") or pkg["title_variants"][0]
LEAD = rd.get("quotable_intro") or pkg.get("meta", "")
TITLE = (pkg["title_variants"][0] + " | Siftly")
META = pkg.get("meta", "")
BYLINE = pkg.get("byline_line") or ""
CTA_LABEL = rd.get("primary_cta", "Book a demo")
TRENDS = rd.get("trend_signals", [])
sections = state.get("sections", {})
outline = (state.get("outline") or {}).get("sections", [])
faq = state.get("faq", [])
author = (state.get("brand_assets") or {}).get("author") or {}

FACT = re.compile(r"\s*\(fact:[a-z0-9\-]+\)", re.I)
VERIFY = re.compile(r"\s*\[VERIFY[^\]]*\]")   # never render an unresolved flag
def strip_facts(t): return VERIFY.sub("", FACT.sub("", t or ""))
def esc(t): return _html.escape(strip_facts(t), quote=False)
def md_inline(t):
    s = esc(t)
    s = re.sub(r"\[([^\]]+)\]\((/[^)\s]+|https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)  # md links
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)                                  # bold
    s = re.sub(r"(?<!\w)\*(?=\S)(.+?)(?<=\S)\*(?!\w)", r"<em>\1</em>", s)                     # italic
    return s.replace("**", "").replace("](", "] (")   # strip any stray markers
def blocks(t): return [b.strip() for b in re.split(r"\n\s*\n", strip_facts(t)) if b.strip()]

def md_table(b):
    """Convert a GitHub-style markdown table block to a styled HTML table."""
    lines = [l for l in b.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2 or not re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[1]):
        return None
    def cells(l): return [c.strip() for c in l.strip().strip("|").split("|")]
    head = cells(lines[0]); rows = [cells(l) for l in lines[2:] if l.strip()]
    th = "".join(f"<th>{md_inline(c)}</th>" for c in head)
    tb = "".join("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="ctab"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>'

def prose(body):
    out = []
    for b in blocks(body):
        if b.lstrip().startswith("|") and (t := md_table(b)):
            out.append(t); continue
        m = re.fullmatch(r"\*\*(.+?)\*\*", b)
        if m:
            out.append(f'<h3 class="sub">{md_inline(m.group(1))}</h3>')
        elif re.match(r"^#{2,6}\s+", b):                       # stray markdown header
            htxt = md_inline(re.sub(r"^#{2,6}\s+", "", b))
            out.append(f'<h3 class="sub">{htxt}</h3>')
        else:
            out.append(f"<p>{md_inline(b)}</p>")
    return "\n".join(out)

def as_steps(body):
    bl = blocks(body); pairs = []; i = 0
    while i < len(bl):
        m = re.fullmatch(r"\*\*(.+?)\*\*", bl[i])
        if m and i + 1 < len(bl):
            pairs.append((re.sub(r"^\d+[\.\)]\s*", "", m.group(1)), bl[i + 1])); i += 2
        else: i += 1
    if not pairs: return None
    ic = ["🔍", "✍️", "📈", "🎯", "⚡", "🛠️"]
    return '<div class="steps">' + "".join(
        f'<div class="step"><div class="step-num">{n}</div><div class="step-ico">{ic[(n-1)%len(ic)]}</div>'
        f'<h3>{md_inline(t)}</h3><p>{md_inline(d)}</p></div>' for n, (t, d) in enumerate(pairs, 1)) + "</div>"

def as_feats(body):
    cards = []; ic = ["📡", "🔗", "✍️", "💬", "📣", "🛒", "📊", "🎯"]
    for b in blocks(body):
        m = re.match(r"\*\*(.+?)\*\*\s*(.*)", b, re.S)
        if not m: continue
        cards.append((m.group(1).strip().rstrip("."), m.group(2).strip()))
    if len(cards) < 3: return None
    return '<div class="feat-grid">' + "".join(
        f'<div class="feat"><div class="feat-ico">{ic[i%len(ic)]}</div><h3>{md_inline(t)}</h3><p>{md_inline(d)}</p></div>'
        for i, (t, d) in enumerate(cards)) + "</div>"

def _n(t): return (t or "").lower()

def classify_role(idx, total, sid, h2, body):
    """Detect a section's role by content, not just id — outlines may use
    semantic ids (answer_first/proof/cta) OR generic ones (s1..s8)."""
    s, h, b = _n(sid), _n(h2), body or ""
    # tool_widget / value_prop are UI placeholder slots on free-tool / landing
    # page-types. The writer sometimes fills them with mock HTML; we render a
    # clean tool-widget skeleton instead and ignore the model output.
    if s in ("tool_widget", "widget", "value_prop", "tool"):
        return "tool_widget"
    if s == "faq" or "frequently asked" in h or h.strip() in ("faq", "faqs") or b.count("### ") >= 2:
        return "faq"
    if s == "proof" or "real results" in h or "results from real" in h or re.search(r'(^|\n)\s*>\s*"', b):
        return "proof"
    if s == "cta" or "primary cta" in h or h.startswith("cta") or "ready to" in h or "call to action" in h:
        return "cta"
    if idx == 0 and (s in ("answer_first", "answer", "hero") or "answer-first" in h or "lead:" in h):
        return "hero"
    return "body"

_KICK_KW = [("fail", "The problem"), ("problem", "The problem"), ("matters", "The problem"),
            ("how ", "How it works"), ("works", "How it works"), ("capabilit", "What you get"),
            ("deliver", "What you get"), ("different", "Why Siftly"), ("vs ", "Why Siftly"),
            ("why now", "Why now"), ("measurable", "Why now")]
def kicker_for(sid, h2):
    semantic = {"problem": "The problem", "how_it_works": "How it works", "capabilities": "What you get",
                "differentiators": "Why Siftly", "market_context": "Why now"}
    if sid in semantic:
        return semantic[sid]
    for kw, k in _KICK_KW:
        if kw in _n(h2):
            return k
    return ""

def clean_h2(h2):
    """An h2 that is really a brief instruction ('Answer-first lead: …',
    'Primary CTA block: …') is not a headline — strip to its real headline or drop."""
    t = (h2 or "").strip()
    if re.match(r"(?i)^(answer-first lead|primary cta block|cta block|call to action|cta button|hero)\b", t) or len(t) > 95:
        tail = re.split(r"[:—]", t)[-1].strip()           # instructions use ':' or '—'
        if re.search(r"(?i)primary|secondary|button|link to|→|/[a-z]", tail) or not 8 < len(tail) <= 80:
            return ""                                       # still an instruction → drop, caller defaults
        return tail
    return t

def clean_body(body, h2):
    """Strip embedded markdown headers (## repeating the section heading; ###
    become subheads) and blockquote markers so prose() renders cleanly."""
    out = []
    for ln in (body or "").split("\n"):
        m = re.match(r"\s*#{2,6}\s+(.*)", ln)
        if m:
            txt = m.group(1).strip()
            if _n(txt) == _n(h2):
                continue
            out.append(f"**{txt}**")
        else:
            out.append(re.sub(r"^\s*>\s?", "", ln))
    return "\n".join(out)

def render_section(h2, body, soft, sid=""):
    body = clean_body(body, h2)
    inner = as_steps(body) or as_feats(body) or prose(body)
    kh2 = clean_h2(h2)
    kick = kicker_for(sid, h2)
    kh = f'<span class="kicker">{esc(kick)}</span>' if kick else ""
    head = (f'<div class="band-head">{kh}<h2>{esc(kh2)}</h2></div>' if kh2
            else (f'<div class="band-head">{kh}</div>' if kh else ""))
    cls = "band band-soft" if soft else "band"
    return f'<section class="{cls}"><div class="wrap">{head}{inner}</div></section>'

# body sections — skip hero / faq / cta / proof (rendered separately), by ROLE
roles = {}
body_html = []
soft = False
total = len(outline)
for idx, s in enumerate(outline):
    sid = s.get("id")
    if sid not in sections:
        continue
    roles[sid] = classify_role(idx, total, sid, s.get("h2", ""), sections[sid])
    if roles[sid] != "body":
        continue
    body_html.append(render_section(s.get("h2", ""), sections[sid], soft, sid))
    soft = not soft
body_html = "\n".join(body_html)

# trend band
# Tool-widget placeholder: clean dev-team slot for the interactive UI.
# Only emitted when the outline declares a tool_widget role (free-tool page-type).
tool_widget_html = ""
if any(r == "tool_widget" for r in roles.values()):
    seed = (inp.get("seed_keyword") or "").lower().replace(" ", "-") or "tool"
    tool_widget_html = (
        f'<section class="tool-widget-band"><div class="wrap" style="max-width:780px">'
        f'<div id="tool-widget" data-tool="{esc(seed)}" '
        f'data-target-url="{esc(rd.get("target_url",""))}" '
        f'aria-label="Tool widget — replace with real interactive UI">'
        f'<div class="tool-widget-placeholder">'
        f'<div class="twp-form"><label class="twp-label" for="tw-url">'
        f'Enter your URL to {esc(inp.get("seed_keyword","check"))}</label>'
        f'<div class="twp-row"><input id="tw-url" class="twp-input" type="url" '
        f'placeholder="https://example.com" autocomplete="off">'
        f'<button class="btn btn-primary twp-btn" type="button">Check</button></div>'
        f'<p class="twp-note">Interactive tool — plug your real widget into this slot. '
        f'No signup required.</p></div></div></div></div></section>')

trends_html = ""
if TRENDS:
    cards = "".join(f'<div class="trend"><span class="trend-icon">↗</span><p>{esc(t)}</p></div>' for t in TRENDS)
    trends_html = f'<section class="trend-band"><div class="wrap"><div class="band-head"><span class="kicker">Why now</span><h2>The shift to AI search is measurable</h2></div><div class="trend-grid">{cards}</div></div></section>'

# proof quotes from schema Reviews
reviews = [b for b in pkg["schema_jsonld"].get("@graph", []) if b.get("@type") == "Review"]
ORG = {"Manuel": ("Domu", "GTM"), "Emi": ("KIWABI", "Founder"), "Niigawa Kyouhei": ("BROMO", "CEO")}
def quote(r):
    n = r.get("author", {}).get("name", ""); org, role = ORG.get(n, ("", ""))
    return (f'<figure class="quote"><div class="rating">★★★★★</div><blockquote>"{esc(r["reviewBody"])}"</blockquote>'
            f'<figcaption><span class="avatar">{esc(n[:1])}</span><span><strong>{esc(n)}</strong><br>'
            f'<span class="org">{esc(org)}</span> <span class="role">· {esc(role)}</span></span></figcaption></figure>')
# proof heading from whichever section is the proof role
_proof_sid = next((sid for sid, r in roles.items() if r == "proof"), None)
_proof_h2_raw = next((s.get("h2", "") for s in outline if s.get("id") == _proof_sid), "") if _proof_sid else ""
# fallback: if the schema carries no Reviews, lift blockquotes from the proof section
if not reviews and _proof_sid:
    for q_ in re.findall(r'>\s*"([^"]+)"', sections.get(_proof_sid, "")):
        reviews.append({"@type": "Review", "reviewBody": q_, "author": {"name": ""}})
proof_html = ""
if reviews:
    proof_h2 = clean_h2(_proof_h2_raw) or "Results teams have already seen"
    proof_html = f'<section class="proof"><div class="wrap"><div class="band-head center"><span class="kicker">Proof</span><h2>{esc(proof_h2)}</h2></div><div class="quotes">{"".join(quote(r) for r in reviews)}</div></div></section>'

faq_html = "".join(f'<details><summary>{esc(f["q"])}</summary><div class="faq-a"><p>{md_inline(f["a"])}</p></div></details>' for f in faq)
faq_sec = f'<section class="faq-band"><div class="wrap"><div class="band-head center"><span class="kicker">FAQ</span><h2>Questions about {esc(inp.get("seed_keyword",""))}</h2></div>{faq_html}</div></section>' if faq else ""

sources = rd.get("external_sources", [])
src_html = ""
if sources:
    items = "".join(f'<li><a href="{_html.escape(s["url"])}" rel="nofollow">{esc(s["name"])}</a></li>' for s in sources)
    src_html = f'<section class="band band-soft"><div class="wrap"><div class="band-head center"><span class="kicker">Sources &amp; further reading</span><h2>What the field says about AI search</h2></div><ul class="sources">{items}</ul></div></section>'

feature_links = (state.get("brand_assets") or {}).get("feature_links") or []
links_html = ""
if feature_links:
    cards = "".join(f'<a class="plink" href="{_html.escape(fl["url"])}">{esc(fl["label"])} <span>→</span></a>' for fl in feature_links[:10])
    links_html = f'<section class="band"><div class="wrap"><div class="band-head center"><span class="kicker">Explore the platform</span><h2>Every capability, in depth</h2></div><div class="plink-grid">{cards}</div></div></section>'

# CTA section — found by role; its h2 may be a brief instruction, so clean it
_cta_sid = next((sid for sid, r in roles.items() if r == "cta"), None)
_cta_h2_raw = next((s.get("h2", "") for s in outline if s.get("id") == _cta_sid), "") if _cta_sid else ""
cta_h2 = clean_h2(_cta_h2_raw) or "Ready to win AI search?"
def _plain(t):   # strip markdown to plain text for single-line slots (CTA)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t or "")
    return t.replace("**", "").replace("*", "").strip()
cta_body = ""
if _cta_sid and sections.get(_cta_sid):
    cta_body = _plain(strip_facts(clean_body(sections[_cta_sid], _cta_h2_raw)).split("\n")[0])
_bad_cta = any(x in cta_body.lower() for x in ("button:", "→", "primary ", "secondary", "]("))
if not cta_body or len(cta_body) < 15 or _bad_cta:
    cta_body = _plain(strip_facts(LEAD))

# author bio + LinkedIn into schema
lnk = author.get("linkedin")
if lnk:
    for b in pkg["schema_jsonld"].get("@graph", []):
        if isinstance(b, dict) and isinstance(b.get("author"), dict):
            b["author"]["sameAs"] = [lnk]
jsonld = strip_facts(json.dumps(pkg["schema_jsonld"], indent=2, ensure_ascii=False))

CSS = (Path("brands/siftly.ai/runs/20260624T135700Z/page.html").read_text())
CSS = CSS[CSS.index("<style>"):CSS.index("</style>") + len("</style>")]
grad = lambda h: re.sub(r"\b(AI|cited|visibility|recommended)\b", r"<span class='grad'>\1</span>", esc(h), count=1)
lnk_html = f' · <a href="{_html.escape(lnk)}">LinkedIn</a>' if lnk else ""

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(TITLE)}</title><meta name="description" content="{esc(META)}">
<link rel="canonical" href="https://siftly.ai{rd.get('target_url','')}">
<script type="application/ld+json">
{jsonld}
</script>{CSS}
<style>.sub{{font-size:18px;margin:24px 0 8px}}.sources{{max-width:760px;margin:0 auto;padding-left:20px;line-height:2}}
.tool-widget-band{{padding:0 0 60px 0;background:linear-gradient(180deg,#ffffff 0%,var(--soft) 100%)}}
.tool-widget-placeholder{{background:#fff;border:2px solid var(--accent);border-radius:18px;padding:32px;box-shadow:0 14px 40px rgba(91,107,255,.10)}}
.twp-label{{display:block;font-weight:600;color:var(--ink);font-size:15px;margin-bottom:10px}}
.twp-row{{display:flex;gap:10px}}
.twp-input{{flex:1;padding:14px 16px;font-size:15px;border:1px solid var(--line);border-radius:10px;outline:none}}
.twp-input:focus{{border-color:var(--accent);box-shadow:0 0 0 3px rgba(91,107,255,.15)}}
.twp-btn{{padding:14px 22px;white-space:nowrap}}
.twp-note{{margin:12px 0 0 0;font-size:13px;color:var(--muted)}}
.ctab{{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden}}
.ctab th{{background:var(--ink);color:#fff;text-align:left;padding:11px 13px;font-size:12.5px}}
.ctab td{{padding:11px 13px;border-top:1px solid var(--line);color:var(--ink2);vertical-align:top}}
.ctab tr:nth-child(even) td{{background:var(--soft2)}}
.plink-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}}
.plink{{display:flex;justify-content:space-between;background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 20px;font-weight:600;color:var(--ink)}}.plink:hover{{border-color:var(--accent);color:var(--accent)}}.plink span{{color:var(--accent)}}
.author-card{{display:flex;gap:18px;align-items:center;background:var(--soft);border:1px solid var(--line);border-radius:14px;padding:24px;max-width:680px;margin:0 auto}}
.author-card .avatar{{width:54px;height:54px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:20px;flex:0 0 54px}}</style>
</head><body>
<nav class="nav"><div class="wrap nav-inner"><div class="brand"><span class="brand-dot"></span>Siftly</div>
<div class="nav-links"><a href="/answers">Product</a><a href="/use-cases">Use cases</a><a href="/guide/generative-engine-optimization">GEO Guide</a><a href="/pricing">Pricing</a></div>
<a class="btn btn-primary" href="/demo">{esc(CTA_LABEL)}</a></div></nav>

<header class="hero"><div class="wrap hero-grid"><div>
<span class="eyebrow">Siftly · Feature</span>
<h1 class="h-display">{grad(H1)}</h1>
<p class="lead">{esc(LEAD)}</p>
<div class="cta-row"><a class="btn btn-primary" href="/demo">{esc(CTA_LABEL)}</a>
<a class="btn btn-ghost" href="/guide/generative-engine-optimization">Read the GEO guide</a></div>
<p style="margin-top:22px;font-size:13px;color:var(--muted)">{esc(BYLINE)}</p></div>
<div class="mock"><div class="mock-bar"><span></span><span></span><span></span></div><div class="mock-body">
<div class="mock-title">AI visibility · across 9 engines</div>
<div class="mock-row"><div><div class="q">ChatGPT</div><div class="meta">cited · rank #2</div></div><div class="rank up">▲ cited</div></div>
<div class="mock-row"><div><div class="q">Perplexity</div><div class="meta">cited · 3 sources</div></div><div class="rank up">▲ cited</div></div>
<div class="mock-row"><div><div class="q">Google AI Overviews</div><div class="meta">opportunity</div></div><div class="rank new">gap</div></div>
</div></div></div></header>

<section class="stats"><div class="wrap stats-grid">
<div class="stat"><div class="num">9</div><div class="lbl">AI engines tracked</div></div>
<div class="stat"><div class="num">#9</div><div class="lbl">Domu, in one month</div></div>
<div class="stat"><div class="num">3.5×</div><div class="lbl">KIWABI ChatGPT revenue</div></div>
<div class="stat"><div class="num">End-to-end</div><div class="lbl">Track → create → measure</div></div></div></section>

{tool_widget_html}
{trends_html}
{body_html}
{links_html}
{proof_html}
{faq_sec}
{src_html}
<section class="band"><div class="wrap"><div class="author-card"><span class="avatar">{esc(author.get('name','?')[:1])}</span>
<div class="meta"><strong>{esc(author.get('byline') or BYLINE)}</strong>{lnk_html}<br>{esc(author.get('bio',''))}</div></div></div></section>

<section class="cta"><div class="wrap"><h2>{esc(cta_h2)}</h2><p>{esc(cta_body)}</p>
<a class="btn btn-primary" href="/demo">{esc(CTA_LABEL)}</a></div></section>

<footer><div class="wrap footer-grid"><div><div class="brand" style="margin-bottom:10px"><span class="brand-dot"></span>Siftly</div>
<p>{esc(BYLINE)}</p></div><div><strong>Explore</strong><div class="footer-links">
<code><a href="/answers">Product</a></code><code><a href="/pricing">Pricing</a></code><code><a href="/guide/generative-engine-optimization">GEO Guide</a></code></div></div></div></footer>
</body></html>"""

(RUN / "page.html").write_text(page)

# clean markdown
md = [f"# {H1}", "", f"*{BYLINE}*", "", strip_facts(LEAD), ""]
for s in outline:
    sid = s.get("id")
    if sid in ("answer_first", "faq") or sid not in sections: continue
    md += [f"## {s.get('h2','')}", "", strip_facts(sections[sid]), ""]
if faq:
    md += ["## Frequently asked questions", ""]
    for f in faq: md += [f"**{strip_facts(f['q'])}**", "", strip_facts(f["a"]), ""]
if sources:
    md += ["## Sources & further reading", ""] + [f"- [{s['name']}]({s['url']})" for s in sources] + [""]
(RUN / "content.md").write_text("\n".join(md))
print("rendered", RUN / "page.html")
