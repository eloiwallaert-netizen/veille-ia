#!/usr/bin/env python3
"""Ingestion quotidienne des actus IA depuis des flux RSS publics.

Aucune dépendance externe (stdlib uniquement) : pensé pour tourner tel quel
sur un runner GitHub Actions standard. Pas d'appel LLM : la catégorisation
par thématique se fait par mots-clés, et les métiers concernés sont déduits
de la matrice RELEVANCE (dupliquée depuis index.html) plutôt que d'un
second dictionnaire de mots-clés à entretenir en parallèle.
"""
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "articles.json"

FEEDS = [
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("Google AI Blog", "https://blog.google/innovation-and-ai/technology/ai/rss/"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    ("VentureBeat", "https://venturebeat.com/category/ai/feed"),
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    ("The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

MAX_AGE_HOURS = 48
MAX_AUTO_ARTICLES = 30
USER_AGENT = "Mozilla/5.0 (compatible; veille-ia-bot/1.0; +https://modjo-veille-ia.netlify.app/)"

# Mots-clés par thématique (recherche insensible à la casse dans titre + résumé)
THEME_KEYWORDS = {
    "llm": ["llm", "large language model", "gpt-", "foundation model", "claude", "gemini", "fine-tun", "language model"],
    "agents": ["agent", "agentic", "autonomous ai", "multi-agent"],
    "automation": ["automat", "workflow", "rpa", "zapier", "n8n"],
    "ethics": ["regulat", "ai act", "gdpr", "governance", "policy", "bias", "lawsuit", "copyright", "safety"],
    "genai-product": ["generative ai", "copilot", "assistant", "chatbot", "genai", "gen ai"],
    "data": ["rag", "retrieval-augmented", "embedding", "vector database", "data pipeline", "dataset"],
    "nocode": ["no-code", "no code", "low-code", "app builder"],
}

# Copie de la matrice métier × thématique définie dans index.html
RELEVANCE = {
    "sales":      {"agents": "priority", "automation": "priority", "data": "secondary", "llm": "secondary", "genai-product": "secondary", "ethics": "low", "nocode": "low"},
    "csm":        {"agents": "priority", "automation": "priority", "data": "priority", "genai-product": "secondary", "llm": "low", "ethics": "low", "nocode": "secondary"},
    "management": {"ethics": "priority", "llm": "secondary", "agents": "secondary", "automation": "secondary", "genai-product": "secondary", "data": "secondary", "nocode": "secondary"},
    "product":    {"genai-product": "priority", "agents": "priority", "llm": "priority", "ethics": "secondary", "data": "secondary", "automation": "low", "nocode": "secondary"},
    "tech":       {"llm": "priority", "data": "priority", "agents": "priority", "automation": "priority", "genai-product": "secondary", "ethics": "secondary", "nocode": "secondary"},
    "marketing":  {"genai-product": "priority", "nocode": "priority", "data": "secondary", "automation": "secondary", "llm": "low", "ethics": "low", "agents": "secondary"},
    "ops":        {"ethics": "priority", "automation": "priority", "data": "priority", "nocode": "secondary", "llm": "low", "genai-product": "low", "agents": "secondary"},
}

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(raw):
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def parse_feed(raw_xml):
    root = ET.fromstring(raw_xml)
    items = []
    if root.tag == "rss" or root.find("channel") is not None:
        for item in root.findall(".//item"):
            title = strip_html(item.findtext("title", ""))
            link = (item.findtext("link", "") or "").strip()
            desc = strip_html(item.findtext("description", ""))
            pub = parse_date(item.findtext("pubDate", ""))
            items.append((title, link, desc, pub))
    elif root.tag == f"{ATOM_NS}feed":
        for entry in root.findall(f"{ATOM_NS}entry"):
            title = strip_html(entry.findtext(f"{ATOM_NS}title", ""))
            link_el = entry.find(f"{ATOM_NS}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{ATOM_NS}link")
            link = link_el.get("href", "").strip() if link_el is not None else ""
            desc = strip_html(entry.findtext(f"{ATOM_NS}summary", "") or entry.findtext(f"{ATOM_NS}content", ""))
            pub = parse_date(entry.findtext(f"{ATOM_NS}published", "") or entry.findtext(f"{ATOM_NS}updated", ""))
            items.append((title, link, desc, pub))
    else:
        raise ValueError(f"format de flux non reconnu (racine <{root.tag}>)")
    return items


def tag_themes(text):
    low = text.lower()
    return [theme for theme, keywords in THEME_KEYWORDS.items() if any(k in low for k in keywords)]


def derive_metiers(themes):
    metiers = set()
    for metier, rel in RELEVANCE.items():
        for theme in themes:
            if rel.get(theme) == "priority":
                metiers.add(metier)
                break
    return sorted(metiers)


def slug_id(link, title):
    h = hashlib.sha1((link or title).encode("utf-8")).hexdigest()[:12]
    return f"auto-{h}"


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_AGE_HOURS)

    existing = json.loads(DATA_FILE.read_text(encoding="utf-8")) if DATA_FILE.exists() else []
    existing_ids = {a["id"] for a in existing}

    new_articles = []
    ok_feeds = 0
    ko_feeds = []

    for source_name, url in FEEDS:
        try:
            raw = fetch(url)
            items = parse_feed(raw)
            ok_feeds += 1
        except (urllib.error.URLError, ET.ParseError, ValueError, TimeoutError) as e:
            ko_feeds.append(f"{source_name} ({e})")
            continue

        for title, link, desc, pub in items:
            if not title or not link:
                continue
            if pub is None or pub < cutoff:
                continue
            article_id = slug_id(link, title)
            if article_id in existing_ids:
                continue
            themes = tag_themes(f"{title} {desc}")
            metiers = derive_metiers(themes)
            new_articles.append({
                "id": article_id,
                "date": pub.astimezone(timezone.utc).strftime("%Y-%m-%d"),
                "source": source_name,
                "title": title,
                "summary": (desc[:220].rstrip() + "…") if len(desc) > 220 else desc,
                "sourceUrl": link,
                "auto": True,
                "metiers": metiers,
                "themes": themes,
                "resources": [],
            })
            existing_ids.add(article_id)

    untagged = sum(1 for a in new_articles if not a["themes"])

    curated = [a for a in existing if not a.get("auto")]
    auto_existing = [a for a in existing if a.get("auto")]
    all_auto = new_articles + auto_existing
    all_auto.sort(key=lambda a: a["date"], reverse=True)
    dropped = max(0, len(all_auto) - MAX_AUTO_ARTICLES)
    all_auto = all_auto[:MAX_AUTO_ARTICLES]

    combined = curated + all_auto
    combined.sort(key=lambda a: a["date"], reverse=True)

    DATA_FILE.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[fetch_news] flux OK : {ok_feeds}/{len(FEEDS)}")
    if ko_feeds:
        print(f"[fetch_news] flux en échec : {', '.join(ko_feeds)}")
    print(f"[fetch_news] nouveaux articles ajoutés : {len(new_articles)}")
    if untagged:
        print(f"[fetch_news] {untagged} nouvel(aux) article(s) sans thématique détectée (mots-clés insuffisants, resteront visibles seulement dans le fil global)")
    if dropped:
        print(f"[fetch_news] {dropped} ancien(s) article(s) auto retiré(s) (plafond de {MAX_AUTO_ARTICLES})")
    print(f"[fetch_news] total conservé : {len(combined)} (curated : {len(curated)}, auto : {len(all_auto)})")

    if ok_feeds == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
