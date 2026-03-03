#!/usr/bin/env python3
"""
LeadParser Pro Dashboard — Enhanced Web Interface
==================================================
Features:
  - Scrape 100 leads at a time with one click
  - Select niche, city, state for each scrape
  - Only shows leads with NO website + HAS phone number
  - Automatic deduplication
  - Settings/Config management
  - Real-time scraping status

Usage:
  python app.py                              # default http://localhost:5000
  python app.py --port 8080                  # custom port
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from flask import Flask, render_template_string, jsonify, request

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from exporters.sqlite_handler import SQLiteHandler
from utils.lead_scorer import LeadScorer

app = Flask(__name__)

# Global state
scraping_status = {
    "is_running": False,
    "current_niche": "",
    "current_city": "",
    "progress": 0,
    "total": 100,
    "message": "Ready",
    "last_run": None,
    "leads_found": 0
}

CONFIG_PATH = Path("config.yaml")
DB_PATH = Path("data/leads.db")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler("logs/dashboard.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================
# HTML TEMPLATES
# ============================================================

MAIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LeadParser Pro Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            padding: 20px 30px;
            border-bottom: 1px solid #475569;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 24px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .nav-links {
            display: flex;
            gap: 20px;
        }
        
        .nav-links a {
            color: #94a3b8;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.3s;
        }
        
        .nav-links a:hover, .nav-links a.active {
            color: #fff;
            background: #475569;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px;
        }
        
        .control-panel {
            background: #1e293b;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 30px;
            border: 1px solid #334155;
        }
        
        .control-panel h2 {
            margin-bottom: 20px;
            color: #60a5fa;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        .form-group label {
            font-size: 12px;
            text-transform: uppercase;
            color: #94a3b8;
            margin-bottom: 6px;
            font-weight: 600;
        }
        
        .form-group input, .form-group select {
            padding: 12px 16px;
            border: 1px solid #475569;
            border-radius: 10px;
            background: #0f172a;
            color: #fff;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #60a5fa;
            box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.1);
        }
        
        .btn {
            padding: 14px 28px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
        }
        
        .btn-primary:hover:not(:disabled) {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            transform: translateY(-2px);
        }
        
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .btn-secondary {
            background: #475569;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #64748b;
        }
        
        .status-bar {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 16px 20px;
            margin-top: 20px;
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-indicator.ready { background: #22c55e; }
        .status-indicator.running { background: #f59e0b; }
        .status-indicator.error { background: #ef4444; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .progress-bar {
            flex: 1;
            height: 8px;
            background: #334155;
            border-radius: 4px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #3b82f6, #60a5fa);
            border-radius: 4px;
            transition: width 0.3s;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: #1e293b;
            border-radius: 16px;
            padding: 24px;
            border: 1px solid #334155;
        }
        
        .stat-card h3 {
            font-size: 14px;
            color: #94a3b8;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        
        .stat-value {
            font-size: 36px;
            font-weight: 700;
            color: #fff;
        }
        
        .stat-card.hot { border-left: 4px solid #ef4444; }
        .stat-card.warm { border-left: 4px solid #f59e0b; }
        .stat-card.total { border-left: 4px solid #3b82f6; }
        .stat-card.new { border-left: 4px solid #22c55e; }
        
        .filters {
            background: #1e293b;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #334155;
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .filters h3 {
            color: #94a3b8;
            font-size: 14px;
            margin-right: 10px;
        }
        
        .filter-btn {
            padding: 8px 16px;
            border: 1px solid #475569;
            border-radius: 20px;
            background: #0f172a;
            color: #94a3b8;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.3s;
        }
        
        .filter-btn:hover, .filter-btn.active {
            background: #3b82f6;
            color: white;
            border-color: #3b82f6;
        }
        
        .leads-table-container {
            background: #1e293b;
            border-radius: 16px;
            border: 1px solid #334155;
            overflow: hidden;
        }
        
        .leads-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .leads-table th {
            background: #0f172a;
            padding: 16px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            color: #94a3b8;
            font-weight: 600;
            border-bottom: 1px solid #334155;
        }
        
        .leads-table td {
            padding: 16px;
            border-bottom: 1px solid #334155;
            font-size: 14px;
        }
        
        .leads-table tr:hover {
            background: #334155;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .badge-hot {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }
        
        .badge-warm {
            background: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }
        
        .badge-medium {
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
        }
        
        .badge-low {
            background: rgba(148, 163, 184, 0.2);
            color: #94a3b8;
        }
        
        .phone {
            font-family: monospace;
            color: #22c55e;
            font-weight: 600;
        }
        
        .no-leads {
            text-align: center;
            padding: 60px 20px;
            color: #64748b;
        }
        
        .no-leads h3 {
            font-size: 20px;
            margin-bottom: 10px;
            color: #94a3b8;
        }
        
        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #fff;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .toast {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.4);
            display: none;
            align-items: center;
            gap: 12px;
            z-index: 1000;
        }
        
        .toast.show {
            display: flex;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 LeadParser Pro</h1>
        <nav class="nav-links">
            <a href="/" class="active">Dashboard</a>
            <a href="/settings">Settings</a>
            <a href="/export">Export</a>
        </nav>
    </div>
    
    <div class="container">
        <!-- Control Panel -->
        <div class="control-panel">
            <h2>⚡ Scrape New Leads</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>Niche / Business Type</label>
                    <input type="text" id="niche" placeholder="e.g., plumbers, auto detailing" value="auto detailing">
                </div>
                <div class="form-group">
                    <label>City</label>
                    <input type="text" id="city" placeholder="e.g., Dallas" value="Dallas">
                </div>
                <div class="form-group">
                    <label>State</label>
                    <input type="text" id="state" placeholder="e.g., TX" value="TX" maxlength="2">
                </div>
                <div class="form-group">
                    <label>Number of Leads</label>
                    <select id="limit">
                        <option value="50">50 leads</option>
                        <option value="100" selected>100 leads</option>
                        <option value="200">200 leads</option>
                    </select>
                </div>
            </div>
            <button class="btn btn-primary" id="scrapeBtn" onclick="startScraping()">
                <span>🚀 Start Scraping</span>
            </button>
            
            <div class="status-bar" id="statusBar" style="display: none;">
                <div class="status-indicator ready" id="statusIndicator"></div>
                <span id="statusText">Ready</span>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                </div>
                <span id="progressText">0/100</span>
            </div>
        </div>
        
        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card hot">
                <h3>🔥 Hot Leads (18+)</h3>
                <div class="stat-value" id="hotCount">-</div>
            </div>
            <div class="stat-card warm">
                <h3>🌡️ Warm Leads (12-17)</h3>
                <div class="stat-value" id="warmCount">-</div>
            </div>
            <div class="stat-card total">
                <h3>📊 Total Qualified Leads</h3>
                <div class="stat-value" id="totalCount">-</div>
            </div>
            <div class="stat-card new">
                <h3>✨ New This Session</h3>
                <div class="stat-value" id="newCount">-</div>
            </div>
        </div>
        
        <!-- Filters -->
        <div class="filters">
            <h3>Filter by Score:</h3>
            <button class="filter-btn active" onclick="filterLeads('all')">All</button>
            <button class="filter-btn" onclick="filterLeads('hot')">Hot (18+)</button>
            <button class="filter-btn" onclick="filterLeads('warm')">Warm (12-17)</button>
            <button class="filter-btn" onclick="filterLeads('medium')">Medium (7-11)</button>
        </div>
        
        <!-- Leads Table -->
        <div class="leads-table-container">
            <table class="leads-table">
                <thead>
                    <tr>
                        <th>Business Name</th>
                        <th>Phone</th>
                        <th>Niche</th>
                        <th>City</th>
                        <th>Rating</th>
                        <th>Reviews</th>
                        <th>Score</th>
                        <th>Added</th>
                    </tr>
                </thead>
                <tbody id="leadsTableBody">
                    <tr>
                        <td colspan="8" class="no-leads">
                            <h3>No leads yet</h3>
                            <p>Use the form above to scrape your first batch of leads</p>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="toast" id="toast">
        <span id="toastIcon">✅</span>
        <span id="toastMessage">Operation completed</span>
    </div>

    <script>
        let currentFilter = 'all';
        let leadsData = [];
        
        // Load leads on page load
        loadLeads();
        updateStats();
        
        // Auto-refresh every 5 seconds when scraping
        setInterval(() => {
            checkStatus();
            if (scraping_status && scraping_status.is_running) {
                loadLeads();
                updateStats();
            }
        }, 5000);
        
        let scraping_status = {};
        
        async function checkStatus() {
            const response = await fetch('/api/status');
            scraping_status = await response.json();
            
            const statusBar = document.getElementById('statusBar');
            const statusIndicator = document.getElementById('statusIndicator');
            const statusText = document.getElementById('statusText');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            const scrapeBtn = document.getElementById('scrapeBtn');
            
            if (scraping_status.is_running) {
                statusBar.style.display = 'flex';
                statusIndicator.className = 'status-indicator running';
                statusText.textContent = scraping_status.message;
                progressFill.style.width = (scraping_status.progress / scraping_status.total * 100) + '%';
                progressText.textContent = scraping_status.progress + '/' + scraping_status.total;
                scrapeBtn.disabled = true;
                scrapeBtn.innerHTML = '<span class="spinner"></span> Scraping...';
            } else if (scraping_status.last_run) {
                statusBar.style.display = 'flex';
                statusIndicator.className = 'status-indicator ready';
                statusText.textContent = 'Last run: ' + scraping_status.last_run + ' | Found: ' + scraping_status.leads_found + ' new leads';
                progressFill.style.width = '100%';
                progressText.textContent = 'Complete';
                scrapeBtn.disabled = false;
                scrapeBtn.innerHTML = '<span>🚀 Start Scraping</span>';
            }
        }
        
        async function startScraping() {
            const niche = document.getElementById('niche').value;
            const city = document.getElementById('city').value;
            const state = document.getElementById('state').value;
            const limit = document.getElementById('limit').value;
            
            if (!niche || !city || !state) {
                showToast('⚠️ Please fill in all fields', 'warning');
                return;
            }
            
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({niche, city, state, limit: parseInt(limit)})
            });
            
            const result = await response.json();
            if (result.success) {
                showToast('🚀 Scraping started!', 'success');
                checkStatus();
            } else {
                showToast('❌ ' + result.error, 'error');
            }
        }
        
        async function loadLeads() {
            const response = await fetch('/api/leads?filter=' + currentFilter);
            leadsData = await response.json();
            renderLeads();
        }
        
        async function updateStats() {
            const response = await fetch('/api/stats');
            const stats = await response.json();
            document.getElementById('hotCount').textContent = stats.hot || 0;
            document.getElementById('warmCount').textContent = stats.warm || 0;
            document.getElementById('totalCount').textContent = stats.total || 0;
            document.getElementById('newCount').textContent = stats.new_this_session || 0;
        }
        
        function renderLeads() {
            const tbody = document.getElementById('leadsTableBody');
            
            if (leadsData.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="8" class="no-leads">
                            <h3>No qualified leads found</h3>
                            <p>Scrape leads that have no website and a valid phone number</p>
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = leadsData.map(lead => `
                <tr>
                    <td><strong>${escapeHtml(lead.name)}</strong></td>
                    <td class="phone">${escapeHtml(lead.phone || 'N/A')}</td>
                    <td>${escapeHtml(lead.niche)}</td>
                    <td>${escapeHtml(lead.city)}, ${escapeHtml(lead.state)}</td>
                    <td>${lead.rating || '-'} ⭐</td>
                    <td>${lead.review_count || 0}</td>
                    <td><span class="badge badge-${getTier(lead.lead_score)}">${lead.lead_score || 0}</span></td>
                    <td>${lead.date_added || '-'}</td>
                </tr>
            `).join('');
        }
        
        function filterLeads(tier) {
            currentFilter = tier;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            loadLeads();
        }
        
        function getTier(score) {
            if (score >= 18) return 'hot';
            if (score >= 12) return 'warm';
            if (score >= 7) return 'medium';
            return 'low';
        }
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function showToast(message, type) {
            const toast = document.getElementById('toast');
            document.getElementById('toastMessage').textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }
    </script>
</body>
</html>
"""

