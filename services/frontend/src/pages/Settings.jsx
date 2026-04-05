import { Server, Database, Key, Zap } from 'lucide-react'

function Settings() {
  return (
    <div>
      <h2 className="text-3xl font-bold text-gray-900 mb-8">Settings</h2>

      <div className="space-y-6">
        {/* System Info */}
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center space-x-3 mb-4">
            <Server className="w-6 h-6 text-primary" />
            <h3 className="text-lg font-semibold text-gray-900">System Information</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-600">API Server</p>
              <p className="text-base font-medium text-gray-900">http://localhost:8000</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Frontend</p>
              <p className="text-base font-medium text-gray-900">http://localhost:3000</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Database</p>
              <p className="text-base font-medium text-gray-900">MongoDB (localhost:27017)</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Cache</p>
              <p className="text-base font-medium text-gray-900">Redis (localhost:6379)</p>
            </div>
          </div>
        </div>

        {/* Crawling Config */}
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center space-x-3 mb-4">
            <Zap className="w-6 h-6 text-primary" />
            <h3 className="text-lg font-semibold text-gray-900">Crawling Configuration</h3>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-sm text-gray-600">Total Sources</p>
              <p className="text-base font-medium text-gray-900">134 enabled sources</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Keywords</p>
              <p className="text-base font-medium text-gray-900">4200+ keywords in 62 clusters</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Proxies</p>
              <p className="text-base font-medium text-gray-900">10 rotating proxies with health tracking</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Crawl Frequency</p>
              <p className="text-base font-medium text-gray-900">Every 6 hours (autonomous)</p>
            </div>
          </div>
        </div>

        {/* AI Configuration */}
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center space-x-3 mb-4">
            <Key className="w-6 h-6 text-primary" />
            <h3 className="text-lg font-semibold text-gray-900">AI Configuration</h3>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-sm text-gray-600">AI Provider</p>
              <p className="text-base font-medium text-gray-900">Google Gemini 2.5 Flash</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">API Keys</p>
              <p className="text-base font-medium text-gray-900">3 keys configured</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Rate Limit</p>
              <p className="text-base font-medium text-gray-900">45 requests/minute (15 RPM per key)</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Analysis Features</p>
              <p className="text-base font-medium text-gray-900">
                Buying intent detection, lead scoring, budget estimation, urgency detection
              </p>
            </div>
          </div>
        </div>

        {/* Documentation */}
        <div className="bg-blue-50 rounded-lg p-6 border border-blue-200">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">Documentation</h3>
          <p className="text-blue-700 mb-4">
            For detailed setup instructions and configuration options, refer to the README files in the project directory.
          </p>
          <div className="flex space-x-3">
            <a
              href="/api/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              API Documentation
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings
