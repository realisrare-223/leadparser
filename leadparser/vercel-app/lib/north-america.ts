// ============================================================
// North America regions — US states, Canadian provinces,
// and Mexican states — with abbreviations and aliases.
// Used for the state/province autocomplete in the scraper.
// ============================================================

export interface NARegion {
  name: string        // canonical display name, e.g. "Texas"
  abbr: string        // official abbreviation, e.g. "TX"
  country: 'US' | 'CA' | 'MX'
  countryLabel: string // "USA" | "Canada" | "Mexico"
}

// All searches are lowercased against name, abbr, and countryLabel
export const NA_REGIONS: NARegion[] = [
  // ── United States ──────────────────────────────────────────
  { name: 'Alabama',              abbr: 'AL', country: 'US', countryLabel: 'USA' },
  { name: 'Alaska',               abbr: 'AK', country: 'US', countryLabel: 'USA' },
  { name: 'Arizona',              abbr: 'AZ', country: 'US', countryLabel: 'USA' },
  { name: 'Arkansas',             abbr: 'AR', country: 'US', countryLabel: 'USA' },
  { name: 'California',           abbr: 'CA', country: 'US', countryLabel: 'USA' },
  { name: 'Colorado',             abbr: 'CO', country: 'US', countryLabel: 'USA' },
  { name: 'Connecticut',          abbr: 'CT', country: 'US', countryLabel: 'USA' },
  { name: 'Delaware',             abbr: 'DE', country: 'US', countryLabel: 'USA' },
  { name: 'Florida',              abbr: 'FL', country: 'US', countryLabel: 'USA' },
  { name: 'Georgia',              abbr: 'GA', country: 'US', countryLabel: 'USA' },
  { name: 'Hawaii',               abbr: 'HI', country: 'US', countryLabel: 'USA' },
  { name: 'Idaho',                abbr: 'ID', country: 'US', countryLabel: 'USA' },
  { name: 'Illinois',             abbr: 'IL', country: 'US', countryLabel: 'USA' },
  { name: 'Indiana',              abbr: 'IN', country: 'US', countryLabel: 'USA' },
  { name: 'Iowa',                 abbr: 'IA', country: 'US', countryLabel: 'USA' },
  { name: 'Kansas',               abbr: 'KS', country: 'US', countryLabel: 'USA' },
  { name: 'Kentucky',             abbr: 'KY', country: 'US', countryLabel: 'USA' },
  { name: 'Louisiana',            abbr: 'LA', country: 'US', countryLabel: 'USA' },
  { name: 'Maine',                abbr: 'ME', country: 'US', countryLabel: 'USA' },
  { name: 'Maryland',             abbr: 'MD', country: 'US', countryLabel: 'USA' },
  { name: 'Massachusetts',        abbr: 'MA', country: 'US', countryLabel: 'USA' },
  { name: 'Michigan',             abbr: 'MI', country: 'US', countryLabel: 'USA' },
  { name: 'Minnesota',            abbr: 'MN', country: 'US', countryLabel: 'USA' },
  { name: 'Mississippi',          abbr: 'MS', country: 'US', countryLabel: 'USA' },
  { name: 'Missouri',             abbr: 'MO', country: 'US', countryLabel: 'USA' },
  { name: 'Montana',              abbr: 'MT', country: 'US', countryLabel: 'USA' },
  { name: 'Nebraska',             abbr: 'NE', country: 'US', countryLabel: 'USA' },
  { name: 'Nevada',               abbr: 'NV', country: 'US', countryLabel: 'USA' },
  { name: 'New Hampshire',        abbr: 'NH', country: 'US', countryLabel: 'USA' },
  { name: 'New Jersey',           abbr: 'NJ', country: 'US', countryLabel: 'USA' },
  { name: 'New Mexico',           abbr: 'NM', country: 'US', countryLabel: 'USA' },
  { name: 'New York',             abbr: 'NY', country: 'US', countryLabel: 'USA' },
  { name: 'North Carolina',       abbr: 'NC', country: 'US', countryLabel: 'USA' },
  { name: 'North Dakota',         abbr: 'ND', country: 'US', countryLabel: 'USA' },
  { name: 'Ohio',                 abbr: 'OH', country: 'US', countryLabel: 'USA' },
  { name: 'Oklahoma',             abbr: 'OK', country: 'US', countryLabel: 'USA' },
  { name: 'Oregon',               abbr: 'OR', country: 'US', countryLabel: 'USA' },
  { name: 'Pennsylvania',         abbr: 'PA', country: 'US', countryLabel: 'USA' },
  { name: 'Rhode Island',         abbr: 'RI', country: 'US', countryLabel: 'USA' },
  { name: 'South Carolina',       abbr: 'SC', country: 'US', countryLabel: 'USA' },
  { name: 'South Dakota',         abbr: 'SD', country: 'US', countryLabel: 'USA' },
  { name: 'Tennessee',            abbr: 'TN', country: 'US', countryLabel: 'USA' },
  { name: 'Texas',                abbr: 'TX', country: 'US', countryLabel: 'USA' },
  { name: 'Utah',                 abbr: 'UT', country: 'US', countryLabel: 'USA' },
  { name: 'Vermont',              abbr: 'VT', country: 'US', countryLabel: 'USA' },
  { name: 'Virginia',             abbr: 'VA', country: 'US', countryLabel: 'USA' },
  { name: 'Washington',           abbr: 'WA', country: 'US', countryLabel: 'USA' },
  { name: 'West Virginia',        abbr: 'WV', country: 'US', countryLabel: 'USA' },
  { name: 'Wisconsin',            abbr: 'WI', country: 'US', countryLabel: 'USA' },
  { name: 'Wyoming',              abbr: 'WY', country: 'US', countryLabel: 'USA' },
  { name: 'Washington DC',        abbr: 'DC', country: 'US', countryLabel: 'USA' },
  { name: 'Puerto Rico',          abbr: 'PR', country: 'US', countryLabel: 'USA' },

  // ── Canada ────────────────────────────────────────────────
  { name: 'Alberta',              abbr: 'AB', country: 'CA', countryLabel: 'Canada' },
  { name: 'British Columbia',     abbr: 'BC', country: 'CA', countryLabel: 'Canada' },
  { name: 'Manitoba',             abbr: 'MB', country: 'CA', countryLabel: 'Canada' },
  { name: 'New Brunswick',        abbr: 'NB', country: 'CA', countryLabel: 'Canada' },
  { name: 'Newfoundland',         abbr: 'NL', country: 'CA', countryLabel: 'Canada' },
  { name: 'Northwest Territories',abbr: 'NT', country: 'CA', countryLabel: 'Canada' },
  { name: 'Nova Scotia',          abbr: 'NS', country: 'CA', countryLabel: 'Canada' },
  { name: 'Nunavut',              abbr: 'NU', country: 'CA', countryLabel: 'Canada' },
  { name: 'Ontario',              abbr: 'ON', country: 'CA', countryLabel: 'Canada' },
  { name: 'Prince Edward Island', abbr: 'PE', country: 'CA', countryLabel: 'Canada' },
  { name: 'Quebec',               abbr: 'QC', country: 'CA', countryLabel: 'Canada' },
  { name: 'Saskatchewan',         abbr: 'SK', country: 'CA', countryLabel: 'Canada' },
  { name: 'Yukon',                abbr: 'YT', country: 'CA', countryLabel: 'Canada' },

  // ── Mexico ────────────────────────────────────────────────
  { name: 'Aguascalientes',       abbr: 'AG', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Baja California',      abbr: 'BC', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Baja California Sur',  abbr: 'BS', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Campeche',             abbr: 'CM', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Chiapas',              abbr: 'CS', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Chihuahua',            abbr: 'CH', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Ciudad de Mexico',     abbr: 'CDMX', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Coahuila',             abbr: 'CO', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Colima',               abbr: 'CL', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Durango',              abbr: 'DG', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Guanajuato',           abbr: 'GT', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Guerrero',             abbr: 'GR', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Hidalgo',              abbr: 'HG', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Jalisco',              abbr: 'JA', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Mexico State',         abbr: 'ME', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Michoacan',            abbr: 'MI', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Morelos',              abbr: 'MO', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Nayarit',              abbr: 'NA', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Nuevo Leon',           abbr: 'NL', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Oaxaca',               abbr: 'OA', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Puebla',               abbr: 'PU', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Queretaro',            abbr: 'QT', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Quintana Roo',         abbr: 'QR', country: 'MX', countryLabel: 'Mexico' },
  { name: 'San Luis Potosi',      abbr: 'SL', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Sinaloa',              abbr: 'SI', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Sonora',               abbr: 'SO', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Tabasco',              abbr: 'TB', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Tamaulipas',           abbr: 'TM', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Tlaxcala',             abbr: 'TL', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Veracruz',             abbr: 'VE', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Yucatan',              abbr: 'YU', country: 'MX', countryLabel: 'Mexico' },
  { name: 'Zacatecas',            abbr: 'ZA', country: 'MX', countryLabel: 'Mexico' },
]

// Group headers for display in the dropdown
export const COUNTRY_ORDER: NARegion['country'][] = ['US', 'CA', 'MX']
export const COUNTRY_LABELS: Record<NARegion['country'], string> = {
  US: '🇺🇸 United States',
  CA: '🇨🇦 Canada',
  MX: '🇲🇽 Mexico',
}

/**
 * Filter regions by a free-text query. Matches:
 *   - Abbreviation (exact, case-insensitive) — "TX" → Texas
 *   - Name prefix — "tex" → Texas
 *   - Name substring — "north" → North Carolina, North Dakota
 *   - Country label — "usa" → all US states
 */
export function searchRegions(query: string): NARegion[] {
  const q = query.toLowerCase().trim()
  if (!q) return NA_REGIONS

  return NA_REGIONS.filter(r => {
    const abbr    = r.abbr.toLowerCase()
    const name    = r.name.toLowerCase()
    const country = r.countryLabel.toLowerCase()

    // Exact abbreviation match gets top priority (handled by sort below)
    return (
      abbr  === q          ||
      abbr.startsWith(q)   ||
      name.startsWith(q)   ||
      name.includes(q)     ||
      country.includes(q)
    )
  }).sort((a, b) => {
    // Exact abbr match first, then name-starts-with, then anything
    const q2 = query.toLowerCase()
    const scoreA = a.abbr.toLowerCase() === q2 ? 0 : a.name.toLowerCase().startsWith(q2) ? 1 : 2
    const scoreB = b.abbr.toLowerCase() === q2 ? 0 : b.name.toLowerCase().startsWith(q2) ? 1 : 2
    return scoreA - scoreB || a.name.localeCompare(b.name)
  })
}

/** Given free text, return the best single match (for normalization on form submit). */
export function resolveRegion(query: string): NARegion | null {
  const q = query.toLowerCase().trim()
  if (!q) return null
  // 1. Exact abbreviation
  const byAbbr = NA_REGIONS.find(r => r.abbr.toLowerCase() === q)
  if (byAbbr) return byAbbr
  // 2. Exact name
  const byName = NA_REGIONS.find(r => r.name.toLowerCase() === q)
  if (byName) return byName
  // 3. First substring match
  return NA_REGIONS.find(r => r.name.toLowerCase().startsWith(q)) ?? null
}
