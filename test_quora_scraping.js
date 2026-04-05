const puppeteer = require('puppeteer');

(async () => {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const page = await browser.newPage();
  
  // Set a realistic user agent
  await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
  
  console.log('Navigating to Quora search...');
  try {
    await page.goto('https://www.quora.com/search?q=freelance+developer', { 
      waitUntil: 'networkidle2',
      timeout: 30000 
    });
    
    // Wait for potential login modal or content to load
    await page.waitForTimeout(3000);
    
    // Check if we got through
    const html = await page.content();
    console.log('Page title:', await page.title());
    
    // Check for specific elements
    const hasCloudflare = html.includes('cloudflare') || html.includes('Just a moment');
    const hasLoginWall = html.includes('sign up') || html.includes('Sign Up') || html.includes('login');
    const hasSearchResults = html.includes('search') || html.includes('question');
    
    console.log('\nStatus:');
    console.log('- Cloudflare detected:', hasCloudflare);
    console.log('- Login wall detected:', hasLoginWall);
    console.log('- Potential search results:', hasSearchResults);
    console.log('- HTML length:', html.length);
    
    // Try to find question elements
    const questions = await page.evaluate(() => {
      const elements = document.querySelectorAll('a[href*="/"]');
      return Array.from(elements).slice(0, 10).map(el => ({
        text: el.textContent.trim().substring(0, 100),
        href: el.href
      }));
    });
    
    console.log('\nFound elements:', questions.length);
    if (questions.length > 0) {
      console.log('Sample links:', JSON.stringify(questions.slice(0, 3), null, 2));
    }
    
    // Save HTML for analysis
    const fs = require('fs');
    fs.writeFileSync('quora_test_output.html', html);
    console.log('\nHTML saved to quora_test_output.html');
    
  } catch (error) {
    console.error('Error accessing Quora:', error.message);
  }
  
  await browser.close();
})();
