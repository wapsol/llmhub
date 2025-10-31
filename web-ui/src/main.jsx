import { render } from 'preact'
import { Router } from 'preact-router'
import App from './App'
import './style.css'

// Import views
import DashboardView from './views/DashboardView'
import ProvidersView from './views/ProvidersView'
import ModelsView from './views/ModelsView'
import APIClientsView from './views/APIClientsView'
import TemplatesView from './views/TemplatesView'
import BillingView from './views/BillingView'

// Create router component with App wrapper
function AppWithRouter() {
  // Update page title on route change
  const handleRoute = (e) => {
    const routes = {
      '/': 'Dashboard',
      '/providers': 'Provider Management',
      '/models': 'Models',
      '/clients': 'API Clients',
      '/templates': 'Prompt Templates',
      '/billing': 'Billing & Usage'
    }
    document.title = `${routes[e.url] || 'LLMHub'} - LLMHub`
  }

  return (
    <App>
      <Router onChange={handleRoute}>
        <DashboardView path="/" />
        <ProvidersView path="/providers" />
        <ModelsView path="/models" />
        <APIClientsView path="/clients" />
        <TemplatesView path="/templates" />
        <BillingView path="/billing" />
      </Router>
    </App>
  )
}

// Render app
render(<AppWithRouter />, document.getElementById('app'))
