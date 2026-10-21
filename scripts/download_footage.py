
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path("downloads")
OUT.mkdir(parents=True, exist_ok=True)
UA = "HindiTechShorts/1.0 (personal video project)"
MAX_BYTES = 100 * 1024 * 1024
MAX_CLIPS = 4
ALLOWED = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/ogg": ".ogv",
    "video/quicktime": ".mov",
}


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def search(term):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": "filetype:video " + term,
        "gsrnamespace": 6,
        "gsrlimit": 20,
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "format": "json",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    data = get_json(url)
    return list(data.get("query", {}).get("pages", {}).values())


def download(page):
    info_list = page.get("imageinfo", [])
    if not info_list:
        return False

    info = info_list[0]
    mime = info.get("mime", "")
    url = info.get("url", "")

    if mime not in ALLOWED or not url:
        print("Skipping unsupported format:", page.get("title"), mime)
        return False

    title = page.get("title", "clip")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", title)[:70]
    dest = OUT / (safe + ALLOWED[mime])

    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            total = 0
            with dest.open("wb") as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError("File exceeds 100 MB limit")
                    f.write(chunk)

        if total < 10_000:
            raise ValueError("File too small to be a useful video")

        meta = info.get("extmetadata", {})
        record = {
            "file": dest.name,
            "title": title,
            "source": "https://commons.wikimedia.org/wiki/"
                      + urllib.parse.quote(title.replace(" ", "_")),
            "license": meta.get("LicenseShortName", {}).get("value", "Check source"),
            "artist": meta.get("Artist", {}).get("value", "Check source"),
        }
        with (OUT / "sources.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print("Downloaded:", dest.name, total, "bytes")
        return True

    except Exception as e:
        dest.unlink(missing_ok=True)
        print("Download error:", title, str(e))
        return False


def main():
    terms = [
        "smartphone",
        "mobile phone",
        "computer technology",
        "electronics",
    ]
    seen = set()
    count = 0

    for term in terms:
        print("\nSearching Commons for:", term)
        try:
            pages = search(term)
            print("Search results:", len(pages))
        except Exception as e:
            print("Search error:", str(e))
            continue

        for page in pages:
            title = page.get("title", "")
            if title in seen:
                continue
            seen.add(title)

            if download(page):
                count += 1
                if count >= MAX_CLIPS:
                    break
            time.sleep(1)

        if count >= MAX_CLIPS:
            break

    print("\nUsable clips downloaded:", count)
    if count == 0:
        raise SystemExit(
            "No supported video files found. Review the search and download logs."
        )


if __name__ == "__main__":
    main()
