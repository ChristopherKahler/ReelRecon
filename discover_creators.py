"""
Instagram Creator Discovery Script
Test script to find creators by keyword, category, and follower range.

Uses same cookie/session approach as ReelRecon's core scraper.

Usage:
    python discover_creators.py --keyword fitness --min 10000 --max 100000 --limit 10
"""

import asyncio
import argparse
import re
import json
import time
from pathlib import Path

import requests
from playwright.async_api import async_playwright


# ============================================================
# Cookie and Session Handling (from core.py pattern)
# ============================================================

def load_cookies(filepath):
    """Load cookies from Netscape cookies.txt format (same as core.py)"""
    cookies = {}
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                name, value = parts[5], parts[6]
                cookies[name] = value
    return cookies


def create_session(cookies_path):
    """Create an authenticated Instagram session (same as core.py)"""
    cookies = load_cookies(cookies_path)

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-IG-App-ID': '936619743392459',
        'X-Requested-With': 'XMLHttpRequest',
        'X-ASBD-ID': '129477',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.instagram.com',
        'Referer': 'https://www.instagram.com/',
    })

    for name, value in cookies.items():
        session.cookies.set(name, value, domain='.instagram.com')

    if 'csrftoken' in cookies:
        session.headers['X-CSRFToken'] = cookies['csrftoken']

    return session


def parse_netscape_cookies_for_playwright(cookies_path: str) -> list[dict]:
    """Parse Netscape format cookies.txt into Playwright cookie format."""
    cookies = []
    with open(cookies_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('\t')
            if len(parts) >= 7:
                domain, _, path, secure, expiry, name, value = parts[:7]
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': domain,
                    'path': path,
                    'secure': secure.upper() == 'TRUE',
                    'httpOnly': False,
                    'expires': int(expiry) if expiry != '0' else -1,
                })
    return cookies


# ============================================================
# Profile Info via API (faster than page scraping)
# ============================================================

def get_profile_info_api(session, username: str) -> dict | None:
    """
    Get profile info using Instagram's private API.
    Much faster than Playwright page visits.
    """
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"

    try:
        resp = session.get(url, timeout=10)

        if resp.status_code == 404:
            return None
        if resp.status_code == 401:
            print("  [AUTH ERROR] Cookies may be expired")
            return None
        if resp.status_code == 429:
            print("  [RATE LIMITED] Waiting...")
            time.sleep(5)
            return None
        if resp.status_code != 200:
            return None

        try:
            data = resp.json()
        except:
            return None

        user = data.get('data', {}).get('user')
        if not user:
            return None

        # Extract data
        followers = user.get('edge_followed_by', {}).get('count', 0)
        full_name = user.get('full_name', '')
        bio = user.get('biography', '')
        is_private = user.get('is_private', False)
        is_verified = user.get('is_verified', False)
        category = user.get('category_name', None)  # Business/Creator category
        profile_pic = user.get('profile_pic_url_hd', user.get('profile_pic_url', ''))

        if is_private:
            return None  # Skip private accounts

        return {
            'username': username,
            'followers': followers,
            'followers_display': format_follower_count(followers),
            'full_name': full_name,
            'bio': bio,
            'category': category,
            'is_verified': is_verified,
            'profile_pic': profile_pic,
            'url': f'https://www.instagram.com/{username}/'
        }

    except requests.exceptions.Timeout:
        print(f"  Timeout fetching @{username}")
        return None
    except Exception as e:
        print(f"  Error fetching @{username}: {e}")
        return None


def format_follower_count(count: int) -> str:
    """Format follower count for display (e.g., 1500000 -> '1.5M')"""
    if count >= 1000000:
        return f"{count/1000000:.1f}M"
    elif count >= 1000:
        return f"{count/1000:.1f}K"
    else:
        return str(count)


def search_instagram_api(session, keyword: str, max_results: int = 50) -> list[dict]:
    """
    Search Instagram using their internal search API.
    Returns list of user dicts with username, full_name, follower_count, etc.
    """
    users = []

    # Instagram's internal search endpoint
    url = f"https://www.instagram.com/web/search/topsearch/?query={keyword}"

    print(f"\nSearching Instagram for: {keyword}")

    try:
        resp = session.get(url, timeout=15)

        if resp.status_code == 401:
            print("  [AUTH ERROR] Cookies may be expired")
            return []
        if resp.status_code == 429:
            print("  [RATE LIMITED] Try again later")
            return []
        if resp.status_code != 200:
            print(f"  [ERROR] Status {resp.status_code}")
            return []

        data = resp.json()

        # Extract users from response
        user_results = data.get('users', [])
        print(f"  Found {len(user_results)} users in search results")

        for item in user_results[:max_results]:
            user = item.get('user', {})
            if user:
                users.append({
                    'username': user.get('username'),
                    'full_name': user.get('full_name', ''),
                    'is_verified': user.get('is_verified', False),
                    'is_private': user.get('is_private', False),
                    'profile_pic': user.get('profile_pic_url', ''),
                })

        return users

    except Exception as e:
        print(f"  Error searching: {e}")
        return []


async def search_hashtag_for_creators(page, keyword: str, max_profiles: int = 30) -> list[str]:
    """
    Fallback: Search a hashtag and extract usernames by clicking into posts.
    Only used if API search doesn't return enough results.
    """
    usernames = set()

    hashtag = keyword.replace('#', '').replace(' ', '')
    url = f'https://www.instagram.com/explore/tags/{hashtag}/'

    print(f"\nSearching hashtag: #{hashtag}")
    await page.goto(url, timeout=30000)
    await page.wait_for_timeout(3000)

    page_content = await page.content()
    if 'Page Not Found' in page_content or 'Sorry, this page' in page_content:
        print(f"  Hashtag #{hashtag} not found")
        return []

    # Scroll to load posts
    for scroll in range(3):
        await page.evaluate('window.scrollBy(0, 1500)')
        await page.wait_for_timeout(800)

    # Find and click posts
    posts = await page.query_selector_all('a[href^="/p/"], a[href^="/reel/"]')
    print(f"  Found {len(posts)} posts")

    for post in posts[:max_profiles * 2]:
        if len(usernames) >= max_profiles:
            break

        try:
            await post.click()
            await page.wait_for_timeout(1200)

            # Extract username from modal
            username = await page.evaluate('''() => {
                const selectors = [
                    'article header a[href^="/"]',
                    'div[role="dialog"] header a[href^="/"]',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const href = el.getAttribute('href');
                        const match = href.match(/^\\/([a-zA-Z0-9_.]+)\\/?$/);
                        if (match && !['p', 'reel', 'explore'].includes(match[1])) {
                            return match[1];
                        }
                    }
                }
                return null;
            }''')

            if username and username not in usernames:
                usernames.add(username)
                print(f"    Found: @{username}")

            await page.keyboard.press('Escape')
            await page.wait_for_timeout(400)

        except:
            try:
                await page.keyboard.press('Escape')
            except:
                pass
            continue

    print(f"  Extracted {len(usernames)} creators from hashtag")
    return list(usernames)


