import React, { useState, useEffect } from 'react';
import { Shield, Bell, Star, Eye, Settings, LogOut } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const RegulatoryTrackerApp = () => {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [view, setView] = useState('login');
  const [user, setUser] = useState(null);
  const [preferences, setPreferences] = useState(null);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filterUnread, setFilterUnread] = useState(false);
  const [filterStarred, setFilterStarred] = useState(false);

  // Auth Forms
  const [authForm, setAuthForm] = useState({
    email: '',
    password: '',
    full_name: ''
  });

  useEffect(() => {
    if (token) {
      fetchUser();
      fetchPreferences();
      fetchReports();
    }
  }, [token]);

  const apiCall = async (endpoint, method = 'GET', body = null) => {
    const headers = {
      'Content-Type': 'application/json',
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
      method,
      headers,
    };

    if (body) {
      config.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_URL}${endpoint}`, config);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Request failed');
    }

    return response.json();
  };

  const handleRegister = async () => {
    setLoading(true);
    setError('');

    try {
      const data = await apiCall('/api/auth/register', 'POST', authForm);
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      setView('dashboard');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async () => {
    setLoading(true);
    setError('');

    try {
      const data = await apiCall('/api/auth/login', 'POST', {
        email: authForm.email,
        password: authForm.password
      });
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      setView('dashboard');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    setPreferences(null);
    setReports([]);
    setView('login');
  };

  const fetchUser = async () => {
    try {
      const data = await apiCall('/api/user/me');
      setUser(data);
    } catch (err) {
      console.error('Failed to fetch user:', err);
      handleLogout();
    }
  };

  const fetchPreferences = async () => {
    try {
      const data = await apiCall('/api/user/preferences');
      setPreferences(data);
    } catch (err) {
      console.error('Failed to fetch preferences:', err);
    }
  };

  const fetchReports = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterUnread) params.append('unread_only', 'true');
      if (filterStarred) params.append('starred_only', 'true');
      
      const data = await apiCall(`/api/reports?${params.toString()}`);
      setReports(data);
    } catch (err) {
      setError('Failed to load reports');
    } finally {
      setLoading(false);
    }
  };

  const updateReportStatus = async (reportId, updates) => {
    try {
      await apiCall(`/api/reports/${reportId}`, 'PATCH', updates);
      fetchReports();
    } catch (err) {
      console.error('Failed to update report:', err);
    }
  };

  const updatePreferences = async (updates) => {
    setLoading(true);
    try {
      const data = await apiCall('/api/user/preferences', 'PUT', updates);
      setPreferences(data);
      setError('');
      alert('Preferences updated successfully!');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token && view === 'dashboard') {
      fetchReports();
    }
  }, [filterUnread, filterStarred]);

  // Login/Register View
  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-3 bg-blue-600 rounded-lg">
              <Shield className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">RegTracker</h1>
              <p className="text-sm text-gray-600">Regulatory Intelligence</p>
            </div>
          </div>

          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setView('login')}
              className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                view === 'login' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'
              }`}
            >
              Login
            </button>
            <button
              onClick={() => setView('register')}
              className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                view === 'register' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'
              }`}
            >
              Register
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-4">
            {view === 'register' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Full Name</label>
                <input
                  type="text"
                  value={authForm.full_name}
                  onChange={(e) => setAuthForm({...authForm, full_name: e.target.value})}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
              <input
                type="email"
                value={authForm.email}
                onChange={(e) => setAuthForm({...authForm, email: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
              <input
                type="password"
                value={authForm.password}
                onChange={(e) => setAuthForm({...authForm, password: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <button
              onClick={view === 'login' ? handleLogin : handleRegister}
              disabled={loading}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {loading ? 'Processing...' : view === 'login' ? 'Login' : 'Create Account'}
            </button>
          </div>

          <div className="mt-6 p-4 bg-yellow-50 border-l-4 border-yellow-400 rounded text-sm text-yellow-800">
            <strong>Legal Disclaimer:</strong> This tool provides informational regulatory updates only and does not constitute legal advice.
          </div>
        </div>
      </div>
    );
  }

  // Settings View
  if (view === 'settings') {
    return (
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className="w-8 h-8 text-blue-600" />
              <h1 className="text-xl font-bold text-gray-900">RegTracker</h1>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={() => setView('dashboard')}
                className="text-gray-600 hover:text-gray-900"
              >
                Dashboard
              </button>
              <button onClick={handleLogout} className="text-red-600 hover:text-red-700">
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </nav>

        <div className="max-w-4xl mx-auto p-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Preferences</h2>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
                {error}
              </div>
            )}

            {preferences && (
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Jurisdiction</label>
                  <select
                    value={preferences.jurisdiction}
                    onChange={(e) => updatePreferences({ jurisdiction: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="EU">European Union</option>
                    <option value="DE">Germany</option>
                    <option value="FR">France</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Sectors of Interest</label>
                  <div className="grid grid-cols-2 gap-3">
                    {['IT', 'Finance', 'Healthcare', 'Manufacturing', 'Energy', 'Transport'].map(sector => (
                      <label key={sector} className="flex items-center gap-2 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                        <input
                          type="checkbox"
                          checked={preferences.sectors.includes(sector)}
                          onChange={(e) => {
                            const newSectors = e.target.checked
                              ? [...preferences.sectors, sector]
                              : preferences.sectors.filter(s => s !== sector);
                            updatePreferences({ sectors: newSectors });
                          }}
                          className="rounded text-blue-600"
                        />
                        <span className="text-sm text-gray-700">{sector}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Notification Frequency</label>
                  <select
                    value={preferences.notification_frequency}
                    onChange={(e) => updatePreferences({ notification_frequency: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={preferences.email_notifications}
                    onChange={(e) => updatePreferences({ email_notifications: e.target.checked })}
                    className="rounded text-blue-600"
                  />
                  <label className="text-sm text-gray-700">Enable email notifications</label>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Dashboard View
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className="w-8 h-8 text-blue-600" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">RegTracker</h1>
                <p className="text-sm text-gray-600">Welcome, {user?.full_name}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={() => setView('settings')}
                className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <Settings className="w-5 h-5" />
                <span className="hidden sm:inline">Settings</span>
              </button>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-4 py-2 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
              >
                <LogOut className="w-5 h-5" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto p-4 sm:p-6">
        <div className="mb-6 p-4 bg-yellow-50 border-l-4 border-yellow-400 rounded-lg">
          <p className="text-sm text-yellow-800">
            <strong>Legal Disclaimer:</strong> This tool provides informational regulatory updates only and does not constitute legal advice. Users should consult qualified legal professionals for compliance decisions.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <button
            onClick={() => setFilterUnread(!filterUnread)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              filterUnread ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border border-gray-300'
            }`}
          >
            <Eye className="w-4 h-4" />
            Unread Only
          </button>

          <button
            onClick={() => setFilterStarred(!filterStarred)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              filterStarred ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border border-gray-300'
            }`}
          >
            <Star className="w-4 h-4" />
            Starred Only
          </button>
        </div>

        {loading && reports.length === 0 ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading reports...</p>
          </div>
        ) : reports.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <Bell className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">No Reports Yet</h3>
            <p className="text-gray-600">Reports will appear here when new regulations matching your preferences are detected.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {reports.map(report => (
              <div
                key={report.id}
                className={`bg-white rounded-lg shadow-sm p-6 transition-all hover:shadow-md ${
                  !report.is_read ? 'border-l-4 border-blue-600' : ''
                }`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">{report.title}</h3>
                    <div className="flex flex-wrap gap-3 text-sm text-gray-600">
                      <span>🌍 {report.jurisdiction}</span>
                      <span>📅 {new Date(report.publication_date).toLocaleDateString()}</span>
                      <span>📄 {report.document_type}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                      report.relevance_score >= 0.7 ? 'bg-orange-100 text-orange-800' :
                      report.relevance_score >= 0.5 ? 'bg-yellow-100 text-yellow-800' :
                      'bg-green-100 text-green-800'
                    }`}>
                      {report.relevance_score >= 0.7 ? 'High' : report.relevance_score >= 0.5 ? 'Medium' : 'Low'} ({(report.relevance_score * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>

                {report.summary && report.summary.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-semibold text-gray-800 mb-2">Summary</h4>
                    <ul className="space-y-2">
                      {report.summary.map((point, idx) => (
                        <li key={idx} className="flex gap-2 text-gray-700">
                          <span className="text-blue-600">•</span>
                          <span className="text-sm">{point}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {report.relevance_explanation && (
                  <div className="mb-4 p-4 bg-blue-50 rounded-lg">
                    <h4 className="font-semibold text-gray-800 mb-2">Relevance</h4>
                    <p className="text-sm text-gray-700">{report.relevance_explanation}</p>
                  </div>
                )}

                {report.key_impacts && report.key_impacts.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-semibold text-gray-800 mb-2">Key Business Areas</h4>
                    <div className="flex flex-wrap gap-2">
                      {report.key_impacts.map((impact, idx) => (
                        <span key={idx} className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm">
                          {impact}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="pt-4 border-t border-gray-200 flex items-center justify-between">
                  <a
                    href={report.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                  >
                    View Official Document →
                  </a>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => updateReportStatus(report.id, { is_read: !report.is_read })}
                      className={`p-2 rounded-lg transition-colors ${
                        report.is_read ? 'text-blue-600 bg-blue-50' : 'text-gray-400 hover:bg-gray-100'
                      }`}
                      title={report.is_read ? 'Mark as unread' : 'Mark as read'}
                    >
                      <Eye className="w-5 h-5" />
                    </button>

                    <button
                      onClick={() => updateReportStatus(report.id, { is_starred: !report.is_starred })}
                      className={`p-2 rounded-lg transition-colors ${
                        report.is_starred ? 'text-yellow-500 bg-yellow-50' : 'text-gray-400 hover:bg-gray-100'
                      }`}
                      title={report.is_starred ? 'Remove star' : 'Star report'}
                    >
                      <Star className={`w-5 h-5 ${report.is_starred ? 'fill-current' : ''}`} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default RegulatoryTrackerApp;
