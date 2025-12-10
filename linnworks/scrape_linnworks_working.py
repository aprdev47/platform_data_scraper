import csv
import re
import asyncio
import sys
from playwright.async_api import async_playwright

def extract_email(text):
    """Extract email addresses from text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    filtered = [e for e in emails if not any(skip in e.lower() for skip in [
        'example.com', 'test.com', 'placeholder', 'sentry.io', 'wixpress.com', 'gravatar.com'
    ])]
    return filtered[0] if filtered else ''

async def collect_partner_urls(browser):
    """Collect all partner profile URLs from all pages"""
    all_partners = []

    print("Collecting partner URLs from all pages...")
    sys.stdout.flush()

    # Go through all 9 pages
    for page_num in range(1, 10):
        # Create a fresh page for each iteration
        page = await browser.new_page()

        url = f"https://www.linnworks.com/partners/?_paged={page_num}"
        print(f"\nFetching page {page_num}/9...")
        sys.stdout.flush()

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=25000)
            await page.wait_for_timeout(8000)  # Match the working test

            # Find all partner cards with exact working selector
            partner_cards = await page.query_selector_all('a.search-teaser-integration')

            for card in partner_cards:
                href = await card.get_attribute('href')
                if href:
                    # Get partner name from aria-title
                    aria_title = await card.get_attribute('aria-title')
                    if aria_title and 'view integration:' in aria_title:
                        name = aria_title.replace('view integration:', '').strip()
                    else:
                        # Extract from URL as fallback
                        name = href.split('/')[-2].replace('-', ' ').title()

                    # Avoid duplicates
                    if href not in [p['url'] for p in all_partners]:
                        all_partners.append({
                            'name': name,
                            'url': href
                        })

            print(f"Found {len(partner_cards)} partners on this page (total unique: {len(all_partners)})")
            sys.stdout.flush()

        except Exception as e:
            print(f"Error on page {page_num}: {str(e)}")
            sys.stdout.flush()
        finally:
            await page.close()

    return all_partners

async def scrape_partner_profile(page, url):
    """Scrape a single partner profile for website and email"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(2000)

        # Get content
        content = await page.content()
        page_text = await page.inner_text('body')

        # Extract email
        email = extract_email(page_text)
        if not email:
            email = extract_email(content)

        # Find website link
        website = ''
        links = await page.query_selector_all('a[href]')

        for link in links:
            href = await link.get_attribute('href')
            if not href:
                continue

            # Skip internal and social links
            if any(skip in href.lower() for skip in [
                'linnworks.com',
                'facebook.com',
                'twitter.com',
                'x.com',
                'linkedin.com',
                'instagram.com',
                'youtube.com',
                'tiktok.com',
                'mailto:',
                'javascript:',
                'tel:'
            ]):
                continue

            # Skip document links
            if any(ext in href.lower() for ext in ['.pdf', '.doc', '.xls']):
                continue

            if href.startswith('http'):
                link_text = (await link.inner_text()).lower().strip()

                # Prioritize website/visit links
                if any(keyword in link_text for keyword in ['website', 'visit', 'learn more', 'view site', 'get started', 'sign up']):
                    website = href
                    break

                # Save first external link
                if not website:
                    website = href

        return website, email

    except Exception as e:
        print(f"    Error: {str(e)}", file=sys.stderr)
        return '', ''

async def main():
    output_file = '/Users/athul/dev/ai exp/linnworks_partners.csv'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Step 1: Collect all partner URLs
        partners = await collect_partner_urls(browser)
        print(f"\n✓ Collected {len(partners)} partner profiles\n")
        sys.stdout.flush()

        if len(partners) == 0:
            print("ERROR: No partners collected. Exiting.")
            await browser.close()
            return

        # Step 2: Scrape each partner profile
        page = await browser.new_page()
        results = []

        for i, partner in enumerate(partners, 1):
            print(f"Processing {i}/{len(partners)}: {partner['name']}")
            sys.stdout.flush()

            website, email = await scrape_partner_profile(page, partner['url'])

            results.append({
                'name': partner['name'],
                'profile_url': partner['url'],
                'website': website,
                'email': email
            })

            if website or email:
                print(f"  ✓ Website: {website if website else 'N/A'}")
                print(f"  ✓ Email: {email if email else 'N/A'}")
            else:
                print(f"  - No data found")
            sys.stdout.flush()

            # Delay between requests
            await asyncio.sleep(1.5)

        await browser.close()

    # Step 3: Write to CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Company Name', 'Profile URL', 'Website', 'Email'])

        for result in results:
            writer.writerow([
                result['name'],
                result['profile_url'],
                result['website'],
                result['email']
            ])

    print(f"\n✓ Results saved to: {output_file}")

    # Statistics
    websites_found = sum(1 for r in results if r['website'])
    emails_found = sum(1 for r in results if r['email'])
    print(f"\nStatistics:")
    print(f"  Total partners: {len(results)}")
    print(f"  Websites found: {websites_found}")
    print(f"  Emails found: {emails_found}")

if __name__ == '__main__':
    asyncio.run(main())