async def discover_creators(
    keyword: str,
    min_followers: int = 0,
    max_followers: int = 10000000,
    category_filter: str | None = None,
    limit: int = 10,
    cookies_path: str = 'cookies.txt',
    headless: bool = False
) -> list[dict]:
    """
    Main discovery function.

    Uses Instagram's search API first (fast), then falls back to
    hashtag browsing if needed.

    Args:
        keyword: Keyword to search
        min_followers: Minimum follower count
        max_followers: Maximum follower count
        category_filter: Optional category to filter by (e.g., 'fitness', 'coach')
        limit: Number of creators to return
        cookies_path: Path to cookies.txt file
        headless: Run browser in headless mode (for hashtag fallback)

    Returns:
        List of creator profiles matching criteria
    """

    # Load cookies
    cookies_file = Path(cookies_path)
    if not cookies_file.exists():
        raise FileNotFoundError(f"Cookies file not found: {cookies_path}")

    # Create API session
    print(f"Creating authenticated session from {cookies_path}")
    api_session = create_session(cookies_path)

    # Quick API test
    print("Verifying authentication...")
    test_resp = api_session.get("https://www.instagram.com/api/v1/users/web_profile_info/?username=instagram")
    if test_resp.status_code == 401:
        print("ERROR: Authentication failed! Please update your cookies.txt")
        return []
    elif test_resp.status_code == 200:
        print("Authentication verified!")
    else:
        print(f"Warning: Got status {test_resp.status_code} - proceeding anyway...")

    matching_creators = []
    potential_usernames = []

    # Method 1: Use Instagram's search API (fast, no browser needed)
    search_results = search_instagram_api(api_session, keyword, max_results=limit * 5)

    if search_results:
        # Filter out private accounts and get usernames
        for user in search_results:
            if not user.get('is_private'):
                potential_usernames.append(user['username'])

    # Method 2: If API didn't return enough, try hashtag browsing
    if len(potential_usernames) < limit * 2:
        print(f"\n  API returned {len(potential_usernames)} users, trying hashtag search...")

        pw_cookies = parse_netscape_cookies_for_playwright(str(cookies_file))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            await context.add_cookies(pw_cookies)
            page = await context.new_page()

            hashtag_users = await search_hashtag_for_creators(page, keyword, max_profiles=limit * 3)

            await browser.close()

            # Add unique usernames from hashtag search
            for u in hashtag_users:
                if u not in potential_usernames:
                    potential_usernames.append(u)

    if not potential_usernames:
        print("\nNo profiles found. Try a different keyword.")
        return []

    # Check each profile via API
    print(f"\nChecking {len(potential_usernames)} profiles via API...")
    print(f"Looking for: {min_followers:,} - {max_followers:,} followers")
    if category_filter:
        print(f"Category filter: {category_filter}")

    for i, username in enumerate(potential_usernames):
        if len(matching_creators) >= limit:
            break

        print(f"  [{i+1}/{len(potential_usernames)}] @{username}...", end=' ', flush=True)

        # Use API for profile lookup
        profile = get_profile_info_api(api_session, username)

        if profile:
            followers = profile['followers']

            # Check follower range
            if min_followers <= followers <= max_followers:
                # Check category filter if specified
                if category_filter:
                    profile_cat = profile.get('category') or ''
                    profile_bio = profile.get('bio') or ''
                    # Check category in both category field and bio
                    if (category_filter.lower() in profile_cat.lower() or
                        category_filter.lower() in profile_bio.lower()):
                        matching_creators.append(profile)
                        print(f"MATCH! {profile['followers_display']} followers ({profile_cat or 'bio match'})")
                    else:
                        print(f"({profile['followers_display']} - category mismatch)")
                else:
                    matching_creators.append(profile)
                    cat_info = f" [{profile.get('category')}]" if profile.get('category') else ""
                    print(f"MATCH! {profile['followers_display']} followers{cat_info}")
            else:
                print(f"({profile['followers_display']} - out of range)")
        else:
            print("(private/not found)")

        # Small delay to avoid rate limiting
        time.sleep(0.3)

    return matching_creators


async def main():
    parser = argparse.ArgumentParser(description='Discover Instagram creators by keyword and follower range')
    parser.add_argument('--keyword', '-k', required=True, help='Keyword/hashtag to search')
    parser.add_argument('--min', type=int, default=0, help='Minimum followers (default: 0)')
    parser.add_argument('--max', type=int, default=10000000, help='Maximum followers (default: 10M)')
    parser.add_argument('--category', '-c', help='Category filter (e.g., fitness, coach, creator)')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Number of results (default: 10)')
    parser.add_argument('--cookies', default='cookies.txt', help='Path to cookies.txt')
    parser.add_argument('--output', '-o', help='Output JSON file (optional)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')

    args = parser.parse_args()

    print("=" * 60)
    print("INSTAGRAM CREATOR DISCOVERY")
    print("=" * 60)
    print(f"Keyword: {args.keyword}")
    print(f"Follower range: {args.min:,} - {args.max:,}")
    if args.category:
        print(f"Category: {args.category}")
    print(f"Target results: {args.limit}")
    print("=" * 60)

    creators = await discover_creators(
        keyword=args.keyword,
        min_followers=args.min,
        max_followers=args.max,
        category_filter=args.category,
        limit=args.limit,
        cookies_path=args.cookies,
        headless=args.headless
    )

    print("\n" + "=" * 60)
    print(f"RESULTS: Found {len(creators)} matching creators")
    print("=" * 60)

    for i, creator in enumerate(creators, 1):
        print(f"\n{i}. @{creator['username']}")
        print(f"   Followers: {creator['followers_display']} ({creator['followers']:,})")
        if creator.get('full_name'):
            print(f"   Name: {creator['full_name']}")
        if creator.get('category'):
            print(f"   Category: {creator['category']}")
        if creator.get('bio'):
            bio_preview = creator['bio'][:100] + '...' if len(creator['bio']) > 100 else creator['bio']
            bio_preview = bio_preview.replace('\n', ' ')
            print(f"   Bio: {bio_preview}")
        if creator.get('is_verified'):
            print(f"   Verified: Yes")
        print(f"   URL: {creator['url']}")

    # Save to JSON if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(creators, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    return creators


if __name__ == '__main__':
    asyncio.run(main())