SETTINGS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Settings — LeadParser Pro</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            padding: 20px 30px;
            border-bottom: 1px solid #475569;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 24px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .nav-links {
            display: flex;
            gap: 20px;
        }
        
        .nav-links a {
            color: #94a3b8;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.3s;
        }
        
        .nav-links a:hover, .nav-links a.active {
            color: #fff;
            background: #475569;
        }
        
        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 30px;
        }
        
        .settings-section {
            background: #1e293b;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid #334155;
        }
        
        .settings-section h2 {
            color: #60a5fa;
            margin-bottom: 20px;
            font-size: 18px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            font-size: 13px;
            text-transform: uppercase;
            color: #94a3b8;
            margin-bottom: 8px;
            font-weight: 600;
        }
        
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 12px 16px;
            border: 1px solid #475569;
            border-radius: 10px;
            background: #0f172a;
            color: #fff;
            font-size: 14px;
        }
        
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #60a5fa;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        
        .checkbox-group input[type="checkbox"] {
            width: 20px;
            height: 20px;
            accent-color: #3b82f6;
        }
        
        .checkbox-group label {
            margin: 0;
            text-transform: none;
            font-weight: normal;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
        }
        
        .btn-primary:hover {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        }
        
        .btn-secondary {
            background: #475569;
            color: white;
            margin-left: 10px;
        }
        
        .help-text {
            font-size: 12px;
            color: #64748b;
            margin-top: 6px;
        }
        
        .niche-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        
        .niche-tag {
            background: #334155;
            padding: 6px 12px;
            border-radius: 16px;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .niche-tag button {
            background: none;
            border: none;
            color: #94a3b8;
            cursor: pointer;
            font-size: 16px;
            line-height: 1;
        }
        
        .niche-tag button:hover {
            color: #ef4444;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 LeadParser Pro</h1>
        <nav class="nav-links">
            <a href="/">Dashboard</a>
            <a href="/settings" class="active">Settings</a>
            <a href="/export">Export</a>
        </nav>
    </div>
    
    <div class="container">
        <!-- Scraping Settings -->
        <div class="settings-section">
            <h2>⚙️ Scraping Settings</h2>
            <div class="form-row">
                <div class="form-group">
                    <label>Delay Min (seconds)</label>
                    <input type="number" id="delay_min" step="0.1" value="{{ config.scraping.delay_min }}">
                    <div class="help-text">Minimum delay between requests</div>
                </div>
                <div class="form-group">
                    <label>Delay Max (seconds)</label>
                    <input type="number" id="delay_max" step="0.1" value="{{ config.scraping.delay_max }}">
                    <div class="help-text">Maximum delay between requests</div>
                </div>
                <div class="form-group">
                    <label>Max Retries</label>
                    <input type="number" id="max_retries" value="{{ config.scraping.max_retries }}">
                </div>
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="headless" {% if config.scraping.headless %}checked{% endif %}>
                <label>Headless Mode (hide browser window)</label>
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="use_undetected_chrome" {% if config.scraping.use_undetected_chrome %}checked{% endif %}>
                <label>Use Undetected Chrome (better anti-bot protection)</label>
            </div>
        </div>
        
        <!-- Filter Settings -->
        <div class="settings-section">
            <h2>🔍 Filter Settings</h2>
            <div class="form-row">
                <div class="form-group">
                    <label>Minimum Reviews</label>
                    <input type="number" id="min_reviews" value="{{ config.filters.min_reviews }}">
                </div>
                <div class="form-group">
                    <label>Maximum Reviews</label>
                    <input type="number" id="max_reviews" value="{{ config.filters.max_reviews }}">
                </div>
                <div class="form-group">
                    <label>Minimum Rating</label>
                    <input type="number" id="min_rating" step="0.1" max="5" value="{{ config.filters.min_rating }}">
                </div>
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="exclude_with_website" {% if config.filters.exclude_with_website %}checked{% endif %}>
                <label>Only include businesses WITHOUT websites (RECOMMENDED)</label>
            </div>
        </div>
        
        <!-- Default Niches -->
        <div class="settings-section">
            <h2>🎯 Default Niches</h2>
            <div class="form-group">
                <label>Add Niche</label>
                <input type="text" id="new_niche" placeholder="e.g., roofing contractors" onkeypress="if(event.key==='Enter') addNiche()">
                <button class="btn btn-secondary" onclick="addNiche()" style="margin-top: 10px;">Add Niche</button>
            </div>
            <div class="niche-list" id="nicheList">
                {% for niche in config.niches %}
                <div class="niche-tag">
                    {{ niche }}
                    <button onclick="removeNiche('{{ niche }}')">×</button>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <!-- Scoring Settings -->
        <div class="settings-section">
            <h2>📊 Lead Scoring Weights</h2>
            <div class="form-row">
                <div class="form-group">
                    <label>No Reviews Score</label>
                    <input type="number" id="no_reviews_score" value="{{ config.scoring.no_reviews_score }}">
                </div>
                <div class="form-group">
                    <label>No Website Bonus</label>
                    <input type="number" id="no_website_bonus" value="{{ config.scoring.no_website_bonus }}">
                </div>
                <div class="form-group">
                    <label>High-Value Niche Bonus</label>
                    <input type="number" id="high_value_niche_bonus" value="{{ config.scoring.high_value_niche_bonus }}">
                </div>
            </div>
        </div>
        
        <button class="btn btn-primary" onclick="saveSettings()">💾 Save Settings</button>
        <button class="btn btn-secondary" onclick="resetSettings()">↺ Reset to Defaults</button>
    </div>
    
    <script>
        let niches = {{ config.niches | tojson }};
        
        function addNiche() {
            const input = document.getElementById('new_niche');
            const niche = input.value.trim();
            if (niche && !niches.includes(niche)) {
                niches.push(niche);
                renderNiches();
                input.value = '';
            }
        }
        
        function removeNiche(niche) {
            niches = niches.filter(n => n !== niche);
            renderNiches();
        }
        
        function renderNiches() {
            const container = document.getElementById('nicheList');
            container.innerHTML = niches.map(n => `
                <div class="niche-tag">
                    ${n}
                    <button onclick="removeNiche('${n}')">×</button>
                </div>
            `).join('');
        }
        
        async function saveSettings() {
            const config = {
                scraping: {
                    delay_min: parseFloat(document.getElementById('delay_min').value),
                    delay_max: parseFloat(document.getElementById('delay_max').value),
                    max_retries: parseInt(document.getElementById('max_retries').value),
                    headless: document.getElementById('headless').checked,
                    use_undetected_chrome: document.getElementById('use_undetected_chrome').checked
                },
                filters: {
                    min_reviews: parseInt(document.getElementById('min_reviews').value),
                    max_reviews: parseInt(document.getElementById('max_reviews').value),
                    min_rating: parseFloat(document.getElementById('min_rating').value),
                    exclude_with_website: document.getElementById('exclude_with_website').checked
                },
                niches: niches,
                scoring: {
                    no_reviews_score: parseInt(document.getElementById('no_reviews_score').value),
                    no_website_bonus: parseInt(document.getElementById('no_website_bonus').value),
                    high_value_niche_bonus: parseInt(document.getElementById('high_value_niche_bonus').value)
                }
            };
            
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(config)
            });
            
            const result = await response.json();
            if (result.success) {
                alert('Settings saved successfully!');
            } else {
                alert('Error saving settings: ' + result.error);
            }
        }
        
        function resetSettings() {
            if (confirm('Reset all settings to defaults?')) {
                location.reload();
            }
        }
    </script>
