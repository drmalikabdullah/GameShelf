import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// This app is served by the Flask backend at /museum/ (not the site root),
// and its build output lands directly in static/museum so app.py can serve
// it with zero extra wiring beyond the route added in app.py. The dev
// server proxies /api and /covers etc. to the Flask dev server so `npm run
// dev` can hit real game data without CORS setup.
export default defineConfig({
  base: '/museum/',
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../static/museum',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/covers': 'http://127.0.0.1:5000',
      '/heroes': 'http://127.0.0.1:5000',
      '/screenshots': 'http://127.0.0.1:5000',
    },
  },
})
