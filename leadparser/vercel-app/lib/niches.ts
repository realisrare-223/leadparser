// ============================================================
// Preset niche list for the scraper / assign comboboxes.
// The user can also type any custom niche not in this list.
// ============================================================

export const PRESET_NICHES: string[] = [
  // Home Services
  'Plumbers',
  'Electricians',
  'HVAC',
  'Roofers',
  'Painters',
  'Landscapers',
  'Lawn Care',
  'Tree Services',
  'Fencing Contractors',
  'Deck Builders',
  'Pool Contractors',
  'Garage Door Repair',
  'Window Installation',
  'Siding Contractors',
  'Gutters',
  'Pressure Washing',
  'House Cleaners',
  'Carpet Cleaners',
  'Junk Removal',
  'Moving Companies',
  'Storage Units',

  // Construction & Remodeling
  'General Contractors',
  'Home Remodelers',
  'Kitchen Remodelers',
  'Bathroom Remodelers',
  'Flooring Contractors',
  'Tile Contractors',
  'Concrete Contractors',
  'Foundation Repair',
  'Masonry',
  'Insulation Contractors',
  'Drywall Contractors',

  // Auto
  'Auto Repair Shops',
  'Auto Body Shops',
  'Car Dealerships',
  'Auto Detailing',
  'Tire Shops',
  'Oil Change Shops',
  'Towing Services',
  'Auto Glass Repair',

  // Health & Wellness
  'Dentists',
  'Chiropractors',
  'Physical Therapists',
  'Optometrists',
  'Veterinarians',
  'Medical Clinics',
  'Mental Health Counselors',
  'Massage Therapists',
  'Gyms',
  'Personal Trainers',

  // Professional Services
  'Accountants',
  'Bookkeepers',
  'Tax Preparers',
  'Lawyers',
  'Insurance Agents',
  'Financial Advisors',
  'Real Estate Agents',
  'Mortgage Brokers',
  'IT Support',
  'Marketing Agencies',

  // Restaurants & Food
  'Restaurants',
  'Pizza Restaurants',
  'Catering Services',
  'Food Trucks',

  // Beauty & Personal Care
  'Hair Salons',
  'Barbershops',
  'Nail Salons',
  'Tattoo Parlors',
  'Spas',

  // Education & Childcare
  'Tutoring Services',
  'Daycares',
  'Preschools',
  'Martial Arts Schools',
  'Dance Studios',
  'Music Schools',

  // Other
  'Pest Control',
  'Security Companies',
  'Photographers',
  'Wedding Planners',
  'Event Venues',
  'Funeral Homes',
  'Churches',
  'Locksmiths',
  'Solar Installers',
  'EV Charger Installation',
]

/**
 * Filter niches by free-text query.
 * Returns preset matches first, then allows custom input.
 */
export function searchNiches(query: string, extraNiches: string[] = []): string[] {
  const q = query.toLowerCase().trim()
  if (!q) {
    // Merge preset + any custom niches from the DB, deduplicated
    const all = [...PRESET_NICHES]
    for (const n of extraNiches) {
      if (!all.some(p => p.toLowerCase() === n.toLowerCase())) all.push(n)
    }
    return all
  }

  const all = [...PRESET_NICHES]
  for (const n of extraNiches) {
    if (!all.some(p => p.toLowerCase() === n.toLowerCase())) all.push(n)
  }

  return all
    .filter(n => n.toLowerCase().includes(q))
    .sort((a, b) => {
      // Starts-with gets priority
      const aStarts = a.toLowerCase().startsWith(q) ? 0 : 1
      const bStarts = b.toLowerCase().startsWith(q) ? 0 : 1
      return aStarts - bStarts || a.localeCompare(b)
    })
}
