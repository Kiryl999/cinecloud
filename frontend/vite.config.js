import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // same origin as behind the ingress: the browser only ever talks to /api
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
