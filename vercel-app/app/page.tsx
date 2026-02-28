'use client';

import { useState, useEffect } from 'react';

interface Lead {
  id: string;
  name: string;
  phone: string;
  niche: string;
  city: string;
  state: string;
  rating: number;
  review_count: number;
  lead_score: number;
  date_added: string;
  gmb_link: string;
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'settings'>('dashboard');
  const [leads, setLeads] = useState<Lead[]>([]);
  const [stats, setStats] = useState({ total: 0, hot: 0, warm: 0, new_this_session: 0 });
  const [filter, setFilter] = useState('all');
  
  // Form state
  const [niche, setNiche] = useState('plumbers');
  const [city, setCity] = useState('Houston');
  const [state, setState] = useState('TX');
  const [limit, setLimit] = useState(100);
  
  // Scraping state
  const [isScraping, setIsScraping] = useState(false);
  const [scrapeProgress, setScrapeProgress] = useState({ current: 0, total: 100, message: '' });
  const [apiKey, setApiKey] = useState('');

  // Fetch leads
  const fetchLeads = async () => {
    try {
      const res = await fetch(`/api/leads?filter=${filter}`);
      const data = await res.json();
      setLeads(data);
    } catch (err) {
      console.error('Failed to fetch leads');
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch stats');
    }
  };

  useEffect(() => {
    fetchLeads();
    fetchStats();
    const interval = setInterval(() => {
      fetchLeads();
      fetchStats();
    }, 5000);
    return () => clearInterval(interval);
  }, [filter]);

