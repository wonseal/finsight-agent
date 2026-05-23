from __future__ import annotations

from src.sec.client import SECClient

FILING_BASE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"


class FilingDownloader:

    def __init__(self, client: SECClient) -> None:
        self.client = client

    def build_document_url(self, cik: str, accession_number: str, primary_document: str) -> str:
        url = FILING_BASE_URL.format(
            cik=cik.lstrip("0"),
            accession=accession_number.replace("-", ""),
            document=primary_document,
        )
        return url

    def download_primary_document(self, cik: str, accession_number: str, primary_document: str) -> str:
        url = self.build_document_url(cik, accession_number, primary_document)
        return self.client.get_text(url)
