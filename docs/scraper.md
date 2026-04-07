# `src/scraper.py` — arXiv Paper Scraper

## Purpose

Fetches paper metadata and full text from arXiv. Three strategies are tried in order, falling back gracefully if a strategy returns too little text.

## Imports

| Import | Used for |
|--------|----------|
| `re` | Regex patterns to extract arXiv ID from URL |
| `arxiv` | Official arXiv Python client for metadata |
| `requests` | HTTP GET for HTML and abstract pages |
| `bs4.BeautifulSoup` | HTML parsing |
| `.logger.get_logger` | Structured logging |

## Public API

### `scrape_paper(url: str) -> dict`

Main entry point. Accepts any valid arXiv URL format.

Returns:
```python
{
    "metadata": {
        "title": str,
        "authors": list[str],
        "abstract": str,
        "published": str,   # ISO date
        "arxiv_id": str,
        "categories": list[str],
        "doi": str,
    },
    "full_text": str,
    "abstract": str,
}
```

### `extract_arxiv_id(url: str) -> str`

Parses an arXiv ID from URLs in any of these formats:
- `arxiv.org/abs/2404.00001`
- `arxiv.org/pdf/2404.00001`
- `arxiv.org/html/2404.00001`
- Bare ID: `2404.00001`

Version suffixes (v1, v2, …) are stripped.

## Scraping Strategy (in order)

1. **HTML version** (`arxiv.org/html/{id}`) — full paper text, prefers `<article>` or `.ltx_document` container.
2. **Abstract page** (`arxiv.org/abs/{id}`) — lightweight fallback, extracts `<blockquote class="abstract">`.
3. **Raw abstract** from `arxiv.Client()` — last resort when both HTTP strategies fail or return < 500 chars.

## Internal Helpers

| Function | Description |
|----------|-------------|
| `_clean_text(text)` | Collapses 3+ newlines, extra spaces, and tabs |
| `_scrape_html_version(arxiv_id)` | Strategy 1 |
| `_scrape_abstract_page(arxiv_id)` | Strategy 2 |
