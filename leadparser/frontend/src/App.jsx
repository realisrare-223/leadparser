import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from './config';

// Styles
const styles = {
  body: {
    fontFamily: 'system-ui, -apple-system, sans-serif',
    background: '#0f172a',
    color: '#e2e8f0',
    minHeight: '100vh',
    margin: 0
  },
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
  nav: {
    display: 'flex',
    gap: '20px'
  },
  navLink: {
    color: '#94a3b8',
    textDecoration: 'none',
    padding: '8px 16px',
    borderRadius: '8px',
    cursor: 'pointer',
    border: 'none',
    background: 'transparent',
    fontSize: '14px'
  },
  navLinkActive: {
    color: '#fff',
    background: '#475569'
  },
  container: {
    maxWidth: '1400px',
    margin: '0 auto',
    padding: '30px'
  },
  card: {
    background: '#1e293b',
    borderRadius: '16px',
    padding: '24px',
    marginBottom: '24px',
    border: '1px solid #334155'
  },
  cardTitle: {
    color: '#60a5fa',
    marginBottom: '20px',
    fontSize: '18px'
  },
  formGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '16px',
    marginBottom: '20px'
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column'
  },
  label: {
    fontSize: '12px',
    textTransform: 'uppercase',
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
  button: {
    padding: '14px 28px',
    border: 'none',
    borderRadius: '10px',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
    color: 'white'
  },
  buttonDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed'
  },
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
  progressBar: {
    flex: 1,
    height: '8px',
    background: '#334155',
    borderRadius: '4px',
    overflow: 'hidden'
  },
  progressFill: {
    height: '100%',
    background: 'linear-gradient(90deg, #3b82f6, #60a5fa)',
    borderRadius: '4px',
    transition: 'width 0.3s'
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '20px',
    marginBottom: '30px'
  },
  statCard: {
    background: '#1e293b',
    borderRadius: '16px',
    padding: '24px',
    border: '1px solid #334155',
    borderLeft: '4px solid #3b82f6'
  },
  statValue: {
    fontSize: '36px',
    fontWeight: 700,
    color: '#fff'
  },
  statLabel: {
    fontSize: '14px',
    color: '#94a3b8',
    textTransform: 'uppercase'
  },
  filters: {
    display: 'flex',
    gap: '12px',
    marginBottom: '20px',
    flexWrap: 'wrap'
  },
  filterBtn: {
    padding: '8px 16px',
    border: '1px solid #475569',
    borderRadius: '20px',
    background: '#0f172a',
    color: '#94a3b8',
    cursor: 'pointer',
    fontSize: '13px'
  },
  filterBtnActive: {
    background: '#3b82f6',
    color: 'white',
    borderColor: '#3b82f6'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    background: '#1e293b',
    borderRadius: '16px',
    overflow: 'hidden'
  },
  th: {
    background: '#0f172a',
    padding: '16px',
    textAlign: 'left',
    fontSize: '12px',
    color: '#94a3b8',
    textTransform: 'uppercase'
  },
  td: {
    padding: '16px',
    borderBottom: '1px solid #334155'
  },
  badge: {
    display: 'inline-block',
    padding: '4px 12px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: 600
  },
  alert: {
    background: 'rgba(245, 158, 11, 0.1)',
    border: '1px solid #f59e0b',
    borderRadius: '10px',
    padding: '16px',
    marginBottom: '20px',
    color: '#f59e0b'
  }
};

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState({ total: 0, hot: 0, warm: 0, new_this_session: 0 });
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Form state
  const [niche, setNiche] = useState('plumbers');
  const [city, setCity] = useState('Houston');
  const [state, setState] = useState('TX');
  const [limit, setLimit] = useState(100);
  
  // Scraping status
  const [status, setStatus] = useState({
    is_running: false,
    progress: 0,
    total: 100,
    message: 'Ready'
  });

  // Fetch leads and stats
  const fetchData = async () => {
    try {
      const [leadsRes, statsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/leads?filter=${filter}`),
        fetch(`${API_BASE_URL}/api/stats`)
      ]);
      
      if (!leadsRes.ok) throw new Error('Failed to fetch leads');
      
      const leadsData = await leadsRes.json();
      const statsData = await statsRes.json();
      
      setLeads(leadsData);
      setStats(statsData);
      setError(null);
    } catch (err) {
      setError('Cannot connect to API server. Make sure `python api_server.py` is running on your PC.');
    }
  };

  // Check scraping status
  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/status`);
      const data = await res.json();
      setStatus(data);
      
      if (data.is_running) {
        setTimeout(checkStatus, 2000);
        fetchData();
      }
    } catch (err) {
      console.log('Status check failed');
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [filter]);

  const startScraping = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/scrape`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche, city, state, limit })
      });
      
      if (!res.ok) throw new Error('Failed to start scraping');
      
      checkStatus();
    } catch (err) {
      setError('Failed to start scraping. Is the API server running?');
    }
  };

  const exportCSV = () => {
    window.open(`${API_BASE_URL}/api/export/csv`, '_blank');
  };

  const getTier = (score) => {
    if (score >= 18) return { label: 'HOT', color: '#ef4444', bg: 'rgba(239,68,68,0.2)' };
    if (score >= 12) return { label: 'WARM', color: '#f59e0b', bg: 'rgba(245,158,11,0.2)' };
    return { label: 'MED', color: '#60a5fa', bg: 'rgba(59,130,246,0.2)' };
  };

  // Dashboard View
  const Dashboard = () => (
    <>
      {error && (
        <div style={styles.alert}>
          <strong>⚠️ Connection Error:</strong> {error}
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
              placeholder="e.g., plumbers"
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
          style={{...styles.button, ...(status.is_running ? styles.buttonDisabled : {})}}
          onClick={startScraping}
          disabled={status.is_running}
        >
          {status.is_running ? '⏳ Scraping...' : '🚀 Start Scraping'}
        </button>
        
        {status.is_running && (
          <div style={styles.statusBar}>
            <span>🔄 {status.message}</span>
            <div style={styles.progressBar}>
              <div style={{...styles.progressFill, width: `${(status.progress / status.total) * 100}%`}} />
            </div>
            <span>{status.progress}/{status.total}</span>
          </div>
        )}
      </div>

      {/* Stats */}
      <div style={styles.statsGrid}>
        <div style={{...styles.statCard, borderLeftColor: '#ef4444'}}>
          <div style={styles.statValue}>{stats.hot}</div>
          <div style={styles.statLabel}>🔥 Hot Leads (18+)</div>
        </div>
        <div style={{...styles.statCard, borderLeftColor: '#f59e0b'}}>
          <div style={styles.statValue}>{stats.warm}</div>
          <div style={styles.statLabel}>🌡️ Warm Leads (12-17)</div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statValue}>{stats.total}</div>
          <div style={styles.statLabel}>📊 Total Qualified</div>
        </div>
        <div style={{...styles.statCard, borderLeftColor: '#22c55e'}}>
          <div style={styles.statValue}>{stats.new_this_session}</div>
          <div style={styles.statLabel}>✨ New Today</div>
        </div>
      </div>

      {/* Filters */}
      <div style={styles.filters}>
        {['all', 'hot', 'warm', 'medium'].map(f => (
          <button
            key={f}
            style={{...styles.filterBtn, ...(filter === f ? styles.filterBtnActive : {})}}
            onClick={() => setFilter(f)}
          >
            {f === 'all' ? 'All Leads' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
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
                  No qualified leads yet. Start scraping to find leads with no website + phone number!
                </td>
              </tr>
            ) : leads.map((lead, i) => {
              const tier = getTier(lead.lead_score);
              return (
                <tr key={i}>
                  <td style={styles.td}><strong>{lead.name}</strong></td>
                  <td style={{...styles.td, color: '#22c55e', fontFamily: 'monospace'}}>{lead.phone}</td>
                  <td style={styles.td}>{lead.niche}</td>
                  <td style={styles.td}>{lead.city}, {lead.state}</td>
                  <td style={styles.td}>{lead.rating || '-'} ★</td>
                  <td style={styles.td}>
                    <span style={{...styles.badge, color: tier.color, background: tier.bg}}>
                      {lead.lead_score || 0} {tier.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );

  // Settings View
  const Settings = () => (
    <div style={styles.card}>
      <h2 style={styles.cardTitle}>⚙️ Setup Instructions</h2>
      <div style={{ lineHeight: 1.8 }}>
        <h3 style={{ color: '#60a5fa', marginTop: 20 }}>1. Run API Server Locally</h3>
        <p>On your PC, run:</p>
        <code style={{ 
          display: 'block', 
          background: '#0f172a', 
          padding: '12px', 
          borderRadius: '8px',
          margin: '10px 0'
        }}>
          python api_server.py
        </code>

        <h3 style={{ color: '#60a5fa', marginTop: 20 }}>2. For Remote Access (Vercel)</h3>
        <p>Install ngrok and run:</p>
        <code style={{ 
          display: 'block', 
          background: '#0f172a', 
          padding: '12px', 
          borderRadius: '8px',
          margin: '10px 0'
        }}>
          ngrok http 5001
        </code>
        <p>Then update <code>src/config.js</code> with your ngrok URL.</p>

        <h3 style={{ color: '#60a5fa', marginTop: 20 }}>3. Current API URL</h3>
        <p style={{ color: '#f59e0b' }}>{API_BASE_URL}</p>
      </div>
    </div>
  );

  // Export View
  const Export = () => (
    <div style={styles.card}>
      <h2 style={styles.cardTitle}>📥 Export Leads</h2>
      <p style={{ marginBottom: 20, color: '#94a3b8' }}>
        Download all qualified leads (no website + has phone) in CSV format.
      </p>
      <button style={styles.button} onClick={exportCSV}>
        📄 Download CSV
      </button>
    </div>
  );

  return (
    <div style={styles.body}>
      <header style={styles.header}>
        <h1 style={styles.headerTitle}>🔍 LeadParser Pro</h1>
        <nav style={styles.nav}>
          {['dashboard', 'settings', 'export'].map(tab => (
            <button
              key={tab}
              style={{
                ...styles.navLink,
                ...(activeTab === tab ? styles.navLinkActive : {})
              }}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </header>

      <div style={styles.container}>
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'settings' && <Settings />}
        {activeTab === 'export' && <Export />}
      </div>
    </div>
  );
}

export default App;
