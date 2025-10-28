# LLMHub Web UI

Vue 3 + Vite management console for LLMHub.

## Features

- 📊 Dashboard with usage statistics
- 🤖 Provider and model management
- 🔑 API client and key management
- 📝 Prompt template viewer
- 💰 Billing and cost analytics

## Development

### Prerequisites

- Node.js 18+ and npm

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Opens on http://localhost:5173
# API calls are proxied to http://localhost:4000
```

### Building for Production

```bash
# Build optimized production bundle
npm run build

# Output goes to dist/
# FastAPI serves these files automatically
```

### Preview Production Build

```bash
# Build and preview
npm run build
npm run preview

# Opens on http://localhost:4173
```

## Project Structure

```
web-ui/
├── src/
│   ├── main.js              # App entry point, router setup
│   ├── App.vue              # Root component with navigation
│   ├── style.css            # Tailwind CSS styles
│   ├── api/
│   │   └── client.js        # Axios API client
│   └── views/               # Page components
│       ├── DashboardView.vue
│       ├── ProvidersView.vue
│       ├── APIClientsView.vue
│       ├── TemplatesView.vue
│       └── BillingView.vue
├── index.html               # HTML template
├── package.json             # Dependencies
├── vite.config.js           # Vite configuration
├── tailwind.config.js       # Tailwind CSS config
└── postcss.config.js        # PostCSS config
```

## Tech Stack

- **Vue 3** - Progressive JavaScript framework
- **Vite** - Fast build tool and dev server
- **Vue Router** - Client-side routing
- **Axios** - HTTP client
- **Tailwind CSS** - Utility-first CSS framework

## API Integration

The web UI calls these admin endpoints:

- `GET /api/v1/admin/stats` - Dashboard statistics
- `GET /api/v1/admin/providers` - Provider status
- `GET /api/v1/admin/clients` - List API clients
- `POST /api/v1/admin/clients` - Create client
- `DELETE /api/v1/admin/clients/{id}` - Delete client
- `POST /api/v1/admin/clients/{id}/regenerate-key` - Regenerate key
- `GET /api/v1/admin/billing/*` - Billing data
- `GET /api/v1/llm/prompts` - List templates

## Development Tips

### Hot Module Replacement

Vite provides instant hot module replacement. Changes to `.vue` files are reflected immediately without full page reload.

### API Proxy

The dev server (`npm run dev`) automatically proxies API requests:

```javascript
// vite.config.js
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:4000',
      changeOrigin: true
    }
  }
}
```

This means you can call `/api/v1/admin/stats` and it will be forwarded to `http://localhost:4000/api/v1/admin/stats`.

### Adding a New View

1. Create new component in `src/views/`:

```vue
<!-- src/views/NewView.vue -->
<template>
  <div>
    <h1>New View</h1>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

// Component logic here
</script>
```

2. Add route in `src/main.js`:

```javascript
const routes = [
  // ... existing routes
  {
    path: '/new',
    name: 'new',
    component: NewView,
    meta: { title: 'New View' }
  }
]
```

3. Add navigation link in `App.vue`:

```javascript
const navigation = ref([
  // ... existing items
  { name: 'New View', path: '/new' }
])
```

### Styling with Tailwind

Use Tailwind utility classes:

```vue
<template>
  <div class="card">
    <h2 class="text-lg font-semibold text-gray-900 mb-4">Title</h2>
    <button class="btn-primary">Click Me</button>
  </div>
</template>
```

Custom classes are defined in `src/style.css`:

- `.card` - White card with shadow
- `.btn-primary` - Blue primary button
- `.btn-secondary` - Gray secondary button
- `.badge-*` - Status badges (success, warning, danger)

## Building for Docker

The Dockerfile automatically includes the built web UI:

```bash
# 1. Build web UI
cd web-ui
npm run build

# 2. Build Docker image (from project root)
cd ..
docker build -t llmhub:latest .

# The dist/ folder is copied into the image
# FastAPI serves it at the root URL
```

## Troubleshooting

### Dependencies Won't Install

```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

### Dev Server Won't Start

```bash
# Check if port 5173 is in use
lsof -i :5173

# Change port in vite.config.js:
server: {
  port: 3000  // Use different port
}
```

### API Calls Failing in Dev

1. Ensure backend is running: `docker-compose up llmhub`
2. Check proxy configuration in `vite.config.js`
3. Check browser console for CORS errors

### Build Fails

```bash
# Check for TypeScript/linting errors
npm run build -- --debug

# Update dependencies
npm update
```

## Production Considerations

### Environment Variables

For production deployments with different API URLs:

```javascript
// vite.config.js
const apiUrl = process.env.VITE_API_URL || 'http://localhost:4000'

// Use in code:
const API_BASE_URL = import.meta.env.VITE_API_URL
```

Set in `.env.production`:

```
VITE_API_URL=https://llmhub.yourdomain.com
```

### Performance

The production build:

- Minifies JavaScript and CSS
- Code-splits vendor libraries
- Tree-shakes unused code
- Optimizes assets

Typical build size: ~150KB gzipped

### Browser Support

Supports modern browsers:

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## License

UNLICENSED - Internal project
