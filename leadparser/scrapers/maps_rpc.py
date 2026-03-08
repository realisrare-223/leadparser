"""
Google Maps RPC Scraper - Fast grid-based search
Uses grid search + APP_INITIALIZATION_STATE parsing for high-speed extraction.
"""

import asyncio
import json
import logging
import random
import re
from typing import Callable, Optional
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)


# City coordinates database (lat, lng)
CITY_COORDS = {
    "calgary": (51.0447, -114.0719),
    "vancouver": (49.2827, -123.1207),
    "toronto": (43.6532, -79.3832),
    "edmonton": (53.5461, -113.4938),
    "seattle": (47.6062, -122.3321),
    "portland": (45.5152, -122.6784),
    "dallas": (32.7767, -96.7970),
    "houston": (29.7604, -95.3698),
    "miami": (25.7617, -80.1918),
    "denver": (39.7392, -104.9903),
    "chicago": (41.8781, -87.6298),
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "phoenix": (33.4484, -112.0740),
    "philadelphia": (39.9526, -75.1652),
    "san antonio": (29.4241, -98.4936),
    "san diego": (32.7157, -117.1611),
    "austin": (30.2672, -97.7431),
    "jacksonville": (30.3322, -81.6557),
    "san jose": (37.3382, -121.8863),
}


def generate_grid(city: str, state: str, radius_km: float = 10.0) -> list[dict]:
    """Generate search grid points for a city."""
    city_key = city.lower().strip()
    
    # Try exact match first
    if city_key in CITY_COORDS:
        center_lat, center_lng = CITY_COORDS[city_key]
    else:
        # Try to find partial match
        for key, coords in CITY_COORDS.items():
            if key in city_key or city_key in key:
                center_lat, center_lng = coords
                break
        else:
            # Default to Calgary if unknown
            center_lat, center_lng = 51.0447, -114.0719
            logger.warning(f"Unknown city '{city}', defaulting to Calgary coordinates")
    
    # Generate grid
    # 0.01 degrees ≈ 1.1km at equator, less at higher latitudes
    step = 0.018  # ~2km grid
    radius_deg = radius_km / 111.0
    
    points = []
    steps = int(radius_deg / step)
    
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            lat = center_lat + (i * step)
            lng = center_lng + (j * step)
            points.append({"lat": lat, "lng": lng, "radius": 2000})
    
    logger.info(f"Generated {len(points)} grid points for {city}")
    return points


