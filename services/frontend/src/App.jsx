import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import RawPosts from './pages/RawPosts'
import FilterResults from './pages/FilterResults'
import QualifiedLeads from './pages/QualifiedLeads'
import EmailQueue from './pages/EmailQueue'
import SuppressionList from './pages/SuppressionList'
import PipelineState from './pages/PipelineState'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="raw-posts" element={<RawPosts />} />
          <Route path="filter-results" element={<FilterResults />} />
          <Route path="qualified" element={<QualifiedLeads />} />
          <Route path="email-queue" element={<EmailQueue />} />
          <Route path="suppression" element={<SuppressionList />} />
          <Route path="pipeline-state" element={<PipelineState />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
