#!/usr/bin/env python3
"""Render the /use-cases/saas package into a production HTML page + clean MD.

Reads the pipeline's package_out.json + state.json (the source of truth),
strips internal (fact:id) provenance refs for display, lightly de-AI-smells a
few residual major-level tells (mechanical phrase swaps only — no new facts),
and lays the grounded copy into the production Siftly template.
"""
import json
import re
import html as _html
from pathlib import Path

RUN = Path("brands/siftly.ai/runs/20260625T125505Z")
state = json.loads((RUN / "state.json").read_text())
pkg = json.loads((RUN / "package_out.json").read_text())
inp = json.loads(Path("brands/siftly.ai/inputs/use-cases-saas.json").read_text())

# brand_assets in state.json is frozen at pipeline time — reload the live file
# so author credentials / screenshots / feature links added after the run apply.
state["brand_assets"] = json.loads(Path("brands/siftly.ai/brand_assets.json").read_text())

rd = inp["research_dossier"]
H1 = rd["suggested_h1"]
LEAD = rd["quotable_intro"]
TITLE = pkg["title_variants"][0] + " | Siftly"
META = pkg["meta"]
BYLINE = pkg["byline_line"]
TRENDS = rd["trend_signals"]
CTA_LABEL = rd["primary_cta"]
sections = state["sections"]
outline = state["outline"]["sections"]
faq = state["faq"]

# ---- cleaners -------------------------------------------------------------
FACT_RE = re.compile(r"\s*\(fact:[a-z0-9\-]+\)", re.I)
TELL_SWAPS = [
    (r"AI is fundamentally reshaping how buyers find solutions\.",
     "Buyers now find solutions a different way."),
    (r"\bThe shift is fundamental:\s*c", "C"),
    (r"\bThe shift is fundamental:\s*", ""),
    (r"\bThe stakes are real and urgent\.\s*", ""),
    (r"before the competitive landscape hardens and your future presence is defined by algorithms you never measured or optimized for",
     "before competitors lock in the citations you can still win"),
    (r"\bsilently capturing\b", "capturing"),
    # --- audit polish: AI-tell phrase + repeated "This" openers + vague comparative ---
    (r"\btransform them into\b", "turn them into"),
    (r"\bThis happens on a regular schedule\b", "It runs on a regular schedule"),
    (r"\bThis content is purpose-built\b", "Each piece is purpose-built"),
    (r"\bThis three-step cycle repeats\b", "The cycle repeats"),
    (r"\bThis comprehensive coverage lets you\b", "That coverage shows you"),
    (r"\bThis real buyer behavior data reveals\b", "Real buyer-behavior data reveals"),
    (r"\bThis approach delivers regular\b", "The cadence delivers regular"),
    (r"\bThis comprehensive measurement proves\b", "End-to-end measurement proves"),
    (r"\bThis targeted optimization ensures\b", "That tuning helps ensure"),
    (r"different from other AI visibility tools",
     "different from tracking-only AI visibility tools"),
]

def strip_facts(t: str) -> str:
    return FACT_RE.sub("", t)

def apply_swaps(t: str) -> str:
    """Fact-strip + AI-tell phrase swaps, preserving whitespace (for JSON blobs)."""
    t = strip_facts(t)
    for pat, rep in TELL_SWAPS:
        t = re.sub(pat, rep, t)
    return t

