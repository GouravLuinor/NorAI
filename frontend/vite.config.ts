import { defineConfig, searchForWorkspaceRoot } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: '..',
  server: {
    fs: {
      allow: [
        // Dynamically allows the root project directory and node_modules
        searchForWorkspaceRoot(process.cwd())
      ],
    },
    proxy: {
      '/process': 'http://localhost:8000',
      '/estimate': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/chat/stream': 'http://localhost:8000',
      '/quiz': 'http://localhost:8000',
      '/flashcards': 'http://localhost:8000',
      '/summary': 'http://localhost:8000',
      '/notes': 'http://localhost:8000',
      '/screenshots': 'http://localhost:8000',
      '/threads': 'http://localhost:8000',
      '/download': 'http://localhost:8000',
      '/lectures': 'http://localhost:8000',
      // /courses is BOTH an SPA route and an API endpoint: bypass the proxy for
      // HTML navigations (serve the app), proxy JSON fetches to the backend.
      '/courses': {
        target: 'http://localhost:8000',
        bypass: (req) =>
          (req.headers.accept ?? '').includes('text/html') ? '/index.html' : undefined,
      },
      // /share is BOTH an SPA route (viewer landing) and an API endpoint
      // (slug resolution): same HTML-bypass trick as /billing and /usage.
      '/share': {
        target: 'http://localhost:8000',
        bypass: (req) =>
          (req.headers.accept ?? '').includes('text/html') ? '/index.html' : undefined,
      },
      '/static': 'http://localhost:8000',
      '/outline': 'http://localhost:8000',
      '/video-map': 'http://localhost:8000',
      '/study-guide': 'http://localhost:8000',
      '/concept-map': 'http://localhost:8000',
      '/quota': 'http://localhost:8000',
      // /billing is BOTH an SPA route and an API endpoint: bypass the proxy for
      // HTML navigations (serve the app), proxy JSON fetches (Accept: */*) to
      // the backend.
      '/billing': {
        target: 'http://localhost:8000',
        bypass: (req) =>
          (req.headers.accept ?? '').includes('text/html') ? '/index.html' : undefined,
      },
      // /usage is BOTH an SPA route and an API endpoint — same bypass trick.
      '/usage': {
        target: 'http://localhost:8000',
        bypass: (req) =>
          (req.headers.accept ?? '').includes('text/html') ? '/index.html' : undefined,
      },
    },
  },
})