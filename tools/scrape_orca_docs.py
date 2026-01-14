#!/usr/bin/env python3
"""
Scrape ORCA documentation for offline analysis.

Downloads ORCA Manual, Tutorials, and Input Library to a local cache.

Usage:
    python tools/scrape_orca_docs.py

Output:
    .tmp/orca_docs/
      manual/
      tutorials/
      input_library/
      index.json
      failures.log
"""

import json
import hashlib
import re
import time
import random
from pathlib import Path
from typing import Dict, List, Set, Optional
from urllib.parse import urljoin, urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
import warnings
from bs4 import XMLParsedAsHTMLWarning

# Suppress XML parsing warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Configuration
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = REPO_ROOT / ".tmp" / "orca_docs"
MAX_WORKERS = 12
DELAY_MIN = 0.0
DELAY_MAX = 0.2
MAX_RETRIES = 3
TIMEOUT = 30

# Base URLs and allowed domains
BASE_URLS = {
    "manual": "https://www.faccts.de/docs/orca/6.0/manual/",
    "tutorials": "https://www.faccts.de/docs/orca/6.0/tutorials/",
    "input_library": "https://sites.google.com/site/orcainputlibrary/",
}

ALLOWED_DOMAINS = {
    "manual": ["www.faccts.de"],
    "tutorials": ["www.faccts.de"],
    "input_library": ["sites.google.com"],
}

ALLOWED_PATHS = {
    "manual": "/docs/orca/6.0/manual/",
    "tutorials": "/docs/orca/6.0/tutorials/",
    "input_library": "/site/orcainputlibrary/",
}


