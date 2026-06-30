from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ingest.reference_indexes import normalize_key, write_reference_indexes  # noqa: E402


ATLAS_ROOT_URL = "https://colleges.shkolamoskva.ru/atlas"
FAQ_URL = "https://school.mos.ru/mcrpo/portal/admission/"
DEFAULT_DATA_DIR = Path("data")
DEFAULT_SNAPSHOT_PATH = DEFAULT_DATA_DIR / "atlas_snapshot.json"
REQUEST_TIMEOUT = (8, 25)

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0",
}

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
LINK_RE = re.compile(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>", re.IGNORECASE | re.DOTALL)
ATTR_RE = re.compile(r"(?P<name>[a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?P<quote>[\"'])(?P<value>.*?)\2", re.DOTALL)
HEADING_RE = re.compile(r"<h(?P<level>[1-6])\b[^>]*>(?P<body>.*?)</h(?P=level)>", re.IGNORECASE | re.DOTALL)

ATLAS_NETLOC = urlsplit(ATLAS_ROOT_URL).netloc
IGNORED_H1 = {
    normalize_key("Колледжи Москвы"),
    normalize_key("Мастерство начинается здесь"),
}
ADDRESS_MARKERS = (
    "адрес",
    "улица",
    "ул.",
    "проспект",
    "проезд",
    "переулок",
    "шоссе",
    "бульвар",
    "набережная",
    "площадь",
    "дом ",
    "д.",
    "корпус",
    "м.",
    "цао",
    "сзао",
    "сао",
    "свао",
    "вао",
    "ювао",
    "юао",
    "юзао",
    "зао",
)


@dataclass(frozen=True)
class Link:
    href: str
    text: str
    raw_href: str


def clean_text(text: str) -> str:
    text = unescape(str(text)).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n-–—")


def clean_multiline(text: str) -> str:
    text = unescape(str(text)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def html_to_text(fragment: str, *, multiline: bool = False) -> str:
    fragment = SCRIPT_STYLE_RE.sub(" ", fragment)
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"(?i)</(p|div|li|tr|td|th|h[1-6])>", "\n", fragment)
    text = TAG_RE.sub(" ", fragment)
    return clean_multiline(text) if multiline else clean_text(text)


def parse_attrs(attrs: str) -> dict[str, str]:
    return {match.group("name").lower(): unescape(match.group("value")) for match in ATTR_RE.finditer(attrs)}


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def absolute_url(href: str, base_url: str) -> str:
    href = unescape(str(href)).strip()
    return canonical_url(urljoin(base_url, href))


def extract_links(html: str, base_url: str) -> list[Link]:
    links: list[Link] = []
    for match in LINK_RE.finditer(html):
        attrs = parse_attrs(match.group("attrs"))
        href = attrs.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "tel:", "mailto:")):
            normalized = href
        else:
            normalized = absolute_url(href, base_url)
        text = html_to_text(match.group("body"))
        if href or text:
            links.append(Link(normalized, text, href))
    return links


def is_atlas_url(url: str) -> bool:
    return urlsplit(url).netloc == ATLAS_NETLOC


def atlas_path(url: str) -> str:
    return urlsplit(url).path.rstrip("/")


def is_cluster_url(url: str) -> bool:
    return is_atlas_url(url) and bool(re.fullmatch(r"/atlas/cluster/[^/]+", atlas_path(url)))


def is_college_url(url: str) -> bool:
    return is_atlas_url(url) and bool(re.fullmatch(r"/atlas/college/[^/]+", atlas_path(url)))


def is_specialty_url(url: str) -> bool:
    if not is_atlas_url(url):
        return False
    path = atlas_path(url)
    if path in {"", "/atlas", "/atlas/fullmap"}:
        return False
    if path.startswith(("/atlas/cluster/", "/atlas/college/", "/atlas/page/")):
        return False
    return bool(re.fullmatch(r"/atlas/[^/]+", path))


def slug_from_url(url: str) -> str:
    return atlas_path(url).rsplit("/", 1)[-1]


