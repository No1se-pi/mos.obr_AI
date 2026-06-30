from __future__ import annotations

import argparse
import base64
import json
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests


DEFAULT_ROOT_URL = (
    "https://app.weeek.net/s/"
    "masterstvo-nachinaetsya-zdes-document-"
    "NzA4NTAzfDlkYThiY2Q2LTMwMDctNDAxZi1hODllLTM3YjAyMjc1YTRmNQ=="
)
DEFAULT_OUTPUT = Path("data/weeek_knowledge.json")
API_URL = "https://api.weeek.net/shared/articles/{token}"
MAX_CHUNK_CHARS = 1800
MIN_CHUNK_CHARS = 300

SHARED_DOCUMENT_RE = re.compile(r"/s/[^?#\s\"']*?document-(?P<token>[A-Za-z0-9+/=_-]+)")


@dataclass(frozen=True)
class SharedLink:
    token: str
    text: str
    href: str


def extract_token(value: str) -> str:
    value = unquote(str(value)).strip()
    match = re.search(r"document-(?P<token>[A-Za-z0-9+/=_-]+)", value)
    if match:
        return match.group("token")
    return value


def decode_token(token: str) -> tuple[str | None, str | None]:
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:
        return None, None

    if "|" not in decoded:
        return None, decoded
    workspace_id, article_id = decoded.split("|", 1)
    return workspace_id or None, article_id or None


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_shared_document_href(href: str) -> bool:
    return bool(SHARED_DOCUMENT_RE.search(unquote(str(href))))


def text_node_to_text(node: dict[str, Any]) -> str:
    text = str(node.get("text") or "")
    if not text:
        return ""

    for mark in node.get("marks") or []:
        attrs = mark.get("attrs") if isinstance(mark, dict) else {}
        href = str((attrs or {}).get("href") or "")
        if href and not is_shared_document_href(href):
            return f"{text} ({href})"
    return text


def inline_text(node: Any) -> str:
    if isinstance(node, list):
        return clean_text("".join(inline_text(item) for item in node))
    if not isinstance(node, dict):
        return ""

    node_type = node.get("type")
    if node_type == "text":
        return text_node_to_text(node)
    if node_type == "hardBreak":
        return "\n"

    content = node.get("content") or []
    if node_type in {"paragraph", "heading"}:
        return clean_text("".join(inline_text(item) for item in content))
    return clean_text(" ".join(filter(None, (inline_text(item) for item in content))))


