// ============================================================
// Niche list for the scraper / assign comboboxes.
//
// Structure
// ---------
// • "General" entries (e.g. "Food (General)") send a broad keyword
//   to the scraper.  The Python NICHE_EXPANSIONS map then searches
//   every sub-category automatically (restaurants → cafes → pizza…).
//   Use these when you want maximum coverage in one job.
//
// • Specific entries (e.g. "Restaurants") target exactly that niche
//   plus its own keyword variants.  Use these for focused campaigns.
//
// The `value` field is lowercased to match NICHE_EXPANSIONS keys in
// google_maps.py.  The `label` is what displays in the dropdown.
// The `sublabel` shows a hint of what the scraper will search.
// The `group` drives the grouped section headers in the combobox.
// ============================================================

import type { ComboOption } from '@/components/Combobox'

export const NICHE_COMBO_OPTIONS: ComboOption[] = [

  // ── General / broad categories ────────────────────────────────────────────
  // Selecting one of these makes the scraper search ALL sub-niches within
  // that category, maximising lead volume in a single run.

  {
    value:    'food',
    label:    'Food (General)',
    sublabel: 'restaurants, cafes, pizza, bakeries, bars, fast food…',
    group:    'General Categories',
  },
  {
    value:    'home services',
    label:    'Home Services (General)',
    sublabel: 'plumbers, electricians, HVAC, roofing, cleaning…',
    group:    'General Categories',
  },
  {
    value:    'medical',
    label:    'Medical (General)',
    sublabel: 'dentists, clinics, chiropractors, pharmacies, optometrists…',
    group:    'General Categories',
  },
  {
    value:    'beauty',
    label:    'Beauty & Wellness (General)',
    sublabel: 'hair salons, nail salons, spas, gyms, massage…',
    group:    'General Categories',
  },
  {
    value:    'automotive',
    label:    'Automotive (General)',
    sublabel: 'auto repair, detailing, body shops, tire shops, car wash…',
    group:    'General Categories',
  },
  {
    value:    'professional services',
    label:    'Professional Services (General)',
    sublabel: 'lawyers, accountants, real estate, marketing agencies…',
    group:    'General Categories',
  },

  // ── Food & Beverage ───────────────────────────────────────────────────────

  { value: 'restaurants',   label: 'Restaurants',    group: 'Food & Beverage' },
  { value: 'cafes',         label: 'Cafes',          sublabel: 'coffee shops, espresso bars, tea houses', group: 'Food & Beverage' },
  { value: 'coffee shops',  label: 'Coffee Shops',   group: 'Food & Beverage' },
  { value: 'pizzerias',     label: 'Pizzerias',      group: 'Food & Beverage' },
  { value: 'bakeries',      label: 'Bakeries',       sublabel: 'custom cakes, pastries, dessert shops', group: 'Food & Beverage' },
  { value: 'bars',          label: 'Bars',           sublabel: 'pubs, cocktail lounges, craft breweries', group: 'Food & Beverage' },
  { value: 'fast food',     label: 'Fast Food',      sublabel: 'quick service, takeout, drive-thru', group: 'Food & Beverage' },
  { value: 'catering services', label: 'Catering Services', group: 'Food & Beverage' },
  { value: 'food trucks',   label: 'Food Trucks',    group: 'Food & Beverage' },

  // ── Home & Trade Services ─────────────────────────────────────────────────

  { value: 'plumbers',             label: 'Plumbers',            group: 'Home & Trade Services' },
  { value: 'electricians',         label: 'Electricians',        group: 'Home & Trade Services' },
  { value: 'hvac contractors',     label: 'HVAC Contractors',    sublabel: 'heating, cooling, furnace, AC', group: 'Home & Trade Services' },
  { value: 'roofing contractors',  label: 'Roofing Contractors', group: 'Home & Trade Services' },
  { value: 'painters',             label: 'Painters',            group: 'Home & Trade Services' },
  { value: 'landscaping services', label: 'Landscapers',         sublabel: 'lawn care, yard maintenance', group: 'Home & Trade Services' },
  { value: 'tree services',        label: 'Tree Services',       sublabel: 'arborists, tree removal, trimming', group: 'Home & Trade Services' },
  { value: 'cleaning services',    label: 'Cleaning Services',   sublabel: 'house cleaning, maid service, commercial', group: 'Home & Trade Services' },
  { value: 'pest control',         label: 'Pest Control',        sublabel: 'exterminator, rodent, termite', group: 'Home & Trade Services' },
  { value: 'locksmiths',           label: 'Locksmiths',          group: 'Home & Trade Services' },
  { value: 'moving companies',     label: 'Moving Companies',    group: 'Home & Trade Services' },
  { value: 'water damage restoration', label: 'Water Damage Restoration', sublabel: 'flood, mold remediation', group: 'Home & Trade Services' },
  { value: 'towing services',      label: 'Towing Services',     sublabel: 'roadside assistance, flatbed', group: 'Home & Trade Services' },
  { value: 'fencing contractors',  label: 'Fencing Contractors', group: 'Home & Trade Services' },
  { value: 'garage door repair',   label: 'Garage Door Repair',  group: 'Home & Trade Services' },
  { value: 'pressure washing',     label: 'Pressure Washing',    group: 'Home & Trade Services' },
  { value: 'junk removal',         label: 'Junk Removal',        group: 'Home & Trade Services' },
  { value: 'window installation',  label: 'Window Installation', group: 'Home & Trade Services' },
  { value: 'solar installers',     label: 'Solar Installers',    group: 'Home & Trade Services' },

  // ── Construction & Remodeling ─────────────────────────────────────────────

  { value: 'general contractors',   label: 'General Contractors',   group: 'Construction & Remodeling' },
  { value: 'home remodelers',       label: 'Home Remodelers',       group: 'Construction & Remodeling' },
  { value: 'kitchen remodelers',    label: 'Kitchen Remodelers',    group: 'Construction & Remodeling' },
  { value: 'bathroom remodelers',   label: 'Bathroom Remodelers',   group: 'Construction & Remodeling' },
  { value: 'flooring contractors',  label: 'Flooring Contractors',  group: 'Construction & Remodeling' },
  { value: 'concrete contractors',  label: 'Concrete Contractors',  group: 'Construction & Remodeling' },
  { value: 'foundation repair',     label: 'Foundation Repair',     group: 'Construction & Remodeling' },
  { value: 'drywall contractors',   label: 'Drywall Contractors',   group: 'Construction & Remodeling' },
  { value: 'insulation contractors', label: 'Insulation Contractors', group: 'Construction & Remodeling' },

  // ── Automotive ────────────────────────────────────────────────────────────

  { value: 'auto repair shops',   label: 'Auto Repair Shops',   sublabel: 'mechanic, oil change, brakes', group: 'Automotive' },
  { value: 'auto body shops',     label: 'Auto Body Shops',     sublabel: 'collision repair, dent removal', group: 'Automotive' },
  { value: 'auto detailing',      label: 'Auto Detailing',      sublabel: 'car wash, ceramic coating', group: 'Automotive' },
  { value: 'car wash',            label: 'Car Wash',            group: 'Automotive' },
  { value: 'tire shops',          label: 'Tire Shops',          sublabel: 'wheel alignment, winter tires', group: 'Automotive' },
  { value: 'auto glass repair',   label: 'Auto Glass Repair',   group: 'Automotive' },
  { value: 'car dealerships',     label: 'Car Dealerships',     group: 'Automotive' },

  // ── Medical & Healthcare ──────────────────────────────────────────────────

  { value: 'dentists',          label: 'Dentists',          sublabel: 'family, cosmetic, emergency dental', group: 'Medical & Healthcare' },
  { value: 'chiropractors',     label: 'Chiropractors',     sublabel: 'back pain, sports injury', group: 'Medical & Healthcare' },
  { value: 'clinics',           label: 'Medical Clinics',   sublabel: 'family doctor, urgent care, walk-in', group: 'Medical & Healthcare' },
  { value: 'urgent care',       label: 'Urgent Care',       group: 'Medical & Healthcare' },
  { value: 'physical therapy',  label: 'Physical Therapists', sublabel: 'physiotherapy, sports rehab', group: 'Medical & Healthcare' },
  { value: 'optometrists',      label: 'Optometrists',      sublabel: 'eye doctor, glasses, contacts', group: 'Medical & Healthcare' },
  { value: 'pharmacies',        label: 'Pharmacies',        sublabel: 'drugstore, prescription', group: 'Medical & Healthcare' },
  { value: 'veterinarians',     label: 'Veterinarians',     group: 'Medical & Healthcare' },
  { value: 'mental health counselors', label: 'Mental Health Counselors', group: 'Medical & Healthcare' },

  // ── Beauty & Wellness ─────────────────────────────────────────────────────

  { value: 'hair salons',    label: 'Hair Salons',    sublabel: 'colour, balayage, bridal styling', group: 'Beauty & Wellness' },
  { value: 'barber shops',   label: 'Barbershops',    sublabel: 'fade, beard trim, men\'s grooming', group: 'Beauty & Wellness' },
  { value: 'nail salons',    label: 'Nail Salons',    sublabel: 'acrylic, gel, dip powder', group: 'Beauty & Wellness' },
  { value: 'spas',           label: 'Spas',           sublabel: 'day spa, facial, body wrap', group: 'Beauty & Wellness' },
  { value: 'massage therapy', label: 'Massage Therapy', sublabel: 'deep tissue, sports, RMT', group: 'Beauty & Wellness' },
  { value: 'gyms',           label: 'Gyms',           sublabel: 'fitness clubs, 24-hour gym', group: 'Beauty & Wellness' },
  { value: 'yoga studios',   label: 'Yoga Studios',   sublabel: 'pilates, hot yoga, meditation', group: 'Beauty & Wellness' },
  { value: 'personal trainers', label: 'Personal Trainers', group: 'Beauty & Wellness' },
  { value: 'tattoo parlors', label: 'Tattoo Parlors', group: 'Beauty & Wellness' },
  { value: 'pet grooming',   label: 'Pet Grooming',   sublabel: 'dog grooming, mobile grooming', group: 'Beauty & Wellness' },

  // ── Professional Services ─────────────────────────────────────────────────

  { value: 'lawyers',           label: 'Lawyers / Attorneys',  sublabel: 'personal injury, family law, criminal', group: 'Professional Services' },
  { value: 'accountants',       label: 'Accountants / CPAs',   sublabel: 'tax prep, bookkeeping, payroll', group: 'Professional Services' },
  { value: 'real estate agents', label: 'Real Estate Agents',  sublabel: 'realtors, buyers/sellers agents', group: 'Professional Services' },
  { value: 'marketing agencies', label: 'Marketing Agencies',  sublabel: 'SEO, web design, social media', group: 'Professional Services' },
  { value: 'insurance agents',  label: 'Insurance Agents',     group: 'Professional Services' },
  { value: 'financial advisors', label: 'Financial Advisors',  group: 'Professional Services' },
  { value: 'mortgage brokers',  label: 'Mortgage Brokers',     group: 'Professional Services' },
  { value: 'it support',        label: 'IT Support',           group: 'Professional Services' },
  { value: 'web design',        label: 'Web Design',           sublabel: 'website developers, digital marketing', group: 'Professional Services' },
  { value: 'photographers',     label: 'Photographers',        sublabel: 'wedding, portrait, commercial', group: 'Professional Services' },

  // ── Retail & Shopping ─────────────────────────────────────────────────────

  { value: 'florists',          label: 'Florists',            sublabel: 'flower delivery, wedding flowers', group: 'Retail & Shopping' },
  { value: 'electronics repair', label: 'Electronics Repair', sublabel: 'phone repair, laptop, screen replacement', group: 'Retail & Shopping' },
  { value: 'furniture stores',  label: 'Furniture Stores',    group: 'Retail & Shopping' },
  { value: 'clothing stores',   label: 'Clothing Stores',     sublabel: 'boutiques, thrift, formal wear', group: 'Retail & Shopping' },

  // ── Education & Childcare ─────────────────────────────────────────────────

  { value: 'tutoring services', label: 'Tutoring Services',  group: 'Education & Childcare' },
  { value: 'daycares',          label: 'Daycares',           group: 'Education & Childcare' },
  { value: 'preschools',        label: 'Preschools',         group: 'Education & Childcare' },
  { value: 'martial arts schools', label: 'Martial Arts Schools', group: 'Education & Childcare' },
  { value: 'dance studios',     label: 'Dance Studios',      group: 'Education & Childcare' },
  { value: 'music schools',     label: 'Music Schools',      group: 'Education & Childcare' },

  // ── Hospitality & Events ──────────────────────────────────────────────────

  { value: 'hotels',           label: 'Hotels',              sublabel: 'boutique hotels, B&Bs, motels', group: 'Hospitality & Events' },
  { value: 'event venues',     label: 'Event Venues',        sublabel: 'banquet halls, corporate, outdoor', group: 'Hospitality & Events' },
  { value: 'wedding venues',   label: 'Wedding Venues',      group: 'Hospitality & Events' },
  { value: 'wedding planners', label: 'Wedding Planners',    group: 'Hospitality & Events' },
  { value: 'travel agencies',  label: 'Travel Agencies',     group: 'Hospitality & Events' },

  // ── Other ─────────────────────────────────────────────────────────────────

  { value: 'security companies', label: 'Security Companies', group: 'Other' },
  { value: 'funeral homes',      label: 'Funeral Homes',      group: 'Other' },
  { value: 'churches',           label: 'Churches',           group: 'Other' },
  { value: 'solar installers',   label: 'Solar Installers',   group: 'Other' },
  { value: 'ev charger installation', label: 'EV Charger Installation', group: 'Other' },
  { value: 'storage units',      label: 'Storage Units',      group: 'Other' },
]

// Legacy flat list — kept so any code still importing PRESET_NICHES doesn't break
export const PRESET_NICHES: string[] = NICHE_COMBO_OPTIONS.map(o => o.label)