class DocScraper:
    def __init__(self, section: str, base_url: str, output_dir: Path):
        self.section = section
        self.base_url = base_url
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.visited: Set[str] = set()
        self.to_visit: List[str] = [base_url]
        self.index: Dict[str, Dict] = {}
        self.failures: List[Dict] = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; QMatSuite Doc Scraper/1.0)"
        })

    def is_allowed_url(self, url: str) -> bool:
        """Check if URL is within allowed domain and path."""
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path

        allowed_domains = ALLOWED_DOMAINS[self.section]
        allowed_path = ALLOWED_PATHS[self.section]

        if domain not in allowed_domains:
            return False

        if self.section in ["manual", "tutorials"]:
            return path.startswith(allowed_path)
        elif self.section == "input_library":
            return path.startswith(allowed_path) or path == "/site/orcainputlibrary"

        return False

    def sanitize_filename(self, url: str) -> str:
        """Generate a stable filename from URL."""
        parsed = urlparse(url)
        path = unquote(parsed.path)
        
        # Remove leading/trailing slashes and replace with underscores
        path = path.strip("/").replace("/", "_")
        
        # Remove query string hash
        if parsed.query:
            # Use hash of query for stability
            query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
            path = f"{path}_{query_hash}"
        
        # If path is empty or just index, use hash of full URL
        if not path or path == "index":
            path = hashlib.md5(url.encode()).hexdigest()[:16]
        
        # Ensure it ends with .html if no extension
        if "." not in path:
            path = f"{path}.html"
        
        # Limit length
        if len(path) > 200:
            path = path[:180] + "_" + hashlib.md5(path.encode()).hexdigest()[:8] + ".html"
        
        return path

    def extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract all links from HTML that are within allowed scope."""
        soup = BeautifulSoup(html, "html.parser")
        links = []
        
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            absolute_url = urljoin(base_url, href)
            
            # Remove fragments
            absolute_url = absolute_url.split("#")[0]
            
            if self.is_allowed_url(absolute_url) and absolute_url not in self.visited:
                links.append(absolute_url)
        
        return links

    def fetch_page(self, url: str) -> Optional[Dict]:
        """Fetch a single page with retries."""
        for attempt in range(MAX_RETRIES):
            try:
                # Random delay for politeness
                delay = random.uniform(DELAY_MIN, DELAY_MAX)
                time.sleep(delay)
                
                response = self.session.get(url, timeout=TIMEOUT)
                response.raise_for_status()
                
                # Extract title
                soup = BeautifulSoup(response.text, "html.parser")
                title_tag = soup.find("title")
                title = title_tag.get_text().strip() if title_tag else ""
                
                return {
                    "url": url,
                    "content": response.text,
                    "title": title,
                    "status": "success",
                }
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    return {
                        "url": url,
                        "content": None,
                        "title": "",
                        "status": "failed",
                        "error": str(e),
                    }
                time.sleep(1 * (attempt + 1))  # Exponential backoff
        
        return None

    def process_page(self, url: str) -> None:
        """Process a single page: fetch, save, extract links."""
        if url in self.visited:
            return
        
        self.visited.add(url)
        result = self.fetch_page(url)
        
        if result["status"] == "success":
            # Save page
            filename = self.sanitize_filename(url)
            filepath = self.output_dir / filename
            filepath.write_text(result["content"], encoding="utf-8")
            
            # Add to index
            self.index[url] = {
                "local_path": str(filepath.relative_to(OUTPUT_ROOT)),
                "title": result["title"],
                "status": "success",
            }
            
            # Extract links for further crawling
            new_links = self.extract_links(result["content"], url)
            for link in new_links:
                if link not in self.visited and link not in self.to_visit:
                    self.to_visit.append(link)
        else:
            # Record failure
            self.failures.append({
                "url": url,
                "error": result.get("error", "Unknown error"),
            })
            self.index[url] = {
                "local_path": None,
                "title": "",
                "status": "failed",
                "error": result.get("error", "Unknown error"),
            }

    def scrape(self) -> Dict:
        """Main scraping loop."""
        print(f"Scraping {self.section} from {self.base_url}...")
        print(f"Output directory: {self.output_dir}")
        
        # Process pages with limited concurrency
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while self.to_visit:
                # Take a batch of URLs
                batch = self.to_visit[:MAX_WORKERS * 2]
                self.to_visit = self.to_visit[MAX_WORKERS * 2:]
                
                # Submit batch
                futures = {executor.submit(self.process_page, url): url for url in batch}
                
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        url = futures[future]
                        print(f"Error processing {url}: {e}")
                        self.failures.append({"url": url, "error": str(e)})
        
        return {
            "section": self.section,
            "base_url": self.base_url,
            "pages_downloaded": len([v for v in self.index.values() if v["status"] == "success"]),
            "failures": self.failures,  # Return list, not count
            "index": self.index,
        }


def main():
    """Main entry point."""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # Scrape each section
    for section, base_url in BASE_URLS.items():
        output_dir = OUTPUT_ROOT / section
        scraper = DocScraper(section, base_url, output_dir)
        result = scraper.scrape()
        results[section] = result
    
    # Combine all indices
    combined_index = {}
    for section_result in results.values():
        combined_index.update(section_result["index"])
    
    # Write combined index
    index_path = OUTPUT_ROOT / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(combined_index, f, indent=2, ensure_ascii=False)
    
    # Write failures log
    all_failures = []
    for section_result in results.values():
        failures_list = section_result.get("failures", [])
        if isinstance(failures_list, list):
            all_failures.extend(failures_list)
    
    failures_path = OUTPUT_ROOT / "failures.log"
    with open(failures_path, "w", encoding="utf-8") as f:
        for failure in all_failures:
            f.write(f"{failure['url']}\n")
            f.write(f"  Error: {failure.get('error', 'Unknown')}\n\n")
    
    # Print summary
    print("\n" + "=" * 60)
    print("Scraping Summary")
    print("=" * 60)
    
    total_pages = 0
    total_failures = 0
    
    for section, result in results.items():
        pages = result["pages_downloaded"]
        failures_list = result.get("failures", [])
        failures_count = len(failures_list) if isinstance(failures_list, list) else failures_list
        total_pages += pages
        total_failures += failures_count
        print(f"{section:20s}: {pages:4d} pages, {failures_count:3d} failures")
    
    print("-" * 60)
    print(f"{'Total':20s}: {total_pages:4d} pages, {total_failures:3d} failures")
    print(f"\nIndex file: {index_path}")
    print(f"Failures log: {failures_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
