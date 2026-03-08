import httpx
import re

url = 'https://www.google.com/maps/search/food+in+Calgary%2C+Alberta'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
r = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)

# Look for href links with maps/place
href_matches = re.findall(r'href="([^"]*maps/place[^"]+)"', r.text)
print(f'href maps/place: {len(href_matches)} matches')
if href_matches:
    print(f'  Example: {href_matches[0][:100]}')

# Look for any URLs containing /maps/place/
all_matches = re.findall(r'https://www\.google\.com/maps/place/[^\s"<>]+', r.text)
print(f'Full place URLs: {len(all_matches)} matches')
if all_matches:
    print(f'  Example: {all_matches[0][:100]}')

# Look for data attributes
data_matches = re.findall(r'data-[a-z-]+="([^"]*place[^"]*)"', r.text)
print(f'data attributes with place: {len(data_matches)} matches')

# Look for any /maps/place paths
path_matches = re.findall(r'/maps/place/[^\s"<>]+', r.text)
print(f'Place paths: {len(path_matches)} matches')
if path_matches:
    unique = list(dict.fromkeys(path_matches))
    print(f'  Unique paths: {len(unique)}')
    print(f'  First: {unique[0][:100]}')
