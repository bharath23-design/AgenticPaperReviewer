"""
arXiv paper scraper — extracts clean text and metadata from arXiv URLs.
Falls back gracefully: HTML version → abstract page → raw abstract.
"""

import re
import arxiv
import requests
from bs4 import BeautifulSoup
from .logger import get_logger

log = get_logger(__name__)


def extract_arxiv_id(url: str) -> str:
    """Parse arXiv ID from any valid arXiv URL format."""
    patterns = [
        r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)",
        r"arxiv\.org/pdf/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)",
        r"arxiv\.org/html/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)",
        r"([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)",  # bare ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            # Strip only version suffix (v1, v2, …), not the numeric ID itself
            arxiv_id = re.sub(r"v\d+$", "", match.group(1))
            log.debug("Extracted arXiv ID: %s from URL: %s", arxiv_id, url)
            return arxiv_id
    raise ValueError(f"Could not extract arXiv ID from: {url}")


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\t+", " ", text)
    return text.strip()


def _scrape_html_version(arxiv_id: str) -> str:
    """Attempt to get full paper text from arXiv HTML version."""
    url = f"https://arxiv.org/html/{arxiv_id}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PaperReviewer/1.0; research-tool)"}
    log.debug("Fetching HTML version: %s", url)
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            log.warning("HTML version returned HTTP %s for %s", resp.status_code, arxiv_id)
            return ""

        soup = BeautifulSoup(resp.content, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        container = (
            soup.find("article")
            or soup.find("div", class_="ltx_document")
            or soup.find("div", id="content")
        )
        text = container.get_text(separator="\n", strip=True) if container else soup.get_text(separator="\n", strip=True)
        cleaned = _clean_text(text)
        log.info("HTML scrape succeeded for %s — %d chars", arxiv_id, len(cleaned))
        return cleaned
    except Exception as exc:
        log.warning("HTML scrape failed for %s: %s", arxiv_id, exc)
        return ""


def _scrape_abstract_page(arxiv_id: str) -> str:
    """Scrape the abstract landing page as a lightweight fallback."""
    url = f"https://arxiv.org/abs/{arxiv_id}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PaperReviewer/1.0; research-tool)"}
    log.debug("Falling back to abstract page: %s", url)
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(resp.content, "html.parser")

        abstract_block = soup.find("blockquote", class_="abstract")
        abstract_text = abstract_block.get_text(strip=True) if abstract_block else ""

        subjects_block = soup.find("td", class_="subjects")
        subjects_text = subjects_block.get_text(strip=True) if subjects_block else ""

        log.info("Abstract page scraped for %s", arxiv_id)
        return f"{abstract_text}\n\nSubjects: {subjects_text}"
    except Exception as exc:
        log.warning("Abstract page scrape failed for %s: %s", arxiv_id, exc)
        return ""


def scrape_paper(url: str) -> dict:
    """
    Main entry point. Returns:
        {
            metadata: {title, authors, abstract, published, arxiv_id, categories},
            full_text: str,
            abstract: str,
        }
    """
    log.info("Starting scrape for URL: %s", url)
    arxiv_id = extract_arxiv_id(url)

    client = arxiv.Client()
    search = arxiv.Search(id_list=[arxiv_id])
    try:
        paper = next(client.results(search))
    except StopIteration:
        log.error("Paper not found on arXiv: %s", arxiv_id)
        raise ValueError(f"Paper not found on arXiv: {arxiv_id}")

    metadata = {
        "title": paper.title,
        "authors": [str(a) for a in paper.authors],
        "abstract": paper.summary,
        "published": str(paper.published.date()),
        "arxiv_id": arxiv_id,
        "categories": paper.categories,
        "doi": paper.doi or "",
    }
    log.info("Metadata fetched — title: %s | authors: %d", paper.title, len(paper.authors))

    full_text = _scrape_html_version(arxiv_id)

    if not full_text or len(full_text) < 500:
        log.info("HTML text too short (%d chars), trying abstract page", len(full_text))
        full_text = _scrape_abstract_page(arxiv_id)

    if not full_text:
        log.warning("All scrape strategies failed, using raw abstract for %s", arxiv_id)
        full_text = paper.summary

    log.info("Scrape complete — %d chars of text for %s", len(full_text), arxiv_id)
    return {
        "metadata": metadata,
        "full_text": full_text,
        "abstract": paper.summary,
    }
