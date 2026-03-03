'use client'

// ============================================================
// Generic combobox / autocomplete component.
// Supports any list of { label, sublabel?, value } options.
// ============================================================

import { useState, useRef, useEffect, useCallback } from 'react'

export interface ComboOption {
  value: string         // stored value
  label: string         // primary display text
  sublabel?: string     // secondary (e.g. abbreviation, country)
  group?: string        // optional group header
}

interface Props {
  value: string
  onChange: (value: string) => void
  options: ComboOption[]
  placeholder?: string
  /** If true, typing a value not in the list still stores it as-is */
  allowFreeText?: boolean
  className?: string
  /** Called when user commits (blur / enter / click) with no match; clears if false */
  onNoMatch?: (raw: string) => void
}

export function Combobox({
  value,
  onChange,
  options,
  placeholder = 'Type to search…',
  allowFreeText = false,
  className = '',
}: Props) {
  const [inputVal,  setInputVal]  = useState(value)
  const [open,      setOpen]      = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef     = useRef<HTMLInputElement>(null)

  // Sync external value → input display
  useEffect(() => { setInputVal(value) }, [value])

  // Click outside closes dropdown
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  // Filter options on every keystroke
  const filtered = options
    .filter(o => {
      const q = inputVal.toLowerCase()
      return (
        o.label.toLowerCase().includes(q)    ||
        (o.sublabel ?? '').toLowerCase().includes(q) ||
        o.value.toLowerCase().includes(q)
      )
    })
    .slice(0, 40) // cap at 40 results for performance

  function commit(option: ComboOption) {
    onChange(option.value)
    setInputVal(option.label)
    setOpen(false)
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    setInputVal(e.target.value)
    setHighlight(0)
    setOpen(true)
    if (allowFreeText) onChange(e.target.value)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open) { if (e.key === 'ArrowDown' || e.key === 'Enter') setOpen(true); return }

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight(h => Math.min(h + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight(h => Math.max(h - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filtered[highlight]) commit(filtered[highlight])
      else if (allowFreeText) { onChange(inputVal); setOpen(false) }
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  function handleBlur() {
    // Small delay so click on option registers first
    setTimeout(() => {
      if (!containerRef.current?.contains(document.activeElement)) {
        // If free text is allowed, keep whatever was typed
        if (!allowFreeText) {
          // Revert to last committed value if nothing matches
          const exact = options.find(
            o => o.label.toLowerCase() === inputVal.toLowerCase() ||
                 o.value.toLowerCase() === inputVal.toLowerCase() ||
                 (o.sublabel ?? '').toLowerCase() === inputVal.toLowerCase()
          )
          if (exact) { commit(exact) }
          else {
            // Clear back to the current external value
            setInputVal(value)
          }
        }
        setOpen(false)
      }
    }, 150)
  }

  // Group rendering
  let lastGroup: string | undefined = undefined

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <input
        ref={inputRef}
        type="text"
        value={inputVal}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        autoComplete="off"
        className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
      />

      {/* Dropdown arrow */}
      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none text-xs">
        ▾
      </span>

      {open && filtered.length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-h-60 overflow-y-auto bg-slate-800 border border-slate-600 rounded-xl shadow-xl">
          {filtered.map((opt, i) => {
            const showGroup = opt.group && opt.group !== lastGroup
            if (showGroup) lastGroup = opt.group
            return (
              <div key={`${opt.value}-${i}`}>
                {showGroup && (
                  <div className="px-3 py-1.5 text-xs font-semibold uppercase tracking-widest text-slate-500 bg-slate-900/60 border-b border-slate-700">
                    {opt.group}
                  </div>
                )}
                <div
                  onMouseDown={() => commit(opt)}
                  onMouseEnter={() => setHighlight(i)}
                  className={`px-3 py-2 cursor-pointer flex items-center justify-between text-sm transition ${
                    i === highlight
                      ? 'bg-blue-500/20 text-white'
                      : 'text-slate-200 hover:bg-slate-700/60'
                  }`}
                >
                  <span>{opt.label}</span>
                  {opt.sublabel && (
                    <span className="text-xs text-slate-500 ml-2">{opt.sublabel}</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* No results hint when user has typed something */}
      {open && filtered.length === 0 && inputVal && (
        <div className="absolute z-50 mt-1 w-full bg-slate-800 border border-slate-600 rounded-xl shadow-xl px-3 py-2.5 text-xs text-slate-500">
          {allowFreeText ? `Using "${inputVal}" as custom value` : 'No matches — try a different spelling'}
        </div>
      )}
    </div>
  )
}