def unique_items(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = clean_text(value)
        key = normalize_key(value)
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def extract_headings(html: str, level: int | None = None) -> list[str]:
    headings: list[str] = []
    for match in HEADING_RE.finditer(html):
        if level is not None and int(match.group("level")) != level:
            continue
        text = html_to_text(match.group("body"))
        if text:
            headings.append(text)
    return headings


def extract_page_title(html: str) -> str:
    for heading in extract_headings(html, 1):
        if normalize_key(heading) not in IGNORED_H1:
            return heading

    match = re.search(r"<meta\b[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)", html, re.IGNORECASE)
    if not match:
        match = re.search(r"<title\b[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""

    title = html_to_text(match.group(1))
    title = re.split(r"\s+[-—]\s+Атлас", title, maxsplit=1)[0]
    return clean_text(title)


def extract_section(html: str, heading_markers: tuple[str, ...]) -> str:
    headings = list(HEADING_RE.finditer(html))
    normalized_markers = tuple(normalize_key(marker) for marker in heading_markers)
    for index, match in enumerate(headings):
        heading = normalize_key(html_to_text(match.group("body")))
        if not any(marker in heading for marker in normalized_markers):
            continue
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(html)
        return html[start:end]
    return ""


def extract_cluster_links(html: str, base_url: str) -> list[dict[str, str]]:
    clusters: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in extract_links(html, base_url):
        if not is_cluster_url(link.href) or link.href in seen:
            continue
        seen.add(link.href)
        clusters.append(
            {
                "key": slug_from_url(link.href),
                "title": link.text or slug_from_url(link.href),
                "url": link.href,
            }
        )
    return clusters


def extract_specialty_links(html: str, base_url: str) -> list[dict[str, str]]:
    specialties: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in extract_links(html, base_url):
        if not is_specialty_url(link.href) or link.href in seen:
            continue
        seen.add(link.href)
        specialties.append(
            {
                "name": link.text or slug_from_url(link.href),
                "url": link.href,
                "slug": slug_from_url(link.href),
            }
        )
    return specialties


def extract_college_links(html: str, base_url: str) -> list[dict[str, str]]:
    colleges: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in extract_links(html, base_url):
        if not is_college_url(link.href) or link.href in seen:
            continue
        seen.add(link.href)
        colleges.append(
            {
                "name": link.text or slug_from_url(link.href),
                "atlas_url": link.href,
                "slug": slug_from_url(link.href),
            }
        )
    return colleges


def extract_profession_examples(html: str) -> list[str]:
    professions: list[str] = []
    pattern = re.compile(
        r"<(?:div|span|p)\b[^>]*class=[\"'][^\"']*examples-name[^\"']*[\"'][^>]*>(.*?)</(?:div|span|p)>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        professions.append(html_to_text(match.group(1)))
    return unique_items(professions)


def profession_hints_from_title(title: str) -> list[str]:
    hints: list[str] = []
    for value in re.findall(r"\(([^)]+)\)", title):
        for part in re.split(r"[,;/]", value):
            part = clean_text(part)
            if 2 <= len(part) <= 80:
                hints.append(part)
    return unique_items(hints)


def parse_specialty_page(html: str, url: str, *, cluster: dict[str, str] | None = None) -> dict[str, Any]:
    title = extract_page_title(html)
    professions = unique_items(extract_profession_examples(html) + profession_hints_from_title(title))
    colleges = extract_college_links(html, url)
    cluster = cluster or {}

    return {
        "name": title or slug_from_url(url),
        "slug": slug_from_url(url),
        "atlas_url": canonical_url(url),
        "cluster_key": cluster.get("key", ""),
        "cluster_title": cluster.get("title", ""),
        "professions": professions,
        "colleges": colleges,
    }


def looks_like_address(text: str) -> bool:
    normalized = normalize_key(text)
    if len(normalized) < 8:
        return False
    return any(marker in normalized for marker in ADDRESS_MARKERS) or bool(re.search(r"\bд\.?\s*\d", normalized))


def extract_addresses(html: str, base_url: str) -> list[str]:
    addresses: list[str] = []
    for link in extract_links(html, base_url):
        parsed = urlsplit(urljoin(base_url, link.raw_href))
        query = parse_qs(parsed.query)
        if "from_college" in query and looks_like_address(link.text):
            addresses.append(link.text)

    section = extract_section(html, ("Адреса учебных корпусов", "Адреса"))
    if section:
        for line in html_to_text(section, multiline=True).splitlines():
            if looks_like_address(line):
                addresses.append(line)

    return unique_items(addresses)


def contact_from_href(href: str, text: str) -> str:
    if href.startswith("tel:"):
        return clean_text(text or href.removeprefix("tel:"))
    if href.startswith("mailto:"):
        return clean_text(text or href.removeprefix("mailto:"))
    return clean_text(text or href)


def extract_contacts(html: str, base_url: str) -> list[str]:
    contacts: list[str] = []
    section = extract_section(html, ("Контакты",)) or html
    for link in extract_links(section, base_url):
        raw = unescape(link.raw_href).strip()
        if raw.startswith(("tel:", "mailto:")):
            contacts.append(contact_from_href(raw, link.text))
            continue
        if raw.startswith(("https://t.me/", "http://t.me/", "https://vk.com/", "http://vk.com/")):
            contacts.append(absolute_url(raw, base_url))
    return unique_items(contacts)


def extract_website(html: str, base_url: str) -> str:
    section = extract_section(html, ("Контакты",)) or html
    for link in extract_links(section, base_url):
        raw = unescape(link.raw_href).strip()
        href = link.href
        if not raw.startswith(("http://", "https://", "//")):
            continue
        if not href or urlsplit(href).netloc in {ATLAS_NETLOC, "t.me", "vk.com"}:
            continue
        if any(part in href for part in ("/wp-content/", "api-maps.yandex", "yastatic.net", "cdn.jsdelivr.net")):
            continue
        return href
    return ""


def parse_college_page(html: str, url: str) -> dict[str, Any]:
    directions = []
    for link in extract_links(html, url):
        if not is_specialty_url(link.href):
            continue
        if "?" in link.raw_href or looks_like_address(link.text):
            continue
        directions.append(
            {
                "name": link.text or slug_from_url(link.href),
                "atlas_url": link.href,
                "professions": [],
            }
        )

    return {
        "name": extract_page_title(html) or slug_from_url(url),
        "aliases": [],
        "atlas_url": canonical_url(url),
        "website": extract_website(html, url),
        "addresses": extract_addresses(html, url),
        "contacts": extract_contacts(html, url),
        "specialties": dedupe_specialties(directions),
    }


def faq_from_json_ld(html: str, source_url: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for match in re.finditer(
        r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        raw = html_to_text(match.group(1))
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            entities = item.get("mainEntity") if isinstance(item, dict) else None
            if not isinstance(entities, list):
                continue
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                question = clean_text(entity.get("name", ""))
                answer = entity.get("acceptedAnswer", {})
                answer_text = clean_text(answer.get("text", "") if isinstance(answer, dict) else "")
                if question and answer_text:
                    docs.append(build_faq_doc(question, answer_text, source_url))
    return docs


def faq_from_details(html: str, source_url: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for match in re.finditer(r"<details\b[^>]*>(.*?)</details>", html, re.IGNORECASE | re.DOTALL):
        block = match.group(1)
        summary = re.search(r"<summary\b[^>]*>(.*?)</summary>", block, re.IGNORECASE | re.DOTALL)
        if not summary:
            continue
        question = html_to_text(summary.group(1))
        answer_html = block[: summary.start()] + block[summary.end() :]
        answer = html_to_text(answer_html)
        if question and answer:
            docs.append(build_faq_doc(question, answer, source_url))
    return docs


def faq_from_blocks(html: str, source_url: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    pattern = re.compile(
        r"<(?P<tag>div|section|article)\b[^>]*class=[\"'][^\"']*faq[^\"']*[\"'][^>]*>(?P<body>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        body = match.group("body")
        question_match = re.search(
            r"<(?:h[2-5]|button|summary)\b[^>]*>(.*?)</(?:h[2-5]|button|summary)>",
            body,
            re.IGNORECASE | re.DOTALL,
        )
        if not question_match:
            continue
        question = html_to_text(question_match.group(1))
        answer = html_to_text(body[: question_match.start()] + body[question_match.end() :])
        if question and answer and normalize_key(question) != normalize_key(answer):
            docs.append(build_faq_doc(question, answer, source_url))
    return docs


def build_faq_doc(question: str, answer: str, source_url: str) -> dict[str, Any]:
    return {
        "id": "",
        "doc_type": "faq",
        "title": question,
        "content": answer,
        "metadata_json": {
            "section": "Поступление",
            "category": "admission",
            "tags": ["поступление", "faq", "mos.ru"],
            "applies_to": {
                "college_names": [],
                "domain_tags": [],
                "specialty_names": [],
            },
            "source_type": "school_mos_admission",
            "source_url": source_url,
            "priority": 1,
        },
    }


def parse_faq_page(html: str, source_url: str = FAQ_URL) -> list[dict[str, Any]]:
    docs = faq_from_json_ld(html, source_url) or faq_from_details(html, source_url) or faq_from_blocks(html, source_url)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in docs:
        key = normalize_key(doc["title"])
        if not key or key in seen:
            continue
        seen.add(key)
        doc = copy.deepcopy(doc)
        doc["id"] = f"faq_school_mos_{len(result) + 1:03d}"
        result.append(doc)
    return result


def dedupe_specialties(specialties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for specialty in specialties:
        name = clean_text(specialty.get("name", ""))
        key = normalize_key(name)
        if not name or key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "name": name,
                "professions": unique_items([str(value) for value in specialty.get("professions", [])]),
                "atlas_url": clean_text(specialty.get("atlas_url", "")),
            }
        )
    return result


def merge_lists(existing: list[str], incoming: list[str]) -> list[str]:
    return unique_items([str(value) for value in existing] + [str(value) for value in incoming])


def merge_specialty(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    target["professions"] = merge_lists(target.get("professions", []), incoming.get("professions", []))
    incoming_url = clean_text(incoming.get("atlas_url", ""))
    if incoming_url:
        target["atlas_url"] = incoming_url


def merge_specialties(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [copy.deepcopy(item) for item in existing]
    lookup = {normalize_key(str(item.get("name", ""))): item for item in result}
    for item in incoming:
        name = clean_text(item.get("name", ""))
        key = normalize_key(name)
        if not name:
            continue
        if key in lookup:
            merge_specialty(lookup[key], item)
            continue
        new_item = {
            "name": name,
            "professions": unique_items([str(value) for value in item.get("professions", [])]),
        }
        atlas_url = clean_text(item.get("atlas_url", ""))
        if atlas_url:
            new_item["atlas_url"] = atlas_url
        result.append(new_item)
        lookup[key] = new_item
    return result


def college_lookup_keys(college: dict[str, Any]) -> set[str]:
    keys = {normalize_key(str(college.get("name", "")))}
    keys.update(normalize_key(str(alias)) for alias in college.get("aliases", []))
    return {key for key in keys if key}


def merge_college(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    if incoming.get("atlas_url"):
        target["atlas_url"] = incoming["atlas_url"]
    if incoming.get("website") and not target.get("website"):
        target["website"] = incoming["website"]
    target["aliases"] = merge_lists(target.get("aliases", []), incoming.get("aliases", []))
    target["addresses"] = merge_lists(target.get("addresses", []), incoming.get("addresses", []))
    target["contacts"] = merge_lists(target.get("contacts", []), incoming.get("contacts", []))
    target["specialties"] = merge_specialties(target.get("specialties", []), incoming.get("specialties", []))


def merge_colleges(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    result = [copy.deepcopy(item) for item in existing]
    lookup: dict[str, dict[str, Any]] = {}
    for college in result:
        for key in college_lookup_keys(college):
            lookup[key] = college

    stats = {"added_colleges": 0, "updated_colleges": 0}
    for college in incoming:
        key = normalize_key(str(college.get("name", "")))
        target = lookup.get(key)
        if target is None:
            new_college = {
                "name": clean_text(college.get("name", "")),
                "aliases": unique_items([str(value) for value in college.get("aliases", [])]),
                "specialties": merge_specialties([], college.get("specialties", [])),
                "addresses": unique_items([str(value) for value in college.get("addresses", [])]),
                "contacts": unique_items([str(value) for value in college.get("contacts", [])]),
                "website": clean_text(college.get("website", "")),
            }
            if college.get("atlas_url"):
                new_college["atlas_url"] = college["atlas_url"]
            result.append(new_college)
            for lookup_key in college_lookup_keys(new_college):
                lookup[lookup_key] = new_college
            stats["added_colleges"] += 1
            continue

        merge_college(target, college)
        for lookup_key in college_lookup_keys(target):
            lookup[lookup_key] = target
        stats["updated_colleges"] += 1

    return result, stats


def merge_faq_documents(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    result = [copy.deepcopy(item) for item in existing]
    lookup = {
        normalize_key(str(item.get("title", ""))): item
        for item in result
        if (item.get("metadata_json") or {}).get("source_type") == "school_mos_admission"
    }
    all_titles = {normalize_key(str(item.get("title", ""))) for item in result}
    used_ids = {str(item.get("id", "")) for item in result}
    stats = {"added_faq": 0, "updated_faq": 0, "skipped_existing_faq": 0}

    for doc in incoming:
        key = normalize_key(str(doc.get("title", "")))
        if not key:
            continue
        if key in lookup:
            target = lookup[key]
            target["content"] = doc.get("content", target.get("content", ""))
            target["metadata_json"] = {**target.get("metadata_json", {}), **doc.get("metadata_json", {})}
            stats["updated_faq"] += 1
            continue
        if key in all_titles:
            stats["skipped_existing_faq"] += 1
            continue

        new_doc = copy.deepcopy(doc)
        base_id = str(new_doc.get("id") or f"faq_school_mos_{stats['added_faq'] + 1:03d}")
        unique_id = base_id
        suffix = 2
        while unique_id in used_ids:
            unique_id = f"{base_id}_{suffix}"
            suffix += 1
        new_doc["id"] = unique_id
        used_ids.add(unique_id)
        all_titles.add(key)
        result.append(new_doc)
        stats["added_faq"] += 1

    return result, stats


def build_colleges_from_snapshot(specialties: list[dict[str, Any]], college_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}

    def ensure_college(name: str, atlas_url: str = "") -> dict[str, Any]:
        key_url = canonical_url(atlas_url) if atlas_url else ""
        key_name = normalize_key(name)
        college = by_url.get(key_url) if key_url else None
        college = college or by_name.get(key_name)
        if college is None:
            college = {
                "name": clean_text(name),
                "aliases": [],
                "specialties": [],
                "addresses": [],
                "contacts": [],
                "website": "",
            }
            if key_url:
                college["atlas_url"] = key_url
                by_url[key_url] = college
            if key_name:
                by_name[key_name] = college
        return college

    for page in college_pages:
        college = ensure_college(page.get("name", ""), page.get("atlas_url", ""))
        merge_college(college, page)

    for specialty in specialties:
        specialty_entry = {
            "name": specialty.get("name", ""),
            "professions": specialty.get("professions", []),
            "atlas_url": specialty.get("atlas_url", ""),
        }
        for college_ref in specialty.get("colleges", []):
            college = ensure_college(college_ref.get("name", ""), college_ref.get("atlas_url", ""))
            college["specialties"] = merge_specialties(college.get("specialties", []), [specialty_entry])

    return sorted(by_name.values(), key=lambda item: normalize_key(str(item.get("name", ""))))


def fetch_text(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def crawl_atlas(
    session: requests.Session,
    *,
    root_url: str,
    include_college_pages: bool,
    specialty_limit: int | None = None,
    cluster_limit: int | None = None,
) -> dict[str, Any]:
    root_html = fetch_text(session, root_url)
    clusters = extract_cluster_links(root_html, root_url)
    if cluster_limit:
        clusters = clusters[:cluster_limit]

    specialty_refs: dict[str, dict[str, str]] = {}
    for cluster_index, cluster in enumerate(clusters, start=1):
        print(f"Cluster {cluster_index}/{len(clusters)}: {cluster['title']}")
        cluster_html = fetch_text(session, cluster["url"])
        parsed_title = extract_page_title(cluster_html)
        if parsed_title:
            cluster["title"] = parsed_title
        for specialty in extract_specialty_links(cluster_html, cluster["url"]):
            specialty_refs.setdefault(specialty["url"], {**specialty, "cluster_key": cluster["key"], "cluster_title": cluster["title"]})

    refs = list(specialty_refs.values())
    if specialty_limit:
        refs = refs[:specialty_limit]

    specialties: list[dict[str, Any]] = []
    for index, ref in enumerate(refs, start=1):
        print(f"Specialty {index}/{len(refs)}: {ref.get('name')}")
        html = fetch_text(session, ref["url"])
        specialty = parse_specialty_page(
            html,
            ref["url"],
            cluster={"key": ref.get("cluster_key", ""), "title": ref.get("cluster_title", "")},
        )
        specialties.append(specialty)

    college_pages: list[dict[str, Any]] = []
    if include_college_pages:
        college_refs: dict[str, dict[str, str]] = {}
        for specialty in specialties:
            for college in specialty.get("colleges", []):
                college_refs.setdefault(college["atlas_url"], college)
        college_items = list(college_refs.values())
        for index, ref in enumerate(college_items, start=1):
            print(f"College {index}/{len(college_items)}: {ref.get('name')}")
            try:
                html = fetch_text(session, ref["atlas_url"])
            except requests.RequestException as exc:
                print(f"Skipped college page {ref.get('atlas_url')}: {exc}")
                college_pages.append(
                    {
                        "name": ref.get("name", ""),
                        "aliases": [],
                        "atlas_url": ref.get("atlas_url", ""),
                        "website": "",
                        "addresses": [],
                        "contacts": [],
                        "specialties": [],
                    }
                )
                continue
            college_pages.append(parse_college_page(html, ref["atlas_url"]))

    colleges = build_colleges_from_snapshot(specialties, college_pages)
    return {
        "source": root_url,
        "fetched_at": datetime.now(UTC).isoformat(),
        "clusters": clusters,
        "specialties": specialties,
        "colleges": colleges,
    }


def fetch_faq(session: requests.Session, faq_url: str) -> list[dict[str, Any]]:
    try:
        html = fetch_text(session, faq_url)
    except requests.RequestException as exc:
        print(f"Skipped FAQ page {faq_url}: {exc}")
        return []
    return parse_faq_page(html, faq_url)


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_snapshot(snapshot: dict[str, Any], data_dir: Path) -> dict[str, int]:
    colleges_path = data_dir / "colleges.json"
    faq_path = data_dir / "faq_admission.json"

    current_colleges = read_json(colleges_path, [])
    if not isinstance(current_colleges, list):
        raise ValueError("colleges.json must contain a list")
    merged_colleges, college_stats = merge_colleges(current_colleges, snapshot.get("colleges", []))
    write_json(colleges_path, merged_colleges)
    write_reference_indexes(merged_colleges, data_dir)

    faq_stats = {"added_faq": 0, "updated_faq": 0, "skipped_existing_faq": 0}
    if snapshot.get("faq"):
        current_faq = read_json(faq_path, [])
        if not isinstance(current_faq, list):
            raise ValueError("faq_admission.json must contain a list")
        merged_faq, faq_stats = merge_faq_documents(current_faq, snapshot.get("faq", []))
        write_json(faq_path, merged_faq)

    return {**college_stats, **faq_stats}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Moscow colleges Atlas data and optionally merge it into data/*.json.")
    parser.add_argument("--atlas-url", default=ATLAS_ROOT_URL)
    parser.add_argument("--faq-url", default=FAQ_URL)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--apply", action="store_true", help="Merge fetched data into colleges.json, faq_admission.json and reference indexes.")
    parser.add_argument("--skip-faq", action="store_true", help="Do not fetch the admission FAQ page.")
    parser.add_argument("--skip-college-pages", action="store_true", help="Use college names from specialty pages without fetching college cards.")
    parser.add_argument("--specialty-limit", type=int, default=None, help="Limit specialty pages for debugging.")
    parser.add_argument("--cluster-limit", type=int, default=None, help="Limit cluster pages for debugging.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    session = requests.Session()
    session.headers.update(HEADERS)

    snapshot = crawl_atlas(
        session,
        root_url=args.atlas_url,
        include_college_pages=not args.skip_college_pages,
        specialty_limit=args.specialty_limit,
        cluster_limit=args.cluster_limit,
    )
    snapshot["faq"] = [] if args.skip_faq else fetch_faq(session, args.faq_url)
    write_json(args.snapshot, snapshot)

    print(
        "Fetched: "
        f"{len(snapshot.get('clusters', []))} clusters, "
        f"{len(snapshot.get('specialties', []))} specialties, "
        f"{len(snapshot.get('colleges', []))} colleges, "
        f"{len(snapshot.get('faq', []))} FAQ docs."
    )
    print(f"Snapshot: {args.snapshot}")

    if args.apply:
        stats = apply_snapshot(snapshot, args.data_dir)
        print(f"Applied: {stats}")
    else:
        print("Dry run only. Add --apply to update data/colleges.json and data/faq_admission.json.")


if __name__ == "__main__":
    main()
