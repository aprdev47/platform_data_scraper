import csv
import re
import asyncio
import sys
from playwright.async_api import async_playwright

def extract_email(text):
    """Extract email addresses from text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    # Filter out common false positives
    filtered = [e for e in emails if not any(skip in e.lower() for skip in ['example.com', 'test.com', 'placeholder'])]
    return filtered[0] if filtered else ''

async def scrape_profile(page, url):
    """Scrape a single profile page for website and email"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(1500)

        # Get the full page content and HTML
        content = await page.content()
        page_text = await page.inner_text('body')

        # Extract email from visible text and HTML
        email = extract_email(page_text)
        if not email:
            email = extract_email(content)

        # Try to find website link - look for external links
        website = ''
        links = await page.query_selector_all('a[href]')

        for link in links:
            href = await link.get_attribute('href')
            if not href:
                continue

            # Skip internal links and social media
            if any(skip in href.lower() for skip in [
                'cin7.partnerpage.io',
                'cin7.com',
                'cin7-',
                'dearsystems.com',
                'facebook.com',
                'twitter.com',
                'x.com',
                'linkedin.com',
                'instagram.com',
                'youtube.com',
                'mailto:',
                'javascript:',
                'tel:'
            ]):
                continue

            # Look for actual company website
            if href.startswith('http'):
                link_text = (await link.inner_text()).lower().strip()

                # Skip if it's a document/resource link
                if any(ext in href.lower() for ext in ['.pdf', '.doc', '.xls', '/resources/', '/media/']):
                    continue

                # Prioritize links with website indicators
                if any(keyword in link_text for keyword in ['website', 'visit', 'company']):
                    website = href
                    break

                # Save first external link
                if not website and href.startswith('http'):
                    website = href

        return website, email

    except Exception as e:
        print(f"Error scraping {url}: {str(e)}", file=sys.stderr)
        return '', ''

async def main():
    input_file = '/Users/athul/dev/ai exp/cin7 - Sheet5.csv'
    output_file = '/Users/athul/dev/ai exp/cin7 - Sheet5_updated.csv'

    # Read the CSV
    rows = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # Process each row
        for i, row in enumerate(rows):
            if i == 0:  # Header row
                while len(row) < 4:
                    row.append('')
                if not row[2]:
                    row[2] = 'Website'
                if not row[3]:
                    row[3] = 'Email'
                continue

            # Skip if no URL in column 2
            if len(row) < 2 or not row[1]:
                continue

            print(f"\nProcessing {i}/{len(rows)-1}: {row[0]}")
            sys.stdout.flush()

            # Extend row to have 4 columns if needed
            while len(row) < 4:
                row.append('')

            # Scrape if website or email is missing or has wrong data
            should_scrape = (not row[2] or not row[3] or
                           'dearsystems.com' in row[2] or
                           'Login' in row[2])

            if should_scrape:
                website, email = await scrape_profile(page, row[1])

                if not row[2] or 'dearsystems.com' in row[2] or 'Login' in row[2]:
                    row[2] = website
                if not row[3]:
                    row[3] = email

                if website or email:
                    print(f"  ✓ Website: {website if website else 'N/A'}")
                    print(f"  ✓ Email: {email if email else 'N/A'}")
                else:
                    print(f"  - No data found")
                sys.stdout.flush()

                # Small delay between requests
                await asyncio.sleep(1)

        await browser.close()

    # Write updated CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"\n✓ Updated CSV saved to: {output_file}")

if __name__ == '__main__':
    asyncio.run(main())
