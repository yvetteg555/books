#!/usr/bin/env python3
"""Resolve the best Open Library cover URL for every book in the Goodreads CSV.

For each book (title, author, isbn):
  1. Try the ISBN cover URL; accept it if the image isn't OL's "blank" placeholder.
  2. Else query the OL search API (title + author), try up to 3 candidate cover IDs.
Results are cached in covers.json (keyed by title|author) so reruns are cheap.
"""
import csv, hashlib, json, os, re, time, urllib.parse, urllib.request

CSV_PATH = "/home/hatch/workspace/user/files/goodreads_library_export.csv"
CACHE_PATH = "/home/hatch/workspace/books-site/covers.json"
BLANK_MD5 = "e250704785e66162a3a4f08129502dc5"  # OL's 180x245 "no cover" image

def clean_isbn(raw):
    if not raw:
        return ""
    s = raw.strip()
    s = re.sub(r'^="?"?', "", s)
    s = re.sub(r'"?$', "", s)
    return s.strip().strip('"')

def month_of(date_read):
    m = re.match(r"(\d{4})/(\d{2})/\d{2}", (date_read or "").strip())
    return f"{m.group(1)}-{m.group(2)}" if m else ""

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "YvettesBooks/1.0 (personal reading log)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def image_ok(url):
    try:
        data = fetch(url)
    except Exception:
        return False
    if not data or len(data) < 500:
        return False
    return hashlib.md5(data).hexdigest() != BLANK_MD5

def search_covers(title, author, limit=3):
    q = {"title": title, "limit": limit, "fields": "key,title,author_name,cover_i"}
    if author:
        q["author"] = author
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(q)
    try:
        data = json.loads(fetch(url))
    except Exception:
        return []
    out = []
    for doc in data.get("docs", []):
        ci = doc.get("cover_i")
        if ci:
            out.append(f"https://covers.openlibrary.org/b/id/{ci}-M.jpg")
    return out

def google_books_cover(title, author):
    """Fallback: Google Books API thumbnail (https, larger zoom)."""
    q = f"intitle:{title}" + (f"+inauthor:{author}" if author else "")
    url = ("https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode({
        "q": q, "maxResults": 3,
        "fields": "items(volumeInfo(title,authors,imageLinks))",
    }))
    try:
        data = json.loads(fetch(url))
    except Exception:
        return None
    for item in data.get("items", []):
        vi = item.get("volumeInfo", {})
        links = vi.get("imageLinks", {})
        thumb = links.get("thumbnail") or links.get("smallThumbnail")
        if thumb:
            thumb = thumb.replace("http://", "https://").replace("&zoom=1", "&zoom=0").replace("zoom=1", "zoom=0")
            if image_ok(thumb):
                return thumb
    return None

def load_books():
    books = []
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("Exclusive Shelf", "").strip() != "read":
                continue
            books.append({
                "title": row.get("Title", "").strip(),
                "author": row.get("Author", "").strip(),
                "isbn": clean_isbn(row.get("ISBN13", "")) or clean_isbn(row.get("ISBN", "")),
                "date": month_of(row.get("Date Read", "")),
            })
    # Manual additions (same file generate.py uses).
    try:
        manual = json.load(open("/home/hatch/workspace/books-site/manual-books.json"))
        seen = {(b["title"].lower(), b["author"].lower()) for b in books}
        for m in manual:
            if (m["title"].lower(), m["author"].lower()) not in seen:
                books.append({"title": m["title"], "author": m.get("author", ""),
                              "isbn": m.get("isbn", ""), "date": m.get("date", "")})
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    # Currently Reading additions (same covers cache; generate.py pins them on top).
    try:
        cr = json.load(open("/home/hatch/workspace/books-site/currently-reading.json"))
        seen = {(b["title"].lower(), b["author"].lower()) for b in books}
        for c in cr:
            if (c["title"].lower(), c.get("author", "").lower()) not in seen:
                books.append({"title": c["title"], "author": c.get("author", ""),
                              "isbn": c.get("isbn", ""), "date": ""})
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return books

def main():
    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH))
    books = load_books()
    new = 0
    for i, b in enumerate(books):
        key = f"{b['title']}|{b['author']}"
        if cache.get(key):
            continue
        cover = None
        if b["isbn"]:
            url = f"https://covers.openlibrary.org/b/isbn/{urllib.parse.quote(b['isbn'])}-M.jpg"
            if image_ok(url):
                cover = url
        if not cover:
            for url in search_covers(b["title"], b["author"]):
                if image_ok(url):
                    cover = url
                    break
        if not cover:
            cover = google_books_cover(b["title"], b["author"])
        cache[key] = cover
        new += 1
        if new % 10 == 0:
            json.dump(cache, open(CACHE_PATH, "w"), ensure_ascii=False, indent=1)
            print(f"  resolved {i+1}/{len(books)} ({new} new this run)", flush=True)
        time.sleep(0.4)  # be polite to the OL API
    json.dump(cache, open(CACHE_PATH, "w"), ensure_ascii=False, indent=1)
    found = sum(1 for v in cache.values() if v)
    print(f"Done. {found}/{len(cache)} books have a cover URL.")

if __name__ == "__main__":
    main()
