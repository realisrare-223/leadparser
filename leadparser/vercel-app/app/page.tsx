import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'

// Root page: redirect based on auth + role
export default async function RootPage() {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  // Check role to route to the right dashboard
  const { data: caller } = await supabase
    .from('callers')
    .select('role')
    .eq('id', user.id)
    .single()

  if (caller?.role === 'admin') {
    redirect('/admin')
  }

  redirect('/dashboard')
}
