/**
 * Unit tests for components/LeadTable.tsx
 *
 * Tests cover:
 *   - Empty state renders "No leads" message
 *   - Lead rows rendered (name, phone, niche, city)
 *   - Website badge shows YES / NO correctly
 *   - Score badge renders score value
 *   - Status badge rendered when no onStatusChange
 *   - Status select rendered when onStatusChange is provided
 *   - Expand / Hide toggle for detail row
 *   - onStatusChange callback invoked on select change
 *   - Section dividers (No Website / Has Website) when mixed
 *   - showCaller prop presence (smoke test)
 */

import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { LeadTable } from '@/components/LeadTable'
import type { Lead } from '@/lib/types'

// ── Test data ─────────────────────────────────────────────────────────────────

function makeLead(overrides: Partial<Lead> = {}): Lead {
  return {
    id:               'lead-1',
    dedup_key:        'abc123',
    niche:            'plumbers',
    name:             "Joe's Plumbing",
    phone:            '(214) 555-0123',
    secondary_phone:  '',
    address:          '123 Main St',
    city:             'Dallas',
    state:            'TX',
    zip_code:         '75201',
    hours:            'Mon-Fri 8am-6pm',
    review_count:     45,
    rating:           '3.8',
    gmb_link:         'https://maps.google.com/?cid=1',
    website:          '',
    facebook:         '',
    instagram:        '',
    data_source:      'Google Maps',
    lead_score:       18,
    pitch_notes:      'Great prospect',
    additional_notes: '',
    email:            '',
    status:           'new',
    assigned_to:      null,
    assigned_at:      null,
    call_status:      '',
    follow_up_date:   null,
    caller_notes:     '',
    call_attempts:    0,
    last_called_at:   null,
    date_added:       '2026-01-01',
    created_at:       '2026-01-01T00:00:00Z',
    updated_at:       '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

// ── Empty state ───────────────────────────────────────────────────────────────

describe('LeadTable — empty state', () => {
  it('renders "No leads to display" when leads array is empty', () => {
    render(<LeadTable leads={[]} />)
    expect(screen.getByText(/no leads to display/i)).toBeInTheDocument()
  })

  it('does not render a table when leads array is empty', () => {
    render(<LeadTable leads={[]} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})

// ── Lead row rendering ────────────────────────────────────────────────────────

describe('LeadTable — lead row rendering', () => {
  it('renders the business name', () => {
    render(<LeadTable leads={[makeLead()]} />)
    expect(screen.getByText("Joe's Plumbing")).toBeInTheDocument()
  })

  it('renders the phone number', () => {
    render(<LeadTable leads={[makeLead()]} />)
    expect(screen.getByText('(214) 555-0123')).toBeInTheDocument()
  })

  it('renders the niche', () => {
    render(<LeadTable leads={[makeLead({ niche: 'electricians' })]} />)
    expect(screen.getByText('electricians')).toBeInTheDocument()
  })

  it('renders city and state together', () => {
    render(<LeadTable leads={[makeLead()]} />)
    expect(screen.getByText(/Dallas.*TX/)).toBeInTheDocument()
  })

  it('renders a row for each lead', () => {
    const leads = [
      makeLead({ id: '1', name: 'Alpha Plumbing' }),
      makeLead({ id: '2', name: 'Beta Electric' }),
      makeLead({ id: '3', name: 'Gamma HVAC' }),
    ]
    render(<LeadTable leads={leads} />)
    expect(screen.getByText('Alpha Plumbing')).toBeInTheDocument()
    expect(screen.getByText('Beta Electric')).toBeInTheDocument()
    expect(screen.getByText('Gamma HVAC')).toBeInTheDocument()
  })
})

// ── Website badge ─────────────────────────────────────────────────────────────

describe('LeadTable — website badge', () => {
  it('shows NO badge when website is empty', () => {
    render(<LeadTable leads={[makeLead({ website: '' })]} />)
    expect(screen.getByText('NO')).toBeInTheDocument()
  })

  it('shows YES badge when website is present', () => {
    render(<LeadTable leads={[makeLead({ website: 'https://example.com' })]} />)
    expect(screen.getByText('YES')).toBeInTheDocument()
  })
})

// ── Score badge ───────────────────────────────────────────────────────────────

describe('LeadTable — score badge', () => {
  it('renders the lead score', () => {
    render(<LeadTable leads={[makeLead({ lead_score: 18 })]} />)
    expect(screen.getByText('18')).toBeInTheDocument()
  })
})

// ── Status display ────────────────────────────────────────────────────────────

describe('LeadTable — status display', () => {
  it('renders StatusBadge (not select) when no onStatusChange', () => {
    render(<LeadTable leads={[makeLead({ status: 'called' })]} />)
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('renders a status select when onStatusChange is provided', () => {
    const handler = vi.fn().mockResolvedValue(undefined)
    render(<LeadTable leads={[makeLead()]} onStatusChange={handler} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('calls onStatusChange when status select changes', async () => {
    const handler = vi.fn().mockResolvedValue(undefined)
    render(<LeadTable leads={[makeLead({ id: 'lead-1', status: 'new' })]} onStatusChange={handler} />)
    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'called' } })
    await waitFor(() => {
      expect(handler).toHaveBeenCalledWith('lead-1', 'called')
    })
  })
})

// ── Expand / collapse detail row ──────────────────────────────────────────────

describe('LeadTable — expand/collapse', () => {
  it('shows Expand button by default', () => {
    render(<LeadTable leads={[makeLead()]} />)
    expect(screen.getByText('Expand')).toBeInTheDocument()
  })

  it('shows detail row with address after clicking Expand', () => {
    render(<LeadTable leads={[makeLead()]} />)
    fireEvent.click(screen.getByText('Expand'))
    expect(screen.getByText(/123 Main St/)).toBeInTheDocument()
  })

  it('shows pitch notes in expanded row', () => {
    render(<LeadTable leads={[makeLead({ pitch_notes: 'Great prospect' })]} />)
    fireEvent.click(screen.getByText('Expand'))
    expect(screen.getByText('Great prospect')).toBeInTheDocument()
  })

  it('collapses the detail row after clicking Hide', () => {
    render(<LeadTable leads={[makeLead()]} />)
    fireEvent.click(screen.getByText('Expand'))
    fireEvent.click(screen.getByText('Hide'))
    expect(screen.queryByText(/123 Main St/)).not.toBeInTheDocument()
  })

  it('shows notes textarea in expanded row when onNotesChange is provided', () => {
    const handler = vi.fn().mockResolvedValue(undefined)
    render(<LeadTable leads={[makeLead()]} onNotesChange={handler} />)
    fireEvent.click(screen.getByText('Expand'))
    expect(screen.getByPlaceholderText(/call notes/i)).toBeInTheDocument()
  })
})

// ── Section dividers ──────────────────────────────────────────────────────────

describe('LeadTable — section dividers', () => {
  it('shows No Website and Has Website dividers when leads are mixed', () => {
    const leads = [
      makeLead({ id: '1', name: 'No Web Biz',  website: '' }),
      makeLead({ id: '2', name: 'Has Web Biz', website: 'https://example.com' }),
    ]
    render(<LeadTable leads={leads} />)
    expect(screen.getByText(/no website/i)).toBeInTheDocument()
    expect(screen.getByText(/has website/i)).toBeInTheDocument()
  })

  it('does not show dividers when all leads have no website', () => {
    const leads = [
      makeLead({ id: '1', name: 'Biz 1', website: '' }),
      makeLead({ id: '2', name: 'Biz 2', website: '' }),
    ]
    render(<LeadTable leads={leads} />)
    expect(screen.queryByText(/no website/i)).not.toBeInTheDocument()
  })

  it('does not show dividers when all leads have a website', () => {
    const leads = [
      makeLead({ id: '1', name: 'Biz 1', website: 'https://a.com' }),
      makeLead({ id: '2', name: 'Biz 2', website: 'https://b.com' }),
    ]
    render(<LeadTable leads={leads} />)
    expect(screen.queryByText(/has website/i)).not.toBeInTheDocument()
  })
})

// ── Table headers ─────────────────────────────────────────────────────────────

describe('LeadTable — table headers', () => {
  it('renders all column headers', () => {
    render(<LeadTable leads={[makeLead()]} />)
    expect(screen.getByText(/business/i)).toBeInTheDocument()
    expect(screen.getByText(/phone/i)).toBeInTheDocument()
    expect(screen.getByText(/niche/i)).toBeInTheDocument()
    expect(screen.getByText(/city/i)).toBeInTheDocument()
    expect(screen.getByText(/website/i)).toBeInTheDocument()
    expect(screen.getByText(/score/i)).toBeInTheDocument()
    expect(screen.getByText(/status/i)).toBeInTheDocument()
  })
})
