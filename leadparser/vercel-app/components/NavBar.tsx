'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

interface NavBarProps {
  role?: 'caller' | 'admin'
  subtitle?: string
}

export function NavBar({ role, subtitle }: NavBarProps) {
  const router   = useRouter()
  const pathname = usePathname()

  async function handleLogout() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
  }

  const navLink = (href: string, label: string) => {
    const active = pathname === href
    return (
      <Link
        href={href}
        className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
          active
            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
            : 'text-slate-400 hover:text-white hover:bg-slate-800'
        }`}
      >
        {label}
      </Link>
    )
  }

  return (
    <header className="bg-slate-900 border-b border-slate-700 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
            LeadParser Engine
          </h1>
          {subtitle && <p className="text-slate-400 text-xs mt-0.5">{subtitle}</p>}
        </div>

        <nav className="flex items-center gap-1 ml-2">
          {navLink('/dashboard', 'My Leads')}
          {role === 'admin' && navLink('/admin', 'Admin')}
        </nav>
      </div>

      <button
        onClick={handleLogout}
        className="text-slate-400 hover:text-white text-sm transition"
      >
        Sign Out
      </button>
    </header>
  )
}
