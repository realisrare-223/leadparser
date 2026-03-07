# LeadParser Test Suite

All tests for the LeadParser SaaS platform live here.

## Structure

```
tests/
├── python/                         # Python scraper + utility tests
│   ├── conftest.py                 # Shared fixtures (sys.path, sample data)
│   ├── unit/                       # Pure unit tests — no I/O, no DB
│   │   ├── test_lead_scorer.py
│   │   ├── test_phone_validator.py
│   │   ├── test_address_parser.py
│   │   ├── test_pitch_engine.py
│   │   ├── test_sentiment_analyzer.py
│   │   ├── test_email_extractor.py  # Phase 4
│   │   └── test_captcha_detector.py # Phase 4
│   └── integration/                # Mocked Supabase + pipeline tests
│       ├── test_supabase_handler.py
│       ├── test_pipeline.py
│       └── test_google_maps_multiquery.py  # Phase 4
├── nextjs/                         # Next.js API + component tests
│   ├── setup.ts                    # Vitest global setup
│   ├── api/
│   │   ├── leads.test.ts
│   │   ├── admin.test.ts
│   │   └── scrape.test.ts
│   └── components/
│       ├── LeadTable.test.tsx
│       └── LandingPage.test.tsx    # Phase 5
└── phase_checks/                   # Phase completion verification scripts
    ├── check_phase_1.sh
    ├── check_phase_2.sh
    ├── check_phase_3.sh
    ├── check_phase_4.sh
    └── check_phase_5.sh
```

## Running Tests

### Python (from project root)
```bash
python -m pytest tests/python/ -v --tb=short
# With coverage:
python -m pytest tests/python/ -v --cov=leadparser --cov-report=term-missing
```

### Next.js (from vercel-app/)
```bash
cd vercel-app
npm test -- --run
```

### Phase Completion Checks
```bash
bash tests/phase_checks/check_phase_1.sh
bash tests/phase_checks/check_phase_2.sh
# etc.
```

## Dependencies

### Python
- `pytest>=8.0`
- `pytest-cov>=5.0`
- `pytest-mock>=3.12`

### Next.js
- `vitest`
- `@testing-library/react`
- `@testing-library/jest-dom`
- `jsdom`
- `@vitejs/plugin-react`
