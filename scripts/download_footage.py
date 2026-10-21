
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUTPUT_DIR = Path("downloads")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SEARCH_TERMS = [
    "smartphone technology video",
    "mobile phone charging video",
    "computer technology video",
]

USER_AGENT = "HindiTechShortsBot/1.0 (educational video project)"
MAX_DOWNLOADS = 4
MAX_BYTES = 100 * 1024 * 1024


def request_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def search_videos(term):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": (
            "filetype:video " + term
            + " filemime:video/mp4"
        ),
        "gsrnamespace": 6,
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": 640,
        "format": "json",
    }

    url = (
        "https://commons.wikimedia.org/w/api.php?"
        + urllib.parse.urlencode(params)
    )
    data = request_json(url)
    pages = data.get("query", {}).get("pages", {})
    return list(pages.values())


def download_video(page):
    info_list = page.get("imageinfo", [])
    if not info_list:
        return False

    info = info_list[0]
    mime = info.get("mime", "")
    source_url = info.get("url", "")

    # Only download direct MP4 video files.
    if mime != "video/mp4" or not source_url:
        return False

    title = page.get("title", "video")
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", title)
    destination = OUTPUT_DIR / (safe_name[:80] + ".mp4")

    if destination.exists():
        return True

    req = urllib.request.Request(
        source_url, headers={"User-Agent": USER_AGENT}
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            content_type = response.headers.get("Content-Type", "")
            length = response.headers.get("Content-Length")

            if length and int(length) > MAX_BYTES:
                print("Skipping oversized file:", title)
                return False

            if "video" not in content_type.lower() and "octet-stream" not in content_type.lower():
                print("Skipping non-video response:", title)
                return False

            total = 0
            with destination.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        output.close()
                        destination.unlink(missing_ok=True)
                        print("Skipped file over size limit:", title)
                        return False
                    output.write(chunk)

        if total < 10_000:
            destination.unlink(missing_ok=True)
            return False

        metadata = info.get("extmetadata", {})
        record = {
            "filename": destination.name,
            "source_page": "https://commons.wikimedia.org/wiki/"
                           + urllib.parse.quote(title.replace(" ", "_")),
            "license": metadata.get("LicenseShortName", {}).get("value", "Check source page"),
            "artist": metadata.get("Artist", {}).get("value", "Check source page"),
            "title": title,
        }

        with (OUTPUT_DIR / "sources.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print("Downloaded:", destination.name)
        return True

    except Exception as exc:
        destination.unlink(missing_ok=True)
        print("Download failed:", title, str(exc))
        return False


def main():
    count = 0
    seen = set()

    for term in SEARCH_TERMS:
        print("Searching Wikimedia Commons:", term)

        try:
            pages = search_videos(term)
        except Exception as exc:
            print("Search failed:", str(exc))
            continue

        for page in pages:
            title = page.get("title", "")
            if title in seen:
                continue
            seen.add(title)

            if download_video(page):
                count += 1
                if count >= MAX_DOWNLOADS:
                    break

            time.sleep(1)

        if count >= MAX_DOWNLOADS:
            break

    print("Usable clips downloaded:", count)

    if count == 0:
        raise SystemExit(
            "No suitable MP4 clips found. Check the search results or "
            "try alternative footage sources."
        )


if __name__ == "__main__":
    main()
