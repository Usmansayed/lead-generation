import requests
from bs4 import BeautifulSoup
import json
import re

def investigate_medium_search(url):
    print('='*80)
    print('MEDIUM.COM HTML STRUCTURE INVESTIGATION')
    print('='*80)
    print(f'Target URL: {url}\n')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    results = {'url': url, 'findings': [], 'sample_html': []}
    
    try:
        print('Fetching page...')
        response = requests.get(url, headers=headers, timeout=30)
        print(f'Status Code: {response.status_code}')
        print(f'Content Length: {len(response.text)} characters\n')
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        with open('medium_raw.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print('Raw HTML saved\n')
        
        print('='*80)
        print('1. SEARCHING FOR ARTICLE CONTAINERS')
        print('='*80)
        
        selectors = ['article', 'div[role="article"]', 'h2', 'h3', '[data-post-id]']
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                print(f'\nFound {len(elements)} elements: {selector}')
                first = elements[0]
                print(f'  Tag: {first.name}')
                print(f'  Classes: {first.get("class", [])}')
                print(f'  Sample: {str(first)[:300]}...\n')
                results['sample_html'].append({'selector': selector, 'html': str(first)[:1000]})
        
        print('='*80)
        print('2. CHECKING INLINE JAVASCRIPT DATA')
        print('='*80)
        
        scripts = soup.find_all('script')
        print(f'Found {len(scripts)} script tags')
        
        for i, script in enumerate(scripts):
            if script.string:
                if '__APOLLO_STATE__' in script.string:
                    print(f'\nApollo GraphQL found in script {i+1}')
                    results['findings'].append('Apollo GraphQL detected')
                if '__NEXT_DATA__' in script.string:
                    print(f'\nNext.js data found in script {i+1}')
                    results['findings'].append('Next.js data detected')
        
        print('\n' + '='*80)
        print('3. ANALYZING ARTICLE LINKS')
        print('='*80)
        
        all_links = soup.find_all('a', href=True)
        print(f'Total links: {len(all_links)}')
        
        article_links = [l for l in all_links if '/@' in l.get('href', '') or '/p/' in l.get('href', '')]
        print(f'Article links: {len(article_links)}')
        
        for i, link in enumerate(article_links[:5]):
            print(f'\n  {i+1}. {link.get("href", "")[:80]}')
            print(f'     Text: {link.get_text(strip=True)[:80]}')
        
        print('\n' + '='*80)
        print('4. ANALYZING HEADINGS')
        print('='*80)
        
        for tag in ['h1', 'h2', 'h3']:
            headings = soup.find_all(tag)
            if headings:
                print(f'\n{tag}: {len(headings)} found')
                for i, h in enumerate(headings[:3]):
                    print(f'  {i+1}. {h.get_text(strip=True)[:100]}')
                    link = h.find('a')
                    if link:
                        print(f'     Link: {link.get("href", "")[:80]}')
        
        with open('medium_investigation.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        
        print('\n' + '='*80)
        print('Investigation complete!')
        print('='*80)
        
    except Exception as e:
        print(f'Error: {e}')
        results['error'] = str(e)
    
    return results

if __name__ == '__main__':
    url = 'https://medium.com/search?q=startup+hiring'
    results = investigate_medium_search(url)
