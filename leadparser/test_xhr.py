#!/usr/bin/env python3
"""Quick test to see what XHR is getting from Google Maps."""

import httpx
import re

url = "https://www.google.com/maps/search/food+in+Calgary%2C+Alberta"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

print(f"Fetching: {url}")
try:
    r = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
    print(f"Status: {r.status_code}")
    print(f"Content length: {len(r.text)} characters")
    
    # New extraction method from APP_INITIALIZATION_STATE
    unique = []
    seen = set()
    
    match = re.search(r'window\.APP_INITIALIZATION_STATE\s*=\s*(\[.+?\]);</script>', r.text, re.DOTALL)
    if not match:
        match = re.search(r'APP_INITIALIZATION_STATE\s*=\s*(\[.+?\]);', r.text, re.DOTALL)
    
    if match:
        print("Found APP_INITIALIZATION_STATE!")
        json_str = match.group(1)
        # Look for place URLs
        place_urls = re.findall(r'(https://www\.google\.com/maps/place/[^"\\]+)', json_str)
        print(f"Found {len(place_urls)} raw URL matches in JSON")
        for url in place_urls:
            url = url.replace('\\u003d', '=').replace('\\u0026', '&').replace('\\', '')
            clean = re.split(r"(?=/data=)", url)[0]
            if "/maps/place/" in clean and clean not in seen:
                seen.add(clean)
                unique.append(url)
    else:
        print("APP_INITIALIZATION_STATE not found!")
    
    print(f"\nTotal unique URLs: {len(unique)}")
    if unique:
        print("\nFirst 5 URLs:")
        for url in unique[:5]:
            print(f"  {url[:100]}")
    else:
        # Show what the JSON looks like
        if match:
            print("\nJSON snippet (first 500 chars):")
            print(json_str[:500])
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