def table_rows(node: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for row in node.get("content") or []:
        if not isinstance(row, dict):
            continue
        cells = [inline_text(cell) for cell in row.get("content") or []]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(" | ".join(cells))
    return rows


def block_lines(node: dict[str, Any], *, indent: int = 0) -> list[str]:
    node_type = node.get("type")
    prefix = "  " * indent

    if node_type == "heading":
        text = inline_text(node)
        level = int((node.get("attrs") or {}).get("level") or 2)
        return [f"{'#' * max(1, min(level, 4))} {text}"] if text else []

    if node_type == "paragraph":
        text = inline_text(node)
        return [text] if text else []

    if node_type == "bulletList":
        lines: list[str] = []
        for item in node.get("content") or []:
            item_text = clean_text("\n".join(block_lines(item, indent=indent + 1)))
            if item_text:
                first, *rest = item_text.splitlines()
                lines.append(f"{prefix}- {first}")
                lines.extend(f"{prefix}  {line}" for line in rest)
        return lines

    if node_type == "orderedList":
        lines = []
        start = int((node.get("attrs") or {}).get("start") or 1)
        for offset, item in enumerate(node.get("content") or [], start=start):
            item_text = clean_text("\n".join(block_lines(item, indent=indent + 1)))
            if item_text:
                first, *rest = item_text.splitlines()
                lines.append(f"{prefix}{offset}. {first}")
                lines.extend(f"{prefix}   {line}" for line in rest)
        return lines

    if node_type == "listItem":
        lines = []
        for child in node.get("content") or []:
            if isinstance(child, dict):
                lines.extend(block_lines(child, indent=indent))
        return lines

    if node_type == "blockquote":
        return [f"> {line}" for child in node.get("content") or [] for line in block_lines(child, indent=indent)]

    if node_type == "table":
        return table_rows(node)

    text = inline_text(node)
    if text:
        return [text]

    lines = []
    for child in node.get("content") or []:
        if isinstance(child, dict):
            lines.extend(block_lines(child, indent=indent))
    return lines


def top_level_blocks(article_data: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for node in article_data.get("content") or []:
        if not isinstance(node, dict):
            continue
        text = clean_text("\n".join(block_lines(node)))
        if text:
            blocks.append(
                {
                    "type": node.get("type") or "unknown",
                    "level": int((node.get("attrs") or {}).get("level") or 0),
                    "text": text,
                }
            )
    return blocks


def split_long_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    parts: list[str] = []
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        separator_len = 2 if current else 0
        if current and current_len + separator_len + len(paragraph) > max_chars:
            parts.append("\n\n".join(current).strip())
            current = []
            current_len = 0

        if len(paragraph) > max_chars:
            remaining = paragraph
            while len(remaining) > max_chars:
                cut = remaining.rfind(" ", 0, max_chars)
                if cut < max_chars // 2:
                    cut = max_chars
                parts.append(remaining[:cut].strip())
                remaining = remaining[cut:].strip()
            if remaining:
                current = [remaining]
                current_len = len(remaining)
            continue

        current.append(paragraph)
        current_len += separator_len + len(paragraph)

    if current:
        parts.append("\n\n".join(current).strip())

    return [part for part in parts if part]


def chunk_article(article_name: str, article_data: dict[str, Any]) -> list[dict[str, str]]:
    blocks = top_level_blocks(article_data)
    chunks: list[dict[str, str]] = []
    current_heading = article_name
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        text = clean_text("\n\n".join(current))
        current = []
        if not text:
            return
        for part in split_long_text(text):
            chunks.append({"heading": current_heading, "content": part})

    for block in blocks:
        block_text = block["text"]
        is_heading = block["type"] == "heading"

        if is_heading and current and len(clean_text("\n\n".join(current))) >= MIN_CHUNK_CHARS:
            flush()

        if is_heading:
            heading_text = re.sub(r"^#{1,4}\s+", "", block_text).strip()
            current_heading = heading_text or article_name

        current.append(block_text)
        if len(clean_text("\n\n".join(current))) > MAX_CHUNK_CHARS:
            flush()

    flush()

    if not chunks:
        text = clean_text("\n\n".join(block["text"] for block in blocks))
        chunks = [{"heading": article_name, "content": part} for part in split_long_text(text)]

    return chunks


def walk(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def shared_links(article_data: dict[str, Any]) -> list[SharedLink]:
    links: list[SharedLink] = []
    for node in walk(article_data):
        if not isinstance(node, dict) or node.get("type") != "text":
            continue
        text = clean_text(str(node.get("text") or ""))
        for mark in node.get("marks") or []:
            attrs = mark.get("attrs") if isinstance(mark, dict) else {}
            href = str((attrs or {}).get("href") or "")
            match = SHARED_DOCUMENT_RE.search(unquote(href))
            if match:
                links.append(SharedLink(token=match.group("token"), text=text, href=href))
    return links


def tags_for_text(*texts: str) -> list[str]:
    text = clean_text(" ".join(texts)).lower().replace("ё", "е")
    tags = {"weeek", "поступление"}
    rules = {
        "заявление": ("заяв", "mos.ru", "мос.ру"),
        "документы": ("документ", "паспорт", "аттестат", "снилс"),
        "сроки": ("срок", "дата", "июн", "июл", "август"),
        "льготы": ("льгот", "сво", "инвалид", "овз", "преимуществен", "первоочеред"),
        "иностранцы": ("иностран", "граждан"),
        "бюджет": ("бюджет", "конкурс", "приоритет", "зачислен"),
        "9 класс": ("9 класс", "9-й класс"),
        "11 класс": ("11 класс", "11-й класс"),
        "профориентация": ("профориентац", "отрасл", "професс"),
        "колледжи": ("колледж", "матрица"),
    }
    for tag, markers in rules.items():
        if any(marker in text for marker in markers):
            tags.add(tag)
    return sorted(tags)


def category_for_text(*texts: str) -> str:
    tags = set(tags_for_text(*texts))
    if "профориентация" in tags:
        return "career_guidance"
    if "льготы" in tags:
        return "admission_benefits"
    if "иностранцы" in tags:
        return "admission_foreigners"
    if "сроки" in tags:
        return "admission_deadlines"
    if "документы" in tags:
        return "admission_documents"
    if "заявление" in tags:
        return "admission_application"
    if "бюджет" in tags:
        return "admission_budget"
    return "weeek_knowledge"


def source_url_for_token(token: str) -> str:
    return f"https://app.weeek.net/s/document-{token}"


def fetch_article(session: requests.Session, token: str) -> dict[str, Any]:
    response = session.get(API_URL.format(token=token), timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("success"):
        raise RuntimeError(f"Weeek API returned success=false for token {token}")
    return data


def build_documents(
    article_payloads: list[dict[str, Any]],
    *,
    token_urls: dict[str, str],
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []

    for payload in article_payloads:
        article = payload["article"]
        token = payload["token"]
        workspace_id, article_id = decode_token(token)
        article_name = clean_text(str(article.get("name") or "Без названия"))
        article_data = article.get("content", {}).get("data", {})
        links = shared_links(article_data)
        source_url = token_urls.get(token) or source_url_for_token(token)

        for chunk_index, chunk in enumerate(chunk_article(article_name, article_data), start=1):
            heading = clean_text(chunk["heading"])
            content = clean_text(chunk["content"])
            if not content:
                continue

            title = article_name if heading == article_name else f"{article_name}: {heading}"
            tags = tags_for_text(article_name, heading, content)
            documents.append(
                {
                    "id": f"weeek_{article_id or token}_{chunk_index:03d}",
                    "doc_type": "faq",
                    "title": title[:500],
                    "content": content,
                    "metadata_json": {
                        "section": article_name,
                        "heading": heading,
                        "category": category_for_text(article_name, heading, content),
                        "tags": tags,
                        "applies_to": {
                            "college_names": [],
                            "domain_tags": [],
                            "specialty_names": [],
                        },
                        "source_type": "weeek",
                        "source_url": source_url,
                        "workspace_id": workspace_id,
                        "workspace_name": payload.get("workspace_name"),
                        "article_id": article_id,
                        "article_name": article_name,
                        "token": token,
                        "chunk_index": chunk_index,
                        "linked_documents": [
                            {
                                "title": link.text,
                                "url": link.href,
                                "token": link.token,
                            }
                            for link in links
                        ],
                        "priority": 1,
                    },
                }
            )

    documents.sort(key=lambda item: (item["metadata_json"]["section"], item["metadata_json"]["chunk_index"]))
    return documents


def crawl(root_url: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    root_token = extract_token(root_url)
    root_workspace_id, _ = decode_token(root_token)
    queue: deque[str] = deque([root_token])
    seen: set[str] = set()
    failed: set[str] = set()
    payloads: list[dict[str, Any]] = []
    token_urls = {root_token: root_url}

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://app.weeek.net",
            "Referer": "https://app.weeek.net/",
            "User-Agent": "Mozilla/5.0",
            "X-WEEEK-LANG": "ru",
        }
    )

    while queue:
        token = queue.popleft()
        if token in seen:
            continue
        seen.add(token)

        try:
            payload = fetch_article(session, token)
        except requests.RequestException as exc:
            failed.add(token)
            print(f"Skipped {token}: {exc}")
            continue

        article = payload.get("article") or {}
        article_data = article.get("content", {}).get("data", {})
        payloads.append(
            {
                "token": token,
                "workspace_name": (payload.get("workspace") or {}).get("name"),
                "article": article,
            }
        )

        for link in shared_links(article_data):
            workspace_id, _ = decode_token(link.token)
            if root_workspace_id and workspace_id and workspace_id != root_workspace_id:
                continue
            token_urls.setdefault(link.token, link.href)
            if link.token not in seen and link.token not in failed:
                queue.append(link.token)

        print(f"Fetched {len(seen)}: {article.get('name')}")

    if failed:
        print(f"Skipped unavailable Weeek documents: {len(failed)}")

    return payloads, token_urls


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch public Weeek shared knowledge base into RAG JSON.")
    parser.add_argument("--root-url", default=DEFAULT_ROOT_URL)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    payloads, token_urls = crawl(args.root_url)
    documents = build_documents(payloads, token_urls=token_urls)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Saved {len(documents)} Weeek RAG documents to {output}")


if __name__ == "__main__":
    main()
