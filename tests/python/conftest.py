"""
conftest.py — pytest fixtures shared across all Python tests.

Adds the leadparser/ package root to sys.path so imports work
without installing the package. Provides shared sample data fixtures.
"""
import sys
from pathlib import Path

# Add leadparser/ directory to sys.path so we can import scrapers/, utils/, etc.
LEADPARSER_ROOT = Path(__file__).parent.parent.parent / "leadparser"
sys.path.insert(0, str(LEADPARSER_ROOT))

import pytest


@pytest.fixture
def sample_config():
    """Minimal config dict for unit testing utility classes."""
    return {
        "location": {
            "city": "Dallas",
            "state": "TX",
            "full_address": "Dallas, TX",
        },
        "niches": ["plumbers"],
        "filters": {
            "min_reviews": 0,
            "max_reviews": 9999,
            "min_rating": 0.0,
            "max_rating": 5.0,
            "exclude_with_website": False,
            "min_lead_score": 0,
        },
        "scoring": {
            "no_reviews_score": 10,
            "very_few_reviews": 2,
            "few_reviews": 5,
            "moderate_reviews": 10,
            "many_reviews": 13,
            "lots_of_reviews": 15,
            "no_website_base_bonus": 3,
            "rich_no_website_bonus": 7,
            "very_low_rating_bonus": 5,
            "low_rating_bonus": 3,
            "medium_rating_bonus": 1,
            "high_value_niche_bonus": 5,
            "complete_contact_bonus": 2,
        },
        "high_value_niches": ["plumbers", "electricians", "hvac", "roofers"],
        "pitch_templates": {
            "default": "Hi {name}, I help businesses in {city} get more clients.",
            "plumbers": "Hi {name}, I help plumbers in {city} get more service calls.",
            "restaurants": "Hi {name}, are you looking to bring more diners into {name} in {city}?",
        },
        "proxies": {"enabled": False},
        "scraping": {
            "max_results_per_niche": 100,
            "delay_min": 0.1,
            "delay_max": 0.2,
            "max_retries": 3,
            "headless": True,
        },
        "logging": {"level": "INFO", "log_dir": "logs"},
    }


@pytest.fixture
def sample_raw_lead():
    """Raw lead dict as returned by GoogleMapsScraper._extract_business()."""
    return {
        "source": "Google Maps",
        "niche": "plumbers",
        "name": "Joe's Plumbing",
        "phone": "(214) 555-0123",
        "secondary_phone": "",
        "address": "123 Main St, Dallas, TX 75201",
        "city": "Dallas",
        "state": "TX",
        "zip": "75201",
        "hours": "Mon-Fri 8am-6pm",
        "review_count": 45,
        "rating": "3.8",
        "website": "",
        "facebook": "https://facebook.com/joesplumbing",
        "instagram": "",
        "gmb_link": "https://maps.google.com/?cid=123456",
        "category": "Plumber",
        "notes": "",
        "email": "",
    }


@pytest.fixture
def sample_raw_lead_no_phone():
    """Raw lead missing a phone number."""
    return {
        "source": "Google Maps",
        "niche": "plumbers",
        "name": "No Phone Plumbing Co",
        "phone": "",
        "secondary_phone": "",
        "address": "456 Oak Ave, Austin, TX 78701",
        "city": "Austin",
        "state": "TX",
        "zip": "78701",
        "hours": "",
        "review_count": 12,
        "rating": "4.2",
        "website": "https://nophoneplumbing.com",
        "facebook": "",
        "instagram": "",
        "gmb_link": "https://maps.google.com/?cid=789",
        "category": "Plumber",
        "notes": "Phone Number Needed — not found on Google Maps",
        "email": "",
    }


@pytest.fixture
def sample_raw_lead_canadian():
    """Raw lead from a Canadian city."""
    return {
        "source": "Google Maps",
        "niche": "hvac",
        "name": "Calgary HVAC Pro",
        "phone": "(403) 555-0199",
        "secondary_phone": "",
        "address": "789 Macleod Trail SE, Calgary, AB T2G 2L7",
        "city": "Calgary",
        "state": "AB",
        "zip": "T2G 2L7",
        "hours": "Mon-Fri 7am-5pm",
        "review_count": 0,
        "rating": "4.0",
        "website": "",
        "facebook": "",
        "instagram": "",
        "gmb_link": "https://maps.google.com/?cid=999",
        "category": "HVAC Contractor",
        "notes": "",
        "email": "",
    }
