import { NextResponse } from 'next/server'

// Redirects to the proper admin stats endpoint
export async function GET() {
  return NextResponse.redirect(new URL('/api/admin/stats', 'http://localhost'))
}