</body>
</html>
"""


# ============================================================
# FLASK ROUTES
# ============================================================

@app.route("/")
def index():
    """Main dashboard page."""
    return render_template_string(MAIN_TEMPLATE)


@app.route("/settings")
def settings():
    """Settings page."""
    config = load_config()
    return render_template_string(SETTINGS_TEMPLATE, config=config)


@app.route("/export")
def export_page():
    """Export page - simple redirect to API for now."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Export — LeadParser Pro</title>
        <style>
            body { font-family: sans-serif; background: #0f172a; color: #e2e8f0; padding: 40px; }
            .container { max-width: 600px; margin: 0 auto; }
            h1 { color: #60a5fa; }
            .btn { display: inline-block; padding: 14px 28px; background: #3b82f6; color: white; 
                   text-decoration: none; border-radius: 10px; margin: 10px 0; }
            .btn:hover { background: #2563eb; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📥 Export Leads</h1>
            <p>Download your qualified leads in various formats:</p>
            <a href="/api/export/csv" class="btn">Download CSV</a><br>
            <a href="/api/export/json" class="btn">Download JSON</a><br>
            <a href="/" class="btn" style="background: #475569;">← Back to Dashboard</a>
        </div>
    </body>
    </html>
    """


# ============================================================
# API ENDPOINTS
# ============================================================

@app.route("/api/status")
def get_status():
    """Get current scraping status."""
    return jsonify(scraping_status)


@app.route("/api/scrape", methods=["POST"])
def start_scrape():
    """Start a scraping job."""
    global scraping_status
    
    if scraping_status["is_running"]:
        return jsonify({"success": False, "error": "Scraping already in progress"})
    
    data = request.json
    niche = data.get("niche", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "").strip().upper()
    limit = data.get("limit", 100)
    
    if not niche or not city or not state:
        return jsonify({"success": False, "error": "Niche, city, and state are required"})
    
    # Update config for this scrape
    config = load_config()
    config["location"]["city"] = city
    config["location"]["state"] = state
    config["location"]["full_address"] = f"{city}, {state}"
    config["niches"] = [niche]
    config["scraping"]["max_results_per_niche"] = limit
    
    # Start scraping in background thread
    thread = threading.Thread(
        target=run_scraper,
        args=(config, niche, city, state, limit)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True})


@app.route("/api/leads")
def get_leads():
    """Get leads with filtering."""
    filter_type = request.args.get("filter", "all")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    query = """
        SELECT * FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
    """
    params = []
    
    if filter_type == "hot":
        query += " AND lead_score >= 18"
    elif filter_type == "warm":
        query += " AND lead_score >= 12 AND lead_score < 18"
    elif filter_type == "medium":
        query += " AND lead_score >= 7 AND lead_score < 12"
    
    query += " ORDER BY lead_score DESC, date_added DESC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    leads = [dict(row) for row in rows]
    return jsonify(leads)


@app.route("/api/stats")
def get_stats():
    """Get dashboard statistics."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Total qualified leads (no website, has phone)
    total = conn.execute("""
        SELECT COUNT(*) FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
    """).fetchone()[0]
    
    # Hot leads (score >= 18)
    hot = conn.execute("""
        SELECT COUNT(*) FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
        AND lead_score >= 18
    """).fetchone()[0]
    
    # Warm leads (12-17)
    warm = conn.execute("""
        SELECT COUNT(*) FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
        AND lead_score >= 12 AND lead_score < 18
    """).fetchone()[0]
    
    # New leads today
    today = datetime.now().strftime("%Y-%m-%d")
    new_today = conn.execute("""
        SELECT COUNT(*) FROM leads WHERE date_added = ?
    """, (today,)).fetchone()[0]
    
    conn.close()
    
    return jsonify({
        "total": total,
        "hot": hot,
        "warm": warm,
        "new_this_session": new_today
    })


@app.route("/api/config", methods=["GET", "POST"])
def handle_config():
    """Get or update configuration."""
    if request.method == "GET":
        return jsonify(load_config())
    
    # POST - update config
    try:
        new_config = request.json
        config = load_config()
        
        # Update only allowed sections
        for key in ["scraping", "filters", "niches", "scoring"]:
            if key in new_config:
                config[key] = new_config[key]
        
        save_config(config)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/export/csv")
def export_csv():
    """Export leads to CSV."""
    import csv
    import io
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("""
        SELECT * FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
        ORDER BY lead_score DESC
    """).fetchall()
    
    conn.close()
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "name", "phone", "niche", "city", "state", "address",
        "rating", "review_count", "lead_score", "date_added", "gmb_link"
    ])
    writer.writeheader()
    
    for row in rows:
        writer.writerow({
            "name": row["name"],
            "phone": row["phone"],
            "niche": row["niche"],
            "city": row["city"],
            "state": row["state"],
            "address": row["address"],
            "rating": row["rating"],
            "review_count": row["review_count"],
            "lead_score": row["lead_score"],
            "date_added": row["date_added"],
            "gmb_link": row["gmb_link"]
        })
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"}
    )


