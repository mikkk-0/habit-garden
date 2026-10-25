"""Build the bundled emoji picker data from Unicode Emoji 18.0 and CLDR 49.

Run this only when intentionally refreshing the catalog. The application itself
uses the checked-in JSON file and never contacts these URLs at runtime.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


EMOJI_URL = "https://www.unicode.org/Public/emoji/latest/emoji-test.txt"
RU_URL = "https://raw.githubusercontent.com/unicode-org/cldr/release-49/common/annotations/ru.xml"
EXPECTED_EMOJI_VERSION = "18.0"
OUTPUT = Path(__file__).resolve().parents[1] / "src/habit_garden/static/emoji-catalog.json"


def download(url: str) -> str:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read().decode("utf-8")
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def normalize(value: str) -> str:
    return value.replace("\ufe0f", "").replace("\ufe0e", "")


def parse_russian_annotations(xml: str) -> tuple[dict[str, str], dict[str, str]]:
    names, keywords = {}, {}
    for annotation in ET.fromstring(xml).iter("annotation"):
        emoji = normalize(annotation.attrib.get("cp", ""))
        value = (annotation.text or "").strip()
        if not emoji or not value:
            continue
        if annotation.attrib.get("type") == "tts":
            names[emoji] = value
        else:
            keywords[emoji] = value.replace(" | ", " ")
    return names, keywords


def build(emoji_data: str, ru_data: str) -> dict:
    if f"# Version: {EXPECTED_EMOJI_VERSION}" not in emoji_data:
        raise ValueError("Unicode Emoji version changed; review the catalog before updating")
    ru_names, ru_keywords = parse_russian_annotations(ru_data)
    group = ""
    items = []
    seen = set()
    for line in emoji_data.splitlines():
        if line.startswith("# group: "):
            group = line.removeprefix("# group: ")
            continue
        if "; fully-qualified" not in line or "#" not in line:
            continue
        codepoints, comment = line.split(";", 1)[0], line.split("#", 1)[1].strip()
        numbers = [int(point, 16) for point in codepoints.split()]
        # A compact, useful label picker needs base emoji, not every skin-tone variant.
        if any(0x1F3FB <= point <= 0x1F3FF for point in numbers):
            continue
        emoji = "".join(chr(point) for point in numbers)
        if emoji in seen:
            continue
        seen.add(emoji)
        english_name = re.sub(r"^\S+\s+E[\d.]+\s+", "", comment)
        key = normalize(emoji)
        items.append([emoji, ru_names.get(key, english_name), ru_keywords.get(key, ""), group])
    if len(items) < 1000 or "🌱" not in seen:
        raise ValueError("Emoji source is incomplete")
    return {
        "emojiVersion": EXPECTED_EMOJI_VERSION,
        "cldrVersion": "49",
        "sources": [EMOJI_URL, RU_URL],
        "items": items,
    }


if __name__ == "__main__":
    catalog = build(download(EMOJI_URL), download(RU_URL))
    OUTPUT.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(catalog['items'])} emoji to {OUTPUT}")