  const startScraping = async () => {
    if (!niche || !city || !state) return;
    
    setIsScraping(true);
    setScrapeProgress({ current: 0, total: limit, message: 'Starting...' });
    
    try {
      const res = await fetch('/api/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche, city, state, limit })
      });
      
      const data = await res.json();
      
      if (data.success) {
        setScrapeProgress({ 
          current: limit, 
          total: limit, 
          message: `Found ${data.leads_found} new leads!` 
        });
        fetchLeads();
        fetchStats();
      } else {
        setScrapeProgress({ current: 0, total: limit, message: data.error || 'Failed' });
      }
    } catch (err) {
      setScrapeProgress({ current: 0, total: limit, message: 'Network error' });
    } finally {
      setIsScraping(false);
    }
  };

  const exportCSV = () => {
    window.open('/api/export', '_blank');
  };

  const clearLeads = async () => {
    if (!confirm('Clear all leads?')) return;
    await fetch('/api/leads', { method: 'DELETE' });
    fetchLeads();
    fetchStats();
  };

  const getTier = (score: number) => {
    if (score >= 18) return { label: 'HOT', color: '#ef4444', bg: 'rgba(239,68,68,0.2)' };
    if (score >= 12) return { label: 'WARM', color: '#f59e0b', bg: 'rgba(245,158,11,0.2)' };
    return { label: 'MED', color: '#60a5fa', bg: 'rgba(59,130,246,0.2)' };
  };

  const styles = {
    body: { background: '#0f172a', color: '#e2e8f0', minHeight: '100vh' },
    header: {
      background: 'linear-gradient(135deg, #1e293b 0%, #334155 100%)',
      padding: '20px 30px',
      borderBottom: '1px solid #475569',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    },
    headerTitle: {
      fontSize: '24px',
      background: 'linear-gradient(90deg, #60a5fa, #a78bfa)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent'
    },
    nav: { display: 'flex', gap: '20px' },
    navBtn: (active: boolean) => ({
      padding: '8px 16px',
      borderRadius: '8px',
      border: 'none',
      background: active ? '#475569' : 'transparent',
      color: active ? '#fff' : '#94a3b8',
      cursor: 'pointer',
      fontSize: '14px'
    }),
    container: { maxWidth: '1400px', margin: '0 auto', padding: '30px' },
    card: {
      background: '#1e293b',
      borderRadius: '16px',
      padding: '24px',
      marginBottom: '24px',
      border: '1px solid #334155'
    },
    cardTitle: { color: '#60a5fa', marginBottom: '20px', fontSize: '18px' },
    formGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '16px',
      marginBottom: '20px'
    },
    formGroup: { display: 'flex', flexDirection: 'column' as const },
    label: {
      fontSize: '12px',
      textTransform: 'uppercase' as const,
      color: '#94a3b8',
      marginBottom: '6px',
      fontWeight: 600
    },
    input: {
      padding: '12px 16px',
      border: '1px solid #475569',
      borderRadius: '10px',
      background: '#0f172a',
      color: '#fff',
      fontSize: '14px'
    },
    select: {
      padding: '12px 16px',
      border: '1px solid #475569',
      borderRadius: '10px',
      background: '#0f172a',
      color: '#fff',
      fontSize: '14px'
    },
    btn: {
      padding: '14px 28px',
      border: 'none',
      borderRadius: '10px',
      fontSize: '14px',
      fontWeight: 600,
      cursor: 'pointer',
      background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
      color: 'white'
    },
    btnDisabled: { opacity: 0.6, cursor: 'not-allowed' as const },
    statusBar: {
      background: '#0f172a',
      border: '1px solid #334155',
      borderRadius: '10px',
      padding: '16px 20px',
      marginTop: '20px',
      display: 'flex',
      alignItems: 'center',
      gap: '16px'
    },
    progressBar: { flex: 1, height: '8px', background: '#334155', borderRadius: '4px', overflow: 'hidden' as const },
    progressFill: (pct: number) => ({
      height: '100%',
      width: `${pct}%`,
      background: 'linear-gradient(90deg, #3b82f6, #60a5fa)',
      borderRadius: '4px',
      transition: 'width 0.3s'
    }),
    statsGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '20px',
      marginBottom: '30px'
    },
    statCard: (color: string) => ({
      background: '#1e293b',
      borderRadius: '16px',
      padding: '24px',
      border: '1px solid #334155',
      borderLeft: `4px solid ${color}`
    }),
    statValue: { fontSize: '36px', fontWeight: 700, color: '#fff' },
    statLabel: { fontSize: '14px', color: '#94a3b8', textTransform: 'uppercase' as const },
    filters: { display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' as const },
    filterBtn: (active: boolean) => ({
      padding: '8px 16px',
      border: '1px solid #475569',
      borderRadius: '20px',
      background: active ? '#3b82f6' : '#0f172a',
      color: active ? '#fff' : '#94a3b8',
      cursor: 'pointer',
      fontSize: '13px'
    }),
    table: { width: '100%', borderCollapse: 'collapse' as const, background: '#1e293b', borderRadius: '16px', overflow: 'hidden' as const },
    th: { background: '#0f172a', padding: '16px', textAlign: 'left' as const, fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase' as const },
    td: { padding: '16px', borderBottom: '1px solid #334155' },
    badge: (color: string, bg: string) => ({
      display: 'inline-block',
      padding: '4px 12px',
      borderRadius: '12px',
      fontSize: '12px',
      fontWeight: 600,
      color,
      background: bg
    }),
    alert: {
      background: 'rgba(245, 158, 11, 0.1)',
      border: '1px solid #f59e0b',
      borderRadius: '10px',
      padding: '16px',
      marginBottom: '20px',
      color: '#f59e0b'
    }
  };

  return (
    <div style={styles.body}>
      <header style={styles.header}>
        <h1 style={styles.headerTitle}>🔍 LeadParser Pro</h1>
        <nav style={styles.nav}>
          <button style={styles.navBtn(activeTab === 'dashboard')} onClick={() => setActiveTab('dashboard')}>
            Dashboard
          </button>
          <button style={styles.navBtn(activeTab === 'settings')} onClick={() => setActiveTab('settings')}>
            Settings
          </button>
        </nav>
      </header>

      <div style={styles.container}>
        {activeTab === 'dashboard' && (
          <>
            {/* Setup Alert */}
            {!process.env.NEXT_PUBLIC_GOOGLE_PLACES_API_KEY && (
              <div style={styles.alert}>
                <strong>⚠️ Setup Required:</strong> Add your Google Places API key in Settings or as GOOGLE_PLACES_API_KEY environment variable in Vercel.
              </div>
            )}

            {/* Control Panel */}
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>⚡ Scrape New Leads</h2>
              <div style={styles.formGrid}>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Niche / Business Type</label>
                  <input 
                    style={styles.input} 
                    value={niche} 
                    onChange={e => setNiche(e.target.value)}
                    placeholder="e.g., plumbers, auto detailing"
                  />
                </div>
                <div style={styles.formGroup}>
                  <label style={styles.label}>City</label>
                  <input 
                    style={styles.input} 
                    value={city} 
                    onChange={e => setCity(e.target.value)}
                    placeholder="e.g., Houston"
                  />
                </div>
                <div style={styles.formGroup}>
                  <label style={styles.label}>State</label>
                  <input 
                    style={styles.input} 
                    value={state} 
                    onChange={e => setState(e.target.value.toUpperCase())}
                    maxLength={2}
                    placeholder="TX"
                  />
                </div>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Number of Leads</label>
                  <select style={styles.select} value={limit} onChange={e => setLimit(Number(e.target.value))}>
                    <option value={50}>50 leads</option>
                    <option value={100}>100 leads</option>
                    <option value={200}>200 leads</option>
                  </select>
                </div>
              </div>
              <button 
                style={{...styles.btn, ...(isScraping ? styles.btnDisabled : {})}}
                onClick={startScraping}
                disabled={isScraping}
              >
                {isScraping ? '⏳ Scraping...' : '🚀 Start Scraping'}
              </button>
              
              {scrapeProgress.message && (
                <div style={styles.statusBar}>
                  <span>{scrapeProgress.message}</span>
                  {isScraping && (
                    <>
                      <div style={styles.progressBar}>
                        <div style={styles.progressFill((scrapeProgress.current / scrapeProgress.total) * 100)} />
                      </div>
                      <span>{scrapeProgress.current}/{scrapeProgress.total}</span>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Stats */}
            <div style={styles.statsGrid}>
              <div style={styles.statCard('#ef4444')}>
                <div style={styles.statValue}>{stats.hot}</div>
                <div style={styles.statLabel}>🔥 Hot Leads (18+)</div>
              </div>
              <div style={styles.statCard('#f59e0b')}>
                <div style={styles.statValue}>{stats.warm}</div>
                <div style={styles.statLabel}>🌡️ Warm Leads (12-17)</div>
              </div>
              <div style={styles.statCard('#3b82f6')}>
                <div style={styles.statValue}>{stats.total}</div>
                <div style={styles.statLabel}>📊 Total Qualified</div>
              </div>
              <div style={styles.statCard('#22c55e')}>
                <div style={styles.statValue}>{stats.new_this_session}</div>
                <div style={styles.statLabel}>✨ New Today</div>
              </div>
            </div>

            {/* Filters */}
            <div style={styles.filters}>
              {['all', 'hot', 'warm', 'medium'].map(f => (
                <button
                  key={f}
                  style={styles.filterBtn(filter === f)}
                  onClick={() => setFilter(f)}
                >
                  {f === 'all' ? 'All Leads' : f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
              <button style={{...styles.btn, marginLeft: 'auto'}} onClick={exportCSV}>
                📥 Export CSV
              </button>
            </div>

            {/* Leads Table */}
            <div style={styles.card}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Business</th>
                    <th style={styles.th}>Phone</th>
                    <th style={styles.th}>Niche</th>
                    <th style={styles.th}>City</th>
                    <th style={styles.th}>Rating</th>
                    <th style={styles.th}>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{...styles.td, textAlign: 'center', padding: '40px', color: '#64748b'}}>
                        No qualified leads yet. Start scraping to find businesses with no website + phone number!
                      </td>
                    </tr>
                  ) : leads.map((lead) => {
                    const tier = getTier(lead.lead_score);
                    return (
                      <tr key={lead.id}>
                        <td style={styles.td}><strong>{lead.name}</strong></td>
                        <td style={{...styles.td, color: '#22c55e', fontFamily: 'monospace'}}>{lead.phone}</td>
                        <td style={styles.td}>{lead.niche}</td>
                        <td style={styles.td}>{lead.city}, {lead.state}</td>
                        <td style={styles.td}>{lead.rating || '-'} ⭐</td>
                        <td style={styles.td}>
                          <span style={styles.badge(tier.color, tier.bg)}>
                            {lead.lead_score} {tier.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        {activeTab === 'settings' && (
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>⚙️ Settings</h2>
            
            <div style={{ marginBottom: '30px' }}>
              <h3 style={{ color: '#60a5fa', marginBottom: '10px' }}>Google Places API Key</h3>
              <p style={{ color: '#94a3b8', marginBottom: '15px' }}>
                Get your free API key from{' '}
                <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noreferrer" style={{ color: '#60a5fa' }}>
                  Google Cloud Console
                </a>
                . Enable the Places API (free tier: $200/month credit).
              </p>
              <input
                type="password"
                style={{...styles.input, maxWidth: '500px'}}
                placeholder="Paste your API key here"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
              />
              <p style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>
                For production, set this as an environment variable in Vercel instead.
              </p>
            </div>

            <div style={{ marginBottom: '30px' }}>
              <h3 style={{ color: '#60a5fa', marginBottom: '10px' }}>Data Management</h3>
              <button style={{...styles.btn, background: '#ef4444'}} onClick={clearLeads}>
                🗑️ Clear All Leads
              </button>
              <p style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>
                This will permanently delete all scraped leads.
              </p>
            </div>

            <div>
              <h3 style={{ color: '#60a5fa', marginBottom: '10px' }}>Deployment</h3>
              <div style={{ background: '#0f172a', padding: '16px', borderRadius: '8px', fontFamily: 'monospace', fontSize: '13px' }}>
                <p style={{ color: '#22c55e', marginBottom: '8px' }}># Deploy to Vercel:</p>
                <p style={{ color: '#94a3b8' }}>cd vercel-app</p>
                <p style={{ color: '#94a3b8' }}>npm install</p>
                <p style={{ color: '#94a3b8' }}>vercel</p>
                <br/>
                <p style={{ color: '#f59e0b' }}># Then add environment variable:</p>
                <p style={{ color: '#94a3b8' }}>vercel env add GOOGLE_PLACES_API_KEY</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
