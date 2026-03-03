import { NextResponse } from 'next/server'

// Scraping is handled by the Python CLI on your local machine.
// Run: python main.py --city "Dallas" --state TX --niche "plumbers" --limit 100
export async function POST() {
  return NextResponse.json({
    error: 'Scraping runs locally via the Python CLI. See leadparser/main.py.',
  }, { status: 400 })
}