class MapsRPCScraper:
    """
    Fast Google Maps scraper using grid search + APP_INITIALIZATION_STATE parsing.
    """
    
    def __init__(self, config: dict, rate_limiter, proxy_manager=None):
        self.config = config
        self.rate_limiter = rate_limiter
        self.proxy_manager = proxy_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self._concurrency = min(config["scraping"].get("xhr_concurrency", 50), 50)
    
    def scrape_niche(self, niche: str, location: dict, on_progress: Callable = None) -> list[dict]:
        """Scrape leads using grid search."""
        return asyncio.run(self._scrape_async(niche, location, on_progress))
    
    async def _scrape_async(
        self,
        niche: str,
        location: dict,
        on_progress: Optional[Callable],
    ) -> list[dict]:
        """Async grid-based scraping."""
        city = location["city"]
        state = location.get("state", "")
        
        # Generate grid
        grid_points = generate_grid(city, state, radius_km=10.0)
        
        self.logger.info(
            f"MapsRPC: '{niche}' in {city} - {len(grid_points)} grid points, "
            f"concurrency={self._concurrency}"
        )
        
        # Fetch all grid points
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(12.0, connect=5.0),
            follow_redirects=True,
            http2=True,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
        ) as client:
            sem = asyncio.Semaphore(self._concurrency)
            
            progress = {"done": 0, "total": len(grid_points)}
            tasks = [
                self._fetch_grid_point(client, niche, point, sem, progress, on_progress)
                for point in grid_points
            ]
            
            results = await asyncio.gather(*tasks)
        
        # Deduplicate
        all_leads = []
        seen_ids = set()
        
        for point_leads in results:
            for lead in point_leads:
                # Create unique key
                key = lead.get("place_id", "")
                if not key:
                    key = f"{lead.get('name', '')}_{lead.get('lat', '')}_{lead.get('lng', '')}"
                
                if key and key not in seen_ids:
                    seen_ids.add(key)
                    all_leads.append(lead)
        
        self.logger.info(
            f"MapsRPC: {len(all_leads)} unique leads for '{niche}' in {city}"
        )
        return all_leads
    
    async def _fetch_grid_point(
        self,
        client: httpx.AsyncClient,
        niche: str,
        point: dict,
        sem: asyncio.Semaphore,
        progress: dict,
        on_progress: Optional[Callable],
    ) -> list[dict]:
        """Fetch businesses from a single grid point."""
        async with sem:
            # Build search query with location bias
            query = f"{niche} near {point['lat']:.6f},{point['lng']:.6f}"
            url = f"https://www.google.com/maps/search/{quote_plus(query)}"
            
            headers = self._get_headers()
            
            for attempt in range(2):
                try:
                    resp = await client.get(url, headers=headers, follow_redirects=True)
                    
                    if resp.status_code == 200:
                        leads = self._parse_response(resp.text)
                        
                        progress["done"] += 1
                        if on_progress:
                            try:
                                on_progress(progress["done"], progress["total"])
                            except Exception:
                                pass
                        
                        return leads
                    
                    elif resp.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                        
                except Exception as exc:
                    if attempt < 1:
                        await asyncio.sleep(1)
                    continue
            
            progress["done"] += 1
            return []
    
    def _get_headers(self) -> dict:
        """Get request headers."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ]
        
        return {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive",
        }
    
    def _parse_response(self, html: str) -> list[dict]:
        """Extract business data from Maps response."""
        leads = []
        
        # Extract from APP_INITIALIZATION_STATE
        app_state_leads = self._parse_app_state(html)
        leads.extend(app_state_leads)
        
        # If no leads found, try other methods
        if not leads:
            # Try to extract from any business-like patterns
            leads.extend(self._extract_business_patterns(html))
        
        return leads
    
    def _parse_app_state(self, html: str) -> list[dict]:
        """Parse APP_INITIALIZATION_STATE for business data."""
        leads = []
        
        # Find the state
        patterns = [
            r'window\.APP_INITIALIZATION_STATE\s*=\s*(\[.+?\]);</script>',
            r'APP_INITIALIZATION_STATE\s*=\s*(\[.+?\]);',
        ]
        
        json_str = None
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                json_str = match.group(1)
                break
        
        if not json_str:
            return leads
        
        try:
            # The state is a deeply nested array
            # Look for strings that look like business names
            # They're typically in double quotes within the array
            
            # Pattern 1: Look for ["Business Name", rating, ...]
            biz_pattern1 = r'\[\s*"([^"]{3,60}[^"])"\s*,\s*([\d.]+|null)\s*,\s*"([^"]*)"'
            matches1 = re.findall(biz_pattern1, json_str)
            
            for match in matches1:
                name = match[0].strip()
                # Filter out non-business strings
                if self._is_valid_business_name(name):
                    lead = {
                        "name": name,
                        "rating": match[1] if match[1] != 'null' else "",
                        "source": "Google Maps",
                        "gmb_link": "",
                        "niche": "",
                    }
                    leads.append(lead)
            
            # Pattern 2: Look for data with place IDs
            # Format often includes: 0xHEX:0xHEX which is a place ID
            place_pattern = r'0x[0-9a-fA-F]+:0x[0-9a-fA-F]+'
            place_ids = re.findall(place_pattern, json_str)
            
            # Pattern 3: Extract phone numbers
            phone_pattern = r'"(\+?\d[\d\s\-\(\)]{8,20})"'
            phones = re.findall(phone_pattern, json_str)
            
            # Try to associate phones with businesses
            for i, lead in enumerate(leads):
                if i < len(phones):
                    lead["phone"] = phones[i]
            
        except Exception as exc:
            self.logger.debug(f"APP_INITIALIZATION_STATE parse error: {exc}")
        
        return leads
    
    def _extract_business_patterns(self, html: str) -> list[dict]:
        """Extract businesses using various patterns."""
        leads = []
        
        # Look for common business name patterns
        # Many Google Maps responses contain arrays like:
        # ["Business Name", 4.5, "123 Main St", ...]
        
        pattern = r'\[\s*"([A-Z][^"]{2,50}?(?:\s+(?:&amp;|and|&|\\+|[A-Z])[^"]*)?)"\s*,\s*([\d.]+)'
        matches = re.findall(pattern, html)
        
        for match in matches:
            name = match[0].replace('&amp;', '&').replace('\\u0026', '&')
            if self._is_valid_business_name(name):
                leads.append({
                    "name": name,
                    "rating": match[1],
                    "source": "Google Maps",
                    "gmb_link": "",
                    "niche": "",
                })
        
        return leads
    
    def _is_valid_business_name(self, name: str) -> bool:
        """Check if a string looks like a valid business name."""
        if not name or len(name) < 3 or len(name) > 60:
            return False
        
        # Must contain letters
        if not any(c.isalpha() for c in name):
            return False
        
        # Filter out common non-business strings
        invalid_patterns = [
            r'^0x[0-9a-fA-F]+$',  # Hex codes
            r'^https?://',  # URLs
            r'^[\d\s\-\(\)\.]+$',  # Just numbers/punctuation
            r'^null$|^undefined$|^true$|^false$',
            r'^function\s*\(',  # JavaScript
        ]
        
        for pattern in invalid_patterns:
            if re.match(pattern, name, re.IGNORECASE):
                return False
        
        return True