@app.route("/api/export/json")
def export_json():
    """Export leads to JSON."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("""
        SELECT * FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
        ORDER BY lead_score DESC
    """).fetchall()
    
    conn.close()
    
    leads = [dict(row) for row in rows]
    
    from flask import Response
    return Response(
        json.dumps(leads, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=leads.json"}
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_config() -> dict:
    """Load configuration from YAML file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def save_config(config: dict):
    """Save configuration to YAML file."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def run_scraper(config: dict, niche: str, city: str, state: str, limit: int):
    """Run the scraper in background thread."""
    global scraping_status
    
    scraping_status.update({
        "is_running": True,
        "current_niche": niche,
        "current_city": city,
        "progress": 0,
        "total": limit,
        "message": f"Starting scrape for {niche} in {city}, {state}",
        "leads_found": 0
    })
    
    try:
        # Import here to avoid issues if modules aren't ready
        sys.path.insert(0, str(Path(__file__).parent))
        from scrapers.google_maps import GoogleMapsScraper
        
        # Initialize database
        db = SQLiteHandler(config)
        db.open()
        
        # Count leads before
        leads_before = db._conn.execute(
            "SELECT COUNT(*) FROM leads"
        ).fetchone()[0]
        
        # Start session
        session_id = db.start_session([niche], config)
        
        # Initialize scraper
        scraper = GoogleMapsScraper(config)
        
        # Track progress
        leads_collected = []
        
        def progress_callback(current, total, message):
            scraping_status["progress"] = current
            scraping_status["total"] = total
            scraping_status["message"] = message
        
        # Scrape with progress updates
        search_query = f"{niche} in {city}, {state}"
        scraping_status["message"] = f"Searching: {search_query}"
        
        try:
            scraper.start_browser()
            
            # Get search results page
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            
            scraper.driver.get("https://www.google.com/maps")
            time.sleep(2)
            
            # Search for the query
            search_box = scraper.driver.find_element(By.ID, "searchboxinput")
            search_box.clear()
            search_box.send_keys(search_query)
            search_box.send_keys(Keys.RETURN)
            
            scraping_status["message"] = "Waiting for results..."
            time.sleep(5)
            
            # Extract listings
            listings = []
            attempts = 0
            max_attempts = min(limit * 2, 200)  # Safety limit
            
            while len(listings) < limit and attempts < max_attempts:
                try:
                    # Find all result cards
                    cards = scraper.driver.find_elements(
                        By.CSS_SELECTOR, "[data-result-index]"
                    )
                    
                    for card in cards[len(listings):limit]:
                        try:
                            card.click()
                            time.sleep(2)
                            
                            # Extract data
                            lead = extract_business_data(scraper.driver, niche, city, state)
                            
                            if lead and is_qualified_lead(lead):
                                # Score the lead
                                scorer = LeadScorer(config)
                                lead["lead_score"] = scorer.score(lead, niche, config)
                                lead["date_added"] = datetime.now().strftime("%Y-%m-%d")
                                
                                # Insert to database (handles deduplication)
                                inserted, _ = db.insert_lead(lead)
                                
                                if inserted:
                                    listings.append(lead)
                                    scraping_status["leads_found"] = len(listings)
                                    scraping_status["progress"] = len(listings)
                                    
                                    logger.info(f"Added lead: {lead['name']} (Score: {lead['lead_score']})")
                            
                            if len(listings) >= limit:
                                break
                                
                        except Exception as e:
                            logger.debug(f"Error extracting card: {e}")
                            continue
                    
                    # Scroll for more results
                    scraper.driver.execute_script(
                        "document.querySelector('[data-result-index]').scrollIntoView(false);"
                    )
                    time.sleep(2)
                    
                    attempts += 1
                    
                except Exception as e:
                    logger.error(f"Scraping error: {e}")
                    break
            
        finally:
            scraper.stop_browser()
        
        # End session
        leads_after = db._conn.execute(
            "SELECT COUNT(*) FROM leads"
        ).fetchone()[0]
        
        new_leads = leads_after - leads_before
        
        db.end_session({
            "total": len(listings),
            "new": new_leads,
            "duplicates": len(listings) - new_leads,
            "errors": 0
        })
        
        db.close()
        
        scraping_status.update({
            "is_running": False,
            "message": f"Complete! Found {new_leads} new qualified leads",
            "last_run": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "progress": limit,
            "leads_found": new_leads
        })
        
        logger.info(f"Scraping complete: {new_leads} new leads found")
        
    except Exception as e:
        logger.exception("Scraping failed")
        scraping_status.update({
            "is_running": False,
            "message": f"Error: {str(e)}",
            "last_run": datetime.now().strftime("%Y-%m-%d %H:%M")
        })


def extract_business_data(driver, niche, city, state):
    """Extract business data from Google Maps detail view."""
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import NoSuchElementException
    
    lead = {
        "niche": niche,
        "city": city,
        "state": state,
        "data_source": "Google Maps"
    }
    
    try:
        # Business Name
        try:
            name_elem = driver.find_element(By.CSS_SELECTOR, "h1")
            lead["name"] = name_elem.text.strip()
        except:
            return None
        
        # Phone
        try:
            # Look for phone button or phone in text
            phone_elem = driver.find_element(
                By.XPATH, 
                "//button[contains(@data-tooltip, 'Phone')]//div[contains(@class, 'fontBody')]"
            )
            lead["phone"] = phone_elem.text.strip()
        except:
            try:
                # Alternative: look for phone pattern in page
                text = driver.find_element(By.TAG_NAME, "body").text
                import re
                phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
                if phone_match:
                    lead["phone"] = phone_match.group(0)
            except:
                lead["phone"] = ""
        
        # Address
        try:
            addr_elem = driver.find_element(
                By.CSS_SELECTOR, "[data-tooltip='Address']"
            )
            lead["address"] = addr_elem.text.strip()
        except:
            lead["address"] = ""
        
        # Website
        try:
            website_elem = driver.find_element(
                By.CSS_SELECTOR, "[data-tooltip='Website']"
            )
            lead["website"] = website_elem.text.strip()
        except:
            lead["website"] = ""
        
        # Rating
        try:
            rating_elem = driver.find_element(
                By.CSS_SELECTOR, "[role='img'][aria-label*='star']"
            )
            rating_text = rating_elem.get_attribute("aria-label")
            import re
            rating_match = re.search(r'(\d+\.?\d*)', rating_text)
            if rating_match:
                lead["rating"] = rating_match.group(1)
        except:
            lead["rating"] = ""
        
        # Review Count
        try:
            review_elem = driver.find_element(
                By.XPATH, 
                "//span[contains(text(), 'review') or contains(text(), 'Review')]"
            )
            text = review_elem.text
            import re
            count_match = re.search(r'([\d,]+)', text)
            if count_match:
                lead["review_count"] = int(count_match.group(1).replace(",", ""))
        except:
            lead["review_count"] = 0
        
        # Google Maps Link
        lead["gmb_link"] = driver.current_url
        
        return lead
        
    except Exception as e:
        logger.debug(f"Extraction error: {e}")
        return None


def is_qualified_lead(lead: dict) -> bool:
    """Check if lead meets qualifications (no website, has phone)."""
    has_phone = bool(lead.get("phone", "").strip())
    has_no_website = not bool(lead.get("website", "").strip())
    return has_phone and has_no_website


# ============================================================
# MAIN ENTRY
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="LeadParser Pro Dashboard")
    parser.add_argument("--port", type=int, default=5000, help="Port to run on")
    parser.add_argument("--open", action="store_true", help="Open browser on start")
    args = parser.parse_args()
    
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    # Open browser if requested
    if args.open:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()
    
    print(f"""
============================================================
              LeadParser Pro Dashboard
============================================================
  URL: http://localhost:{args.port}

  Features:
  * Scrape 100 leads at a time
  * Select niche & city for each scrape
  * Only shows: NO website + HAS phone
  * Automatic deduplication
  * Settings & configuration
============================================================
    """)
    
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
