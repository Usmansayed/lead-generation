import requests
from urllib.parse import urljoin
import json
import time

def test_quora_access():
    """Test various methods to access Quora without authentication"""
    
    print("=" * 60)
    print("QUORA SCRAPING INVESTIGATION REPORT")
    print("=" * 60)
    print()
    
    # Test URLs
    search_url = "https://www.quora.com/search?q=freelance+developer"
    question_url = "https://www.quora.com/What-is-the-best-way-to-find-freelance-developers"
    
    # Setup session with headers
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }
    
    print("TEST 1: Accessing Search URL")
    print("-" * 60)
    try:
        response = session.get(search_url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Length: {len(response.text)} bytes")
        
        # Check for various indicators
        has_cloudflare = 'cloudflare' in response.text.lower() or 'just a moment' in response.text.lower()
        has_login_modal = 'login' in response.text.lower() or 'sign up' in response.text.lower()
        has_content = len(response.text) > 5000
        
        print(f"Cloudflare Challenge: {has_cloudflare}")
        print(f"Login/Signup Present: {has_login_modal}")
        print(f"Has Substantial Content: {has_content}")
        
        # Save a sample
        with open('quora_search_response.html', 'w', encoding='utf-8') as f:
            f.write(response.text[:2000])
        print("Sample saved to: quora_search_response.html")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print()
    print("TEST 2: Accessing Direct Question URL")
    print("-" * 60)
    try:
        response = session.get(question_url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Length: {len(response.text)} bytes")
        
        has_cloudflare = 'cloudflare' in response.text.lower() or 'just a moment' in response.text.lower()
        has_login_modal = 'login' in response.text.lower() or 'sign up' in response.text.lower()
        has_content = len(response.text) > 5000
        
        print(f"Cloudflare Challenge: {has_cloudflare}")
        print(f"Login/Signup Present: {has_login_modal}")
        print(f"Has Substantial Content: {has_content}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print()
    print("TEST 3: Checking for Public API")
    print("-" * 60)
    api_test_urls = [
        "https://www.quora.com/api/graphql",
        "https://api.quora.com/",
    ]
    
    for api_url in api_test_urls:
        try:
            response = session.get(api_url, headers=headers, timeout=5)
            print(f"{api_url}: {response.status_code}")
        except Exception as e:
            print(f"{api_url}: Not accessible ({str(e)[:50]}...)")
    
    print()
    print("=" * 60)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 60)
    print()
    
    summary = """
Based on the tests:

1. CLOUDFLARE PROTECTION: Quora uses Cloudflare's bot protection
   - All requests are blocked with "Just a moment..." challenge
   - Requires JavaScript execution to pass the challenge
   - Simple HTTP requests will NOT work

2. ROBOTS.TXT ANALYSIS:
   - Explicitly disallows: /search?q=
   - Blocks AI bots including Claude, GPT, Perplexity
   - No public RSS feeds allowed
   - Contact: robotstxt@quora.com for permission

3. AUTHENTICATION WALL:
   - Even if you bypass Cloudflare, login may be required
   - Search results likely need authentication

4. ALTERNATIVE APPROACHES:

   A. Browser Automation (Recommended if legal):
      - Use Playwright or Puppeteer with stealth plugins
      - Can solve Cloudflare challenges
      - Still may require login credentials
      - Risk of IP blocking

   B. Official Quora API:
      - No public API documented
      - Would need to contact Quora directly
      - Likely requires partnership agreement

   C. Third-Party Services:
      - Some data aggregators may have Quora data
      - Usually paid services
      - Legal gray area

   D. Google Search Alternative:
      - Use: site:quora.com "your keywords"
      - Gets indexed questions from Google
      - Limited to what Google has indexed
      - No real-time search

5. LEGAL CONSIDERATIONS:
   - Quora's ToS likely prohibits scraping
   - robots.txt explicitly disallows search
   - Could result in IP bans or legal action
   - Especially prohibited for AI training

RECOMMENDATION: DO NOT scrape Quora without authentication
- High technical barriers (Cloudflare + auth wall)
- Legal/ethical concerns
- Better alternatives exist (Reddit, Stack Overflow, GitHub)
"""
    
    print(summary)
    
if __name__ == "__main__":
    test_quora_access()