def clean(t: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", apply_swaps(t)).strip()

def esc(t: str) -> str:
    return _html.escape(t, quote=False)

def md_inline(t: str) -> str:
    t = esc(t)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

def blocks(body: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", clean(body)) if b.strip()]

def section_html(body: str) -> str:
    out = []
    for b in blocks(body):
        m = re.fullmatch(r"\*\*(.+?)\*\*", b)
        if m:
            out.append(f'<h3 class="sub">{md_inline(m.group(1).strip())}</h3>')
        else:
            out.append(f"<p>{md_inline(b)}</p>")
    return "\n".join(out)

def build_steps(body: str) -> str:
    """how_it_works: pair each '**n. Title**' subhead with the paragraph after it."""
    bl = blocks(body)
    pairs = []
    i = 0
    while i < len(bl):
        m = re.fullmatch(r"\*\*(.+?)\*\*", bl[i])
        if m and i + 1 < len(bl):
            title = re.sub(r"^\d+\.\s*", "", m.group(1).strip())
            pairs.append((title, bl[i + 1]))
            i += 2
        else:
            i += 1
    icons = ["🔍", "✍️", "📈", "🎯"]
    cards = []
    for n, (title, desc) in enumerate(pairs, 1):
        cards.append(
            f'<div class="step"><div class="step-num">{n}</div>'
            f'<div class="step-ico">{icons[(n-1) % len(icons)]}</div>'
            f'<h3>{md_inline(title)}</h3><p>{md_inline(desc)}</p></div>')
    return "\n".join(cards)

def build_feats(body: str) -> str:
    """capabilities: each block is '**Title.** description' on one line."""
    icons = ["📡", "🔗", "✍️", "💬", "📣", "🛒", "📊"]
    cards = []
    n = 0
    for b in blocks(body):
        m = re.match(r"\*\*(.+?)\*\*\s*(.*)", b, re.S)
        if not m:
            continue
        title = m.group(1).strip().rstrip(".")
        desc = m.group(2).strip()
        ico = icons[n % len(icons)]
        n += 1
        cards.append(
            f'<div class="feat"><div class="feat-ico">{ico}</div>'
            f'<h3>{md_inline(title)}</h3><p>{md_inline(desc)}</p></div>')
    return "\n".join(cards)

# ---- testimonials from JSON-LD Reviews (permissioned source) --------------
reviews = [b for b in pkg["schema_jsonld"]["@graph"] if b.get("@type") == "Review"]
ORG = {"Manuel": ("Domu", "GTM"), "Emi": ("KIWABI", "Founder"),
       "Niigawa Kyouhei": ("BROMO", "CEO")}
def quote_card(r):
    name = r.get("author", {}).get("name", "")
    org, role = ORG.get(name, ("", ""))
    initial = (name or "?")[0]
    return f"""<figure class="quote">
  <div class="rating">★★★★★</div>
  <blockquote>"{esc(r['reviewBody'])}"</blockquote>
  <figcaption><span class="avatar">{esc(initial)}</span>
    <span><strong>{esc(name)}</strong><br><span class="org">{esc(org)}</span> <span class="role">· {esc(role)}</span></span>
  </figcaption>
</figure>"""

quotes_html = "\n".join(quote_card(r) for r in reviews)
trends_html = "\n".join(
    f'<div class="trend"><span class="trend-icon">↗</span><p>{esc(strip_facts(t))}</p></div>'
    for t in TRENDS)
faq_html = "\n".join(
    f"""<details><summary>{esc(clean(f['q']))}</summary>
  <div class="faq-a"><p>{md_inline(clean(f['a']))}</p></div></details>"""
    for f in faq)

steps_html = build_steps(sections["how_it_works"])
feats_html = build_feats(sections["capabilities"])
diff_html = section_html(sections["differentiators"])
problem_html = section_html(sections["problem"])
cta_line = clean(sections["cta"]).split("\n")[0]

# --- author bio block (E-E-A-T): grounded in brand_assets, no invented claims ---
author = (state.get("brand_assets") or {}).get("author") or {}
author_bio = author.get("bio", "")
author_name = author.get("name", "")

# --- product screenshot (dummy placeholder), inlined so the page is self-contained ---
shots = (state.get("brand_assets") or {}).get("screenshots") or []
product_fig = ""
if shots:
    shot = shots[0]
    svg_path = RUN / shot["src"]
    if svg_path.exists():
        svg = svg_path.read_text()
        note = " (placeholder mockup — swap with a real screenshot before publishing)" if shot.get("placeholder") else ""
        product_fig = f"""
<section class="band"><div class="wrap">
  <div class="band-head center"><span class="kicker">See it in action</span>
    <h2>One dashboard for your AI search visibility</h2></div>
  <figure class="shot">{svg}
    <figcaption>{esc(shot.get('caption') or shot.get('alt',''))}{note}</figcaption></figure>
</div></section>"""

# --- explore the platform: owner-supplied feature URLs as internal links ---
feature_links = (state.get("brand_assets") or {}).get("feature_links") or []
links_html = ""
if feature_links:
    cards = "\n".join(
        f'<a class="plink" href="{esc(fl["url"])}">{esc(fl["label"])} <span>→</span></a>'
        for fl in feature_links)
    links_html = f"""
<section class="band"><div class="wrap">
  <div class="band-head center"><span class="kicker">Explore the platform</span>
    <h2>Every capability, in depth</h2>
    <p class="band-sub">Dig into the individual features behind Siftly's end-to-end GEO platform.</p></div>
  <div class="plink-grid">{cards}</div>
</div></section>"""

# --- section lookup by id (outline order may shift as sections are added) ---
_by_id = {s["id"]: s for s in outline}
def H2(sid, default=""):
    return _by_id.get(sid, {}).get("h2", default)

# --- market context (real Semrush data + authoritative citations) ----------
market_html = ""
if sections.get("market_context"):
    market_html = f"""
<section class="band"><div class="wrap">
  <div class="band-head"><span class="kicker">Why now</span>
    <h2>{esc(H2('market_context', 'Why AI search is a measurable channel now'))}</h2></div>
  {section_html(sections['market_context'])}
</div></section>"""

# --- sources & further reading: real external authoritative domains --------
sources = state.get("sources") or []
sources_html = ""
if sources:
    items = "\n".join(
        f'<li><a href="{esc(s["url"])}" rel="nofollow">{esc(s["name"])}</a></li>'
        for s in sources)
    sources_html = f"""
<section class="band band-soft"><div class="wrap">
  <div class="band-head"><span class="kicker">Sources &amp; further reading</span>
    <h2>What the field says about AI search</h2></div>
  <ul class="sources">{items}</ul>
</div></section>"""

# inject the author's LinkedIn (sameAs) into the schema — added after the run
_lnk = (state.get("brand_assets") or {}).get("author", {}).get("linkedin")
if _lnk:
    for _b in pkg["schema_jsonld"].get("@graph", []):
        if isinstance(_b, dict) and isinstance(_b.get("author"), dict):
            _b["author"]["sameAs"] = [_lnk]
jsonld = apply_swaps(json.dumps(pkg["schema_jsonld"], indent=2, ensure_ascii=False))
CSS = (RUN.parent / "20260624T135700Z" / "page.html").read_text()
CSS = CSS[CSS.index("<style>"):CSS.index("</style>") + len("</style>")]
H1_HTML = md_inline(H1).replace("get cited", "<span class='grad'>get cited</span>")

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(TITLE)}</title>
<meta name="description" content="{esc(META)}">
<link rel="canonical" href="https://siftly.ai/use-cases/saas">
<script type="application/ld+json">
{jsonld}
</script>
{CSS}
<style>.sub{{font-size:18px;margin:26px 0 8px;letter-spacing:-.01em}}
.shot{{margin:0;border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:0 24px 60px rgba(11,16,32,.12);background:#fff}}
.shot svg{{display:block;width:100%;height:auto}}
.shot figcaption{{padding:14px 20px;font-size:13px;color:var(--muted);border-top:1px solid var(--line);background:var(--soft2)}}
.plink-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}}
.plink{{display:flex;justify-content:space-between;align-items:center;background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 22px;font-weight:600;color:var(--ink);transition:all .15s}}
.plink:hover{{border-color:var(--accent);color:var(--accent);transform:translateY(-2px);box-shadow:0 10px 26px rgba(91,84,246,.12)}}
.plink span{{color:var(--accent);font-weight:700}}
.author-card{{display:flex;gap:18px;align-items:center;background:var(--soft);border:1px solid var(--line);border-radius:14px;padding:24px 28px;max-width:680px;margin:0 auto}}
.author-card .avatar{{width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:22px;flex:0 0 56px}}
.author-card .meta{{font-size:14px;color:var(--muted)}}.author-card .meta strong{{color:var(--ink);font-size:15px}}
.sources{{max-width:760px;margin:0;padding-left:20px;line-height:2}}.sources li{{color:var(--ink2)}}.sources a{{font-weight:600}}</style>
</head><body>
<nav class="nav"><div class="wrap nav-inner">
  <div class="brand"><span class="brand-dot"></span>Siftly</div>
  <div class="nav-links"><a href="/features/ai-prompt-analytics">Product</a><a href="/use-cases/saas">Use cases</a><a href="/guide/generative-engine-optimization">GEO Guide</a><a href="/pricing">Pricing</a></div>
  <a class="btn btn-primary" href="/demo">{esc(CTA_LABEL)}</a>
</div></nav>

<header class="hero"><div class="wrap hero-grid">
  <div>
    <span class="eyebrow">For B2B SaaS</span>
    <h1 class="h-display">{H1_HTML}</h1>
    <p class="lead">{esc(LEAD)}</p>
    <div class="cta-row">
      <a class="btn btn-primary" href="/demo">{esc(CTA_LABEL)}</a>
      <a class="btn btn-ghost" href="/guide/generative-engine-optimization">Read the GEO guide</a>
    </div>
    <p style="margin-top:22px;font-size:13px;color:var(--muted)">{esc(BYLINE)}</p>
  </div>
  <div class="mock"><div class="mock-bar"><span></span><span></span><span></span></div>
    <div class="mock-body"><div class="mock-title">AI shortlist · "best tool for [your category]"</div>
      <div class="mock-row"><div><div class="q">ChatGPT</div><div class="meta">cited · rank #2</div></div><div class="rank up">▲ cited</div></div>
      <div class="mock-row"><div><div class="q">Perplexity</div><div class="meta">cited · 3 sources</div></div><div class="rank up">▲ cited</div></div>
      <div class="mock-row"><div><div class="q">Google AI Overviews</div><div class="meta">not cited yet</div></div><div class="rank new">opportunity</div></div>
      <div class="mock-row"><div><div class="q">Gemini</div><div class="meta">competitor cited</div></div><div class="rank">gap</div></div>
    </div></div>
</div></header>

<section class="stats"><div class="wrap stats-grid">
  <div class="stat"><div class="num">9</div><div class="lbl">AI engines tracked</div></div>
  <div class="stat"><div class="num">#9</div><div class="lbl">Domu, in one month</div></div>
  <div class="stat"><div class="num">3.5×</div><div class="lbl">KIWABI ChatGPT revenue</div></div>
  <div class="stat"><div class="num">End-to-end</div><div class="lbl">Track → create → measure</div></div>
</div></section>

<section class="trend-band"><div class="wrap">
  <div class="band-head"><span class="kicker">Why now</span>
    <h2>The SaaS buying journey moved into AI</h2></div>
  <div class="trend-grid">{trends_html}</div>
</div></section>

<section class="band"><div class="wrap">
  <div class="band-head"><span class="kicker">The problem</span>
    <h2>{esc(H2('problem'))}</h2></div>
  <div class="problem"><div class="problem-text">{problem_html}</div>
    <div class="problem-visual">
      <div class="gap-row"><span class="l">Ranks #1 on Google</span><span class="r ok">✓</span></div>
      <div class="gap-row"><span class="l">Cited by ChatGPT</span><span class="r">✗ invisible</span></div>
      <div class="gap-row"><span class="l">On the Perplexity shortlist</span><span class="r">✗ competitor wins</span></div>
      <div class="gap-row"><span class="l">In Google AI Overviews</span><span class="r">✗ not measured</span></div>
    </div>
  </div>
</div></section>
{market_html}
<section class="band band-soft"><div class="wrap">
  <div class="band-head"><span class="kicker">How it works</span>
    <h2>{esc(H2('how_it_works'))}</h2></div>
  <div class="steps">{steps_html}</div>
</div></section>
{product_fig}
<section class="band band-soft"><div class="wrap">
  <div class="band-head"><span class="kicker">Capabilities</span>
    <h2>{esc(H2('capabilities'))}</h2></div>
  <div class="feat-grid">{feats_html}</div>
</div></section>
{links_html}

<section class="band band-soft"><div class="wrap">
  <div class="band-head"><span class="kicker">Why Siftly</span>
    <h2>{esc(H2('differentiators'))}</h2></div>
  {diff_html}
</div></section>

<section class="proof"><div class="wrap">
  <div class="band-head center"><span class="kicker">Proof</span>
    <h2>Results SaaS teams have already seen</h2></div>
  <div class="quotes">{quotes_html}</div>
</div></section>

<section class="faq-band"><div class="wrap">
  <div class="band-head center"><span class="kicker">FAQ</span>
    <h2>Questions about AI search visibility</h2></div>
  {faq_html}
</div></section>
{sources_html}
<section class="band"><div class="wrap">
  <div class="author-card">
    <span class="avatar">{esc(author_name[:1])}</span>
    <div class="meta"><strong>{esc(author.get('byline') or BYLINE)}</strong>{(' · <a href="' + esc(author.get('linkedin')) + '">LinkedIn</a>') if author.get('linkedin') else ''}<br>{esc(author_bio)}</div>
  </div>
</div></section>

<section class="cta"><div class="wrap">
  <h2>{esc(H2('cta'))}</h2>
  <p>{esc(cta_line)}</p>
  <a class="btn btn-primary" href="/demo">{esc(CTA_LABEL)}</a>
</div></section>

<footer><div class="wrap footer-grid">
  <div><div class="brand" style="margin-bottom:10px"><span class="brand-dot"></span>Siftly</div>
    <p>{esc(BYLINE)}</p></div>
  <div><strong>Explore</strong>
    <div class="footer-links"><code><a href="/features/ai-prompt-analytics">AI Prompt Analytics</a></code><code><a href="/pricing">Pricing</a></code><code><a href="/guide/generative-engine-optimization">GEO Guide</a></code></div>
  </div>
</div></footer>
</body></html>"""

(RUN / "page.html").write_text(page)
print("wrote", RUN / "page.html", len(page), "bytes")

# ---- clean markdown (display copy, fact-refs stripped) ---------------------
md = [f"# {H1}", "", f"*{BYLINE}*", "", LEAD, ""]
labels = {"problem": "The problem", "how_it_works": "How it works",
          "capabilities": "Capabilities", "differentiators": "Why Siftly",
          "proof": "Proof", "cta": "Get started"}
for sec in outline:
    sid = sec["id"]
    if sid in ("answer_first", "faq"):
        continue
    md.append(f"## {sec['h2']}")
    md.append("")
    md.append(clean(sections.get(sid, "")))
    md.append("")
md.append("## Frequently asked questions")
md.append("")
for f in faq:
    md.append(f"**{clean(f['q'])}**")
    md.append("")
    md.append(clean(f["a"]))
    md.append("")
if feature_links:
    md.append("## Explore the platform")
    md.append("")
    for fl in feature_links:
        md.append(f"- [{fl['label']}]({fl['url']})")
    md.append("")
md.append("---")
md.append("### About the author")
md.append(f"{author.get('byline') or BYLINE}. {author_bio}")
md.append("")
md.append("### Proof")
for r in reviews:
    name = r.get("author", {}).get("name", "")
    org = ORG.get(name, ("", ""))[0]
    md.append(f"> {r['reviewBody']}")
    md.append(f"> — {name}, {org}")
    md.append("")
(RUN / "content.md").write_text("\n".join(md))
print("wrote", RUN / "content.md")
