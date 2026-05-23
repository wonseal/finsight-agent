from __future__ import annotations

from bs4 import BeautifulSoup

DEFAULT_KEYWORDS = [
    "revenue",
    "net sales",
    "growth",
    "increase",
    "decrease",
    "demand",
    "acquisition",
    "customer",
    "data center",
    "margin",
    "operating income",
    "cash flow",
    "risk",
    "artificial intelligence",
    "ai",
    "accelerated computing",
    "supply",
    "pricing",
    "volume",
    "product",
    "market",
    "competition",
    "inventory",
    "backlog",
]


class FilingParser:

    def html_to_text(self, html: str) -> str:
        """Convert an SEC filing HTML document to plain text.

        Strips script, style, and table tags, then extracts text and removes blank lines.
        """
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "table"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines()]
        non_empty_lines = [line for line in lines if line]
        return "\n".join(non_empty_lines)

    def extract_relevant_sections(
        self,
        text: str,
        keywords: list[str] | None = None,
        context_lines: int = 2,
    ) -> str:
        """Extract lines containing keywords and their surrounding context.

        For each keyword match, includes context_lines lines before and after.
        Deduplicates and preserves original order before joining.
        """
        if keywords is None:
            keywords = DEFAULT_KEYWORDS
        lines = text.splitlines()
        relevant_lines = set()
        for i, line in enumerate(lines):
            if any(keyword.lower() in line.lower() for keyword in keywords):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                relevant_lines.update(range(start, end)) # find the indexes of lines to include
        sorted_lines = sorted(relevant_lines) # sort the indexes to maintain original order
        extracted_text = "\n".join(lines[i] for i in sorted_lines) # join the selected lines into a single string
        return extracted_text
