#!/usr/bin/env python3
"""Build the Yvette's Books index.html from a Goodreads library export CSV.

Usage: python3 generate.py [path/to/goodreads_library_export.csv]
Only books on the 'read' shelf WITH a Date Read are included (month/year shown on each card).
Run again any time she sends a fresh export to refresh the grid.
"""
import csv, json, re, sys

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "/home/hatch/workspace/user/files/goodreads_library_export.csv"
OUT_PATH = "/home/hatch/workspace/books-site/index.html"

def clean_isbn(raw):
    if not raw:
        return ""
    s = raw.strip()
    s = re.sub(r'^="?"?', "", s)
    s = re.sub(r'"?$', "", s)
    return s.strip().strip('"')

def month_of(date_read):
    # Goodreads Date Read: YYYY/MM/DD
    m = re.match(r"(\d{4})/(\d{2})/\d{2}", date_read.strip())
    return f"{m.group(1)}-{m.group(2)}" if m else ""

books = []
with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        if row.get("Exclusive Shelf", "").strip() != "read":
            continue
        # Books without a Date Read still go in — they just show no date on the card.
        date = month_of(row.get("Date Read", ""))
        isbn = clean_isbn(row.get("ISBN13", "")) or clean_isbn(row.get("ISBN", ""))
        books.append({
            "title": row.get("Title", "").strip(),
            "author": row.get("Author", "").strip(),
            "isbn": isbn,
            "date": date,
        })

# Dated books first (newest first), then undated by title.
dated = sorted([b for b in books if b["date"]], key=lambda b: (b["date"], b["title"]), reverse=True)
undated = sorted([b for b in books if not b["date"]], key=lambda b: b["title"].lower())
books = dated + undated

# Manual additions (books she names in chat that aren't in the Goodreads export).
try:
    manual = json.load(open("/home/hatch/workspace/books-site/manual-books.json"))
    seen = {(b["title"].lower(), b["author"].lower()) for b in books}
    for m in manual:
        if (m["title"].lower(), m["author"].lower()) not in seen:
            books.append({"title": m["title"], "author": m.get("author", ""),
                          "isbn": m.get("isbn", ""), "date": m.get("date", "")})
    dated = sorted([b for b in books if b["date"]], key=lambda b: (b["date"], b["title"]), reverse=True)
    undated = sorted([b for b in books if not b["date"]], key=lambda b: b["title"].lower())
    books = dated + undated
except (FileNotFoundError, json.JSONDecodeError):
    pass

# Apply resolved cover URLs (from resolve_covers.py); fall back to ISBN URL or placeholder.
covers = {}
try:
    covers = json.load(open("/home/hatch/workspace/books-site/covers.json"))
    for b in books:
        url = covers.get(f"{b['title']}|{b['author']}")
        if url:
            b["cover"] = url
except (FileNotFoundError, json.JSONDecodeError):
    pass

# Currently Reading (pinned section at the top; maintained in currently-reading.json).
currently = []
try:
    cr = json.load(open("/home/hatch/workspace/books-site/currently-reading.json"))
    cr_keys = {(c["title"].lower(), c.get("author", "").lower()) for c in cr}
    books = [b for b in books if (b["title"].lower(), b["author"].lower()) not in cr_keys]
    for c in cr:
        entry = {"title": c["title"], "author": c.get("author", ""), "isbn": c.get("isbn", "")}
        url = covers.get(f"{c['title']}|{c.get('author', '')}")
        if url:
            entry["cover"] = url
        currently.append(entry)
except (FileNotFoundError, json.JSONDecodeError):
    pass

books_data = json.dumps(books, ensure_ascii=False)
currently_data = json.dumps(currently, ensure_ascii=False)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yvette's Books</title>
<meta name="description" content="Every book I've read, one cover at a time.">
<style>
/* Yvette's Books — companion to musings.itryilike.com */
:root{
  --bg:#0b0b0d; --bg2:#121214; --card:#161619; --line:#26262b;
  --ink:#f5f3f1; --muted:#a8a29e; --faint:#6e6a66;
  --accent:#8b6ff5; --accent-soft:rgba(139,111,245,.14);
  --radius:16px;
  --shadow:0 8px 30px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:var(--ink);background:var(--bg);margin:0;line-height:1.6;font-size:16px}
