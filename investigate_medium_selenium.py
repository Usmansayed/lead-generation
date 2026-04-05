import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

def investigate_medium_with_selenium(url):
    print("="*80)
    print("MEDIUM.COM HTML STRUCTURE INVESTIGATION (SELENIUM)")
    print("="*80)
    print(f"Target URL: {url}")
    print()
    
    results = {
        "url": url,
        "findings": [],
        "working_selectors": {},
        "recommendations": []
    }
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = None
    try:
        print("Starting Chrome browser...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        print(f"Loading page: {url}")
        driver.get(url)
        
        print("Waiting for content to load (15 seconds)...")
        time.sleep(15)
        
        print(f"Page title: {driver.title}")
        print()
        
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        with open("medium_selenium_raw.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print("Raw HTML saved")
        print()
        
        print("="*80)
        print("1. SEARCHING FOR ARTICLE CONTAINERS")
        print("="*80)
        
        selectors_to_try = {
            "article": "article",
            "h2_tags": "h2",
            "h3_tags": "h3",
            "article_links": "a[href*='/@']",
            "divs": "div[data-testid]",
        }
        
        for name, selector in selectors_to_try.items():
            elements = soup.select(selector)
            if elements:
                print()
                print(f"[+] {name}: {len(elements)} found")
                results["findings"].append(f"{name}: {len(elements)} elements")
                
                first = elements[0]
                print(f"  Tag: {first.name}")
                print(f"  Classes: {first.get('class', [])}")
                print(f"  Sample: {str(first)[:200]}...")
                    
                results["working_selectors"][name] = {
                    "selector": selector,
                    "count": len(elements),
                    "sample_html": str(first)[:500]
                }
        
        print()
        print("="*80)
        print("2. EXTRACTING ARTICLE DATA")
        print("="*80)
        
        articles = []
        h2_elements = soup.find_all("h2")
        print()
        print(f"Found {len(h2_elements)} h2 tags")
        
        for i, h2 in enumerate(h2_elements[:5]):
            article = {}
            article["title"] = h2.get_text(strip=True)
            
            link = h2.find("a") or (h2.find_parent("a") if h2.parent else None)
            if link:
                article["url"] = link.get("href", "")
            
            parent = h2.parent
            if parent:
                author_link = parent.find("a", href=lambda x: x and "/@" in x)
                if author_link:
                    article["author"] = author_link.get_text(strip=True)
                    article["author_url"] = author_link.get("href", "")
                
                paragraphs = parent.find_all("p")
                if paragraphs:
                    article["preview"] = paragraphs[0].get_text(strip=True)[:200]
            
            articles.append(article)
            
            print()
            print(f"Article {i+1}:")
            print(f"  Title: {article.get('title', 'N/A')[:80]}")
            print(f"  URL: {article.get('url', 'N/A')[:80]}")
            print(f"  Author: {article.get('author', 'N/A')}")
        
        results["sample_articles"] = articles
        
        print()
        print("="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        
        recommendations = [
            "Medium uses Cloudflare - Selenium required",
            "Articles are in h2 tags with nested links",
            "Consider RapidAPI Medium API",
            "GraphQL: https://medium.com/_/graphql",
            "Alternative: RSS feeds"
        ]
        
        results["recommendations"] = recommendations
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
        
        with open("medium_investigation_selenium.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        
        print()
        print("Investigation complete!")
        print("Files saved:")
        print("  - medium_selenium_raw.html")
        print("  - medium_investigation_selenium.json")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if driver:
            driver.quit()
    
    return results

if __name__ == "__main__":
    url = "https://medium.com/search?q=startup+hiring"
    results = investigate_medium_with_selenium(url)
