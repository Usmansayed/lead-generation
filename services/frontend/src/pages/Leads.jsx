import { useState, useEffect } from 'react'
import { leadAPI } from '../services/api'
import { Search, Filter, ExternalLink, RefreshCw } from 'lucide-react'

function Leads() {
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    status: '',
    platform: '',
    min_score: '',
  })

  const fetchLeads = async () => {
    try {
      setLoading(true)
      const data = await leadAPI.getLeads(filters)
      setLeads(data)
    } catch (err) {
      console.error('Failed to load leads:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLeads()
  }, [])

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const applyFilters = () => {
    fetchLeads()
  }

  const getScoreColor = (score) => {
    if (score >= 70) return 'text-green-600 bg-green-100'
    if (score >= 50) return 'text-yellow-600 bg-yellow-100'
    return 'text-red-600 bg-red-100'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Leads</h2>
        <button
          onClick={fetchLeads}
          className="flex items-center space-x-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200 mb-6">
        <div className="flex items-center space-x-2 mb-4">
          <Filter className="w-5 h-5 text-gray-500" />
          <h3 className="text-lg font-semibold text-gray-900">Filters</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Status
            </label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
            >
              <option value="">All</option>
              <option value="new">New</option>
              <option value="contacted">Contacted</option>
              <option value="qualified">Qualified</option>
              <option value="won">Won</option>
              <option value="lost">Lost</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Platform
            </label>
            <select
              value={filters.platform}
              onChange={(e) => handleFilterChange('platform', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
            >
              <option value="">All</option>
              <option value="reddit">Reddit</option>
              <option value="twitter">Twitter</option>
              <option value="hackernews">HackerNews</option>
              <option value="linkedin">LinkedIn</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Min Score
            </label>
            <input
              type="number"
              value={filters.min_score}
              onChange={(e) => handleFilterChange('min_score', e.target.value)}
              placeholder="0-100"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
            />
          </div>

          <div className="flex items-end">
            <button
              onClick={applyFilters}
              className="w-full px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              Apply Filters
            </button>
          </div>
        </div>
      </div>

      {/* Leads List */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-primary" />
        </div>
      ) : leads.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm p-12 border border-gray-200 text-center">
          <p className="text-gray-500 text-lg">No leads found</p>
          <p className="text-gray-400 mt-2">Try adjusting your filters or run a crawl</p>
        </div>
      ) : (
        <div className="space-y-4">
          {leads.map((lead) => (
            <div
              key={lead.lead_id}
              className="bg-white rounded-lg shadow-sm p-6 border border-gray-200 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getScoreColor(lead.lead_score)}`}>
                      {lead.lead_score}/100
                    </span>
                    <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm font-medium">
                      {lead.buying_intent}
                    </span>
                    <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
                      {lead.urgency}
                    </span>
                  </div>

                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    {lead.problem_analysis?.problem_summary || 'No title'}
                  </h3>

                  <p className="text-gray-700 mb-3">
                    {lead.problem_analysis?.business_context || 'No description'}
                  </p>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">Platform:</span>
                      <span className="ml-2 font-medium text-gray-900">{lead.platform}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Author:</span>
                      <span className="ml-2 font-medium text-gray-900">{lead.author}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Budget:</span>
                      <span className="ml-2 font-medium text-gray-900">
                        {lead.problem_analysis?.estimated_budget_range || 'Unknown'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Timeline:</span>
                      <span className="ml-2 font-medium text-gray-900">
                        {lead.problem_analysis?.timeline || 'Unknown'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="ml-4">
                  <a
                    href={lead.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                    <span>View Post</span>
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Leads
