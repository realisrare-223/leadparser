// ============================================================
// Shared TypeScript types for the LeadParser dashboard
// ============================================================

export type LeadStatus = 'new' | 'called' | 'sold' | 'followup' | 'dead'

export interface Lead {
  id: string
  dedup_key: string
  niche: string
  name: string
  phone: string
  secondary_phone: string
  address: string
  city: string
  state: string
  zip_code: string
  hours: string
  review_count: number
  rating: string
  gmb_link: string
  website: string
  facebook: string
  instagram: string
  data_source: string
  lead_score: number
  pitch_notes: string
  additional_notes: string
  // CRM fields
  status: LeadStatus
  assigned_to: string | null
  assigned_at: string | null
  call_status: string
  follow_up_date: string | null
  caller_notes: string
  // Timestamps
  date_added: string
  created_at: string
  updated_at: string
}

export interface Caller {
  id: string
  name: string
  role: 'caller' | 'admin'
  created_at: string
}

export interface LeadStats {
  total: number
  new_count: number
  assigned: number
  called: number
  sold: number
  followup: number
  dead: number
  hot: number
  warm: number
  conversion_pct: number | null
}

export interface CallerStats {
  id: string
  name: string
  role: string
  total_assigned: number
  called: number
  sold: number
  followup: number
  untouched: number
  conversion_pct: number | null
}

export type JobStatus = 'pending' | 'running' | 'done' | 'failed'

export interface ScraperJob {
  id: string
  city: string
  state: string
  niche: string
  limit_count: number
  status: JobStatus
  result_count: number
  error_msg: string
  created_at: string
  started_at: string | null
  finished_at: string | null
}