/* nav */
.topbar{position:fixed;top:0;left:0;right:0;z-index:50;
  background:rgba(11,11,13,.72);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.topbar .wrap{display:flex;align-items:center;justify-content:space-between;
  padding:14px 22px;max-width:1160px;margin:0 auto}
.brand{font-weight:800;font-size:1.15rem;letter-spacing:.3px;color:var(--ink);text-decoration:none}
.brand span{color:var(--accent)}
.navlink{font-size:.9rem;color:var(--muted);text-decoration:none;border:1px solid var(--line);
  padding:.45rem 1.1rem;border-radius:999px;transition:.2s}
.navlink:hover{border-color:var(--accent);color:var(--ink)}
/* hero */
.hero{position:relative;text-align:center;padding:150px 22px 70px;overflow:hidden}
.hero::before{content:"";position:absolute;inset:0;
  background:radial-gradient(600px 320px at 50% 20%,rgba(139,111,245,.22),transparent 70%),
             radial-gradient(500px 300px at 80% 80%,rgba(139,111,245,.08),transparent 70%);
  pointer-events:none}
.hero h1{position:relative;font-size:clamp(2.6rem,7vw,4.5rem);margin:0 0 .6rem;
  letter-spacing:-1.5px;font-weight:800;line-height:1.05}
.hero h1 .dot{color:var(--accent)}
.hero .sub{position:relative;font-size:1.2rem;color:var(--muted);margin:0}
.hero .count{position:relative;font-size:.95rem;color:var(--faint);margin:.8rem 0 0}
/* layout */
.wrap{max-width:1160px;margin:0 auto;padding:0 22px}
.section-title{font-size:.85rem;text-transform:uppercase;letter-spacing:2px;
  color:var(--faint);margin:3rem 0 1.2rem;font-weight:700;text-align:center}
/* book grid */
.bookgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:26px 20px}
.searchrow{margin:0 0 26px}
.searchrow input{width:100%;max-width:420px;padding:12px 16px;font-size:15px;color:var(--text);
  background:#16161a;border:1px solid #2a2a31;border-radius:999px;outline:none}
.searchrow input::placeholder{color:#6d6d78}
.searchrow input:focus{border-color:var(--accent)}
.noresults{display:none;color:var(--muted);padding:30px 0;text-align:center}
.book{text-decoration:none;color:var(--ink);display:block}
.book .cover{position:relative;aspect-ratio:2/3;border-radius:10px;overflow:hidden;
  background:var(--card);border:1px solid var(--line);box-shadow:var(--shadow);
  transition:transform .2s}
.book:hover .cover{transform:translateY(-4px)}
.book .cover img{width:100%;height:100%;object-fit:cover;display:block}
.book .cover.placeholder{display:flex;align-items:center;justify-content:center;
  text-align:center;padding:12px;
  background:linear-gradient(135deg,#1c1a26,#2a2440 60%,#221d35)}
.book .cover.placeholder .pt{font-size:.8rem;font-weight:700;color:#cfc6ef;line-height:1.35;
  display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical;overflow:hidden}
.book .btitle{font-size:.92rem;font-weight:700;margin:.7rem 0 .1rem;line-height:1.35;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.book .bdate{font-size:.8rem;color:var(--faint)}
/* empty state */
.empty{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:48px 32px;text-align:center;box-shadow:var(--shadow)}
.empty p{color:var(--muted);margin:.4rem 0}
/* footer */
footer.site{border-top:1px solid var(--line);margin-top:4rem;padding:30px 22px;text-align:center;
  color:var(--faint);font-size:.9rem}
footer.site a{color:var(--accent);text-decoration:none}
footer.site a:hover{text-decoration:underline}
@media (max-width:640px){
  .hero{padding:120px 20px 60px}
  .bookgrid{grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:20px 14px}
}
</style>
</head>
<body>
<header class="topbar"><div class="wrap">
  <a class="brand" href="/">Yvette&rsquo;s <span>Books</span></a>
  <a class="navlink" href="https://musings.itryilike.com">Musings &rarr;</a>
</div></header>

<div class="hero">
  <h1>Yvette&rsquo;s Books<span class="dot">.</span></h1>
  <p class="sub">My reading journey.</p>
</div>

<div class="wrap" id="currentwrap">
  <div class="section-title">Currently Reading</div>
  <div class="bookgrid" id="currentgrid"></div>
</div>

<div class="wrap">
  <div class="section-title">Read</div>
  <div class="searchrow"><input type="search" id="q" placeholder="Search by title or author&hellip;" autocomplete="off" aria-label="Search books"></div>
  <div class="bookgrid" id="bookgrid"></div>
  <div class="noresults" id="noresults">No books match your search.</div>
  <div class="empty" id="emptystate" style="display:none">
    <p><strong>Coming soon.</strong></p>
    <p>My Goodreads books will appear here once they&rsquo;re imported.</p>
  </div>
</div>

<footer class="site">
  <p>Yvette&rsquo;s Books &middot; part of <a href="https://musings.itryilike.com">Yvette&rsquo;s Musings</a></p>
</footer>

<script>
/* Books log: newest first. Each entry: title, author, isbn (for cover), date (YYYY-MM). */
var BOOKS = __BOOKS__;
var CURRENTLY = __CURRENTLY__;
var SAMPLES = false;

function fmtDate(d){
  var months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  var p=d.split("-");
  return months[parseInt(p[1],10)-1]+" "+p[0];
}
function esc(s){
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
/* Currently Reading: pinned grid above the main log. */
var cgrid=document.getElementById("currentgrid");
if(CURRENTLY.length){
  var chtml="";
  for(var j=0;j<CURRENTLY.length;j++){
    var c=CURRENTLY[j], ccover;
    if(c.cover){
      ccover='<div class="cover"><img src="'+esc(c.cover)+'" alt="'+esc(c.title)+'" loading="lazy" onerror="coverFallback(this)"></div>';
    }else if(c.isbn){
      ccover='<div class="cover"><img src="https://covers.openlibrary.org/b/isbn/'+encodeURIComponent(c.isbn)+'-M.jpg" alt="'+esc(c.title)+'" loading="lazy" onerror="coverFallback(this)"></div>';
    }else{
      ccover='<div class="cover placeholder"><span class="pt">'+esc(c.title)+'</span></div>';
    }
    chtml+='<div class="book" data-title="'+esc(c.title)+'">'+ccover+
      '<div class="btitle">'+esc(c.title)+'</div></div>';
  }
  cgrid.innerHTML=chtml;
}else{
  document.getElementById("currentwrap").style.display="none";
}
var grid=document.getElementById("bookgrid");
var empty=document.getElementById("emptystate");
if(!BOOKS.length){
  empty.style.display="block";
}else{
  var html="";
  for(var i=0;i<BOOKS.length;i++){
    var b=BOOKS[i];
    var cover;
    if(b.cover){
      cover='<div class="cover"><img src="'+esc(b.cover)+'" alt="'+esc(b.title)+'" loading="lazy" onerror="coverFallback(this)"></div>';
    }else if(b.isbn){
      cover='<div class="cover"><img src="https://covers.openlibrary.org/b/isbn/'+encodeURIComponent(b.isbn)+'-M.jpg" alt="'+esc(b.title)+'" loading="lazy" onerror="coverFallback(this)"></div>';
    }else{
      cover='<div class="cover placeholder"><span class="pt">'+esc(b.title)+'</span></div>';
    }
    html+='<div class="book" data-search="'+esc((b.title+" "+b.author).toLowerCase())+'" data-title="'+esc(b.title)+'">'+cover+
      '<div class="btitle">'+esc(b.title)+'</div>'+
      (b.date?'<div class="bdate">'+fmtDate(b.date)+'</div>':'')+'</div>';
  }
  grid.innerHTML=html;
  /* Live search filter */
  var q=document.getElementById("q"), nores=document.getElementById("noresults"),
      cards=grid.querySelectorAll(".book");
  q.addEventListener("input",function(){
    var term=q.value.trim().toLowerCase(), shown=0;
    for(var i=0;i<cards.length;i++){
      var hit=!term||cards[i].getAttribute("data-search").indexOf(term)>-1;
      cards[i].style.display=hit?"":"none";
      if(hit)shown++;
    }
    nores.style.display=shown?"none":"block";
  });
}
/* When a cover image fails to load, swap in a styled placeholder with the title. */
function coverFallback(img){
  var title=(img.closest(".book")||{}).dataset?img.closest(".book").dataset.title:"";
  var d=document.createElement("div");
  d.className="cover placeholder";
  d.innerHTML='<span class="pt">'+esc(title)+'</span>';
  img.parentNode.replaceChild(d,img);
}
</script>
</body>
</html>
"""

html = PAGE.replace("__BOOKS__", books_data).replace("__CURRENTLY__", currently_data)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Wrote {OUT_PATH} with {len(books)} books")
