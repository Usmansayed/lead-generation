"""
Medium.com Article Scraper - FIXED VERSION
--------------------------
Extracts articles from Medium search results using Selenium.

Requirements:
- pip install selenium beautifulsoup4

Usage:
python medium_scraper_fixed.py
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

def scrape_medium_search(query, max_articles=10):
    """
    Scrape Medium search results for a given query.
    
    Args:
        query: Search query (e.g., "startup hiring")
        max_articles: Maximum number of articles to extract
        
    Returns:
        List of article dictionaries
    """
    print(f"Searching Medium for: {query}")
    print("-" * 80)
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0")
    
    driver = None
    articles_data = []
    
    try:
        # Initialize Chrome
        print("Starting browser...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        # Build URL
        search_url = f"https://medium.com/search?q={query.replace(' ', '+')}"
        print(f"Loading: {search_url}")
        driver.get(search_url)
        
        # Wait for Cloudflare challenge (IMPORTANT!)
        print("Waiting for Cloudflare challenge (15 seconds)...")
        time.sleep(15)
        
        print(f"Page loaded: {driver.title}")
        
        # Parse HTML
        soup = BeautifulSoup(driver.page_source, "html.parser")
        articles = soup.find_all("article", limit=max_articles)
        
        print(f"Found {len(articles)} articles")
        print()
        
        # Extract data from each article
        for i, article in enumerate(articles, 1):
            article_data = {"id": i}
            
            # Extract title
            title_elem = article.find("h2")
            if title_elem:
                article_data["title"] = title_elem.get_text(strip=True)
                
                # FIXED: URL is in h2's parent <a> tag
                if title_elem.parent and title_elem.parent.name == "a":
                    url = title_elem.parent.get("href", "")
                    if url and not url.startswith("http"):
                        url = f"https://medium.com{url}"
                    article_data["url"] = url
                else:
                    article_data["url"] = None
            else:
                article_data["title"] = None
                article_data["url"] = None
                
            # Extract preview text
            preview_elem = article.find("h3")
            if preview_elem:
                article_data["preview"] = preview_elem.get_text(strip=True)
            else:
                article_data["preview"] = None
                
            # Extract author
            author_link = article.find("a", href=lambda x: x and "/@" in x)
            if author_link:
                article_data["author"] = author_link.get_text(strip=True)
                author_url = author_link.get("href", "")
                if author_url and not author_url.startswith("http"):
                    author_url = f"https://medium.com{author_url.split('?')[0]}"
                article_data["author_url"] = author_url
            else:
                article_data["author"] = None
                article_data["author_url"] = None
            
            articles_data.append(article_data)
            
            # Print article info (with encoding safety)
            title_safe = article_data.get('title', 'N/A')
            if title_safe and len(title_safe) > 60:
                title_safe = title_safe[:60] + "..."
            
            print(f"Article #{i}")
            print(f"  Title: {title_safe}")
            print(f"  URL: {article_data['url']}")
            print(f"  Author: {article_data['author']}")
            print()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            driver.quit()
            print("Browser closed")
    
    return articles_data


def save_results(articles, filename="medium_articles.json"):
    """Save articles to JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(articles)} articles to {filename}")


if __name__ == "__main__":
    # Example usage
    query = "startup hiring"
    articles = scrape_medium_search(query, max_articles=10)
    
    if articles:
        save_results(articles)
        print()
        print("="*80)
        print("SUCCESS!")
        print(f"Extracted {len(articles)} articles from Medium")
        print("="*80)
        print()
        print("WORKING SELECTORS USED:")
        print("  - Articles: article tag")
        print("  - Titles: h2 tag inside article")
        print("  - URLs: h2.parent (the parent <a> tag)")
        print("  - Preview: h3 tag inside article")
        print("  - Authors: a[href*='/@'] inside article")
    else:
        print("No articles extracted")
