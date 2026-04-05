import { useState, useEffect } from 'react'
import { leadAPI } from '../services/api'
import { RefreshCw, Plus, Trash2, Play } from 'lucide-react'

function Sources() {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [crawling, setCrawling] = useState(false)

  const fetchSources = async () => {
    try {
      setLoading(true)
      const data = await leadAPI.getSources()
      setSources(data)
    } catch (err) {
      console.error('Failed to load sources:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSources()
  }, [])

  const handleCrawl = async () => {
    if (crawling) return

    try {
      setCrawling(true)
      await leadAPI.triggerCrawl()
      alert('Crawl started! Check back in a few minutes for results.')
    } catch (err) {
      alert('Failed to start crawl: ' + err.message)
    } finally {
      setCrawling(false)
    }
  }

  const getPriorityColor = (priority) => {
    if (priority >= 8) return 'bg-red-100 text-red-700'
    if (priority >= 5) return 'bg-yellow-100 text-yellow-700'
    return 'bg-green-100 text-green-700'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Sources</h2>
        <div className="flex space-x-3">
          <button
            onClick={handleCrawl}
            disabled={crawling}
            className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {crawling ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            <span>{crawling ? 'Crawling...' : 'Run Crawl'}</span>
          </button>
          <button
            onClick={fetchSources}
            className="flex items-center space-x-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <p className="text-sm text-gray-600 mb-1">Total Sources</p>
          <p className="text-3xl font-bold text-gray-900">{sources.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <p className="text-sm text-gray-600 mb-1">Enabled</p>
          <p className="text-3xl font-bold text-green-600">
            {sources.filter((s) => s.enabled).length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <p className="text-sm text-gray-600 mb-1">Platforms</p>
          <p className="text-3xl font-bold text-blue-600">
            {new Set(sources.map((s) => s.platform)).size}
          </p>
        </div>
      </div>

      {/* Sources List */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-primary" />
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Source
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Platform
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Priority
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Posts Found
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Leads
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sources.map((source) => (
                <tr key={source.source_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      {source.identifier}
                    </div>
                    <div className="text-xs text-gray-500">
                      {source.keywords?.length || 0} keywords
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 rounded">
                      {source.platform}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs font-medium rounded ${getPriorityColor(source.priority)}`}>
                      Priority {source.priority}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded ${
                        source.enabled
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {source.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {source.total_posts_found || 0}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {source.total_leads_generated || 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default Sources
