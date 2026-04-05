import axios from 'axios'

const API_BASE_URL = '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

export const dashboardAPI = {
  getHealth() {
    return api.get('/health').then(r => r.data)
  },
  getStats() {
    return api.get('/stats').then(r => r.data)
  },
  getRawPosts({ status, platform, limit = 50, skip = 0 } = {}) {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (platform) params.set('platform', platform)
    params.set('limit', limit)
    params.set('skip', skip)
    return api.get(`/raw_posts?${params}`).then(r => r.data)
  },
  getRawPost(id) {
    return api.get(`/raw_posts/${encodeURIComponent(id)}`).then(r => r.data)
  },
  getQualifiedLeads({ limit = 50, skip = 0 } = {}) {
    return api.get(`/qualified_leads?limit=${limit}&skip=${skip}`).then(r => r.data)
  },
  getQualifiedLead(id) {
    return api.get(`/qualified_leads/${encodeURIComponent(id)}`).then(r => r.data)
  },
  getEmailQueue({ status, limit = 50, skip = 0 } = {}) {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    params.set('limit', limit)
    params.set('skip', skip)
    return api.get(`/email_queue?${params}`).then(r => r.data)
  },
  getPipelineState() {
    return api.get('/pipeline_state').then(r => r.data)
  },
  getSuppressionList({ limit = 100, skip = 0 } = {}) {
    return api.get(`/suppression_list?limit=${limit}&skip=${skip}`).then(r => r.data)
  },
}

export default api
