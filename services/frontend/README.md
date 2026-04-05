# Lead Generation Dashboard (React)

Modern, production-ready React dashboard for the lead generation system.

## Features

- ✅ **Dashboard** - Real-time stats and charts
- ✅ **Leads Management** - Browse, filter, and export leads
- ✅ **Sources** - Manage crawl sources and trigger crawls
- ✅ **Settings** - System configuration and info
- ✅ **Responsive Design** - Works on desktop and mobile
- ✅ **No Event Loop Issues** - Stable, production-ready

## Tech Stack

- **React 18** - Modern React with hooks
- **Vite** - Lightning-fast build tool
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Beautiful charts
- **Axios** - HTTP client for API calls
- **React Router** - Client-side routing

## Quick Start

### Install Dependencies (first time only)
```bash
cd services/frontend
npm install
```

### Start Development Server
```bash
npm run dev
```

Dashboard will open at **http://localhost:3000**

### Or Use Master Launcher
```bash
# From services/crawlee-python directory
python start_system.py
```

This starts:
- Autonomous crawler
- FastAPI backend
- React dashboard (auto-installs dependencies)

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── Layout.jsx          # Main layout with navigation
│   ├── pages/
│   │   ├── Dashboard.jsx       # Stats and charts
│   │   ├── Leads.jsx           # Leads list with filters
│   │   ├── Sources.jsx         # Sources management
│   │   └── Settings.jsx        # System settings
│   ├── services/
│   │   └── api.js              # API client for FastAPI backend
│   ├── App.jsx                 # Main app with routing
│   ├── main.jsx                # React entry point
│   └── index.css               # Global styles
├── index.html                  # HTML template
├── package.json                # Dependencies
├── vite.config.js              # Vite configuration
└── tailwind.config.js          # Tailwind configuration
```

## API Integration

The React app connects to the FastAPI backend at **http://localhost:8000**.

All API calls are proxied through Vite dev server:
- Frontend: `http://localhost:3000/api/leads`
- Backend: `http://localhost:8000/leads`

## Available Scripts

```bash
# Development server (port 3000)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Start (used by launcher)
npm run start
```

## Key Differences from Streamlit

### Streamlit (Old)
- ❌ Event loop issues on reload
- ❌ Python-based (slower)
- ❌ Limited customization
- ❌ Not production-ready

### React (New)
- ✅ No event loop issues
- ✅ Fast and responsive
- ✅ Fully customizable
- ✅ Production-ready
- ✅ Better developer experience

## Customization

### Colors
Edit `tailwind.config.js`:
```js
theme: {
  extend: {
    colors: {
      primary: '#1f77b4',  // Change this
      // ...
    }
  }
}
```

### Add New Pages
1. Create component in `src/pages/YourPage.jsx`
2. Add route in `src/App.jsx`
3. Add navigation link in `src/components/Layout.jsx`

### API Calls
All API functions are in `src/services/api.js`. Add new endpoints there.

## Deployment

### Build for Production
```bash
npm run build
```

Output will be in `dist/` directory.

### Serve Production Build
```bash
npm run preview
```

Or use any static file server:
```bash
npx serve dist
```

## Troubleshooting

### "npm not found"
Install Node.js from https://nodejs.org

### Port 3000 already in use
Kill the process using port 3000:
```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Mac/Linux
lsof -ti:3000 | xargs kill
```

### API calls failing
Make sure FastAPI backend is running on port 8000:
```bash
cd ../crawlee-python
python api_server.py
```

## License

Same as parent project.
