import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // `loadEnv` is used rather than `process.env` so the value can come from a
  // `.env` / `.env.local` file, matching how the rest of the project is
  // configured. The default is the local FastAPI backend.
  const env = loadEnv(mode, import.meta.dirname, '')
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname, './src'),
      },
    },
    server: {
      port: 5173,
      proxy: {
        // The application calls the relative path `/api/v1/...`; this proxy is
        // the only place the backend's host and port are named in development.
        // Production resolves the same relative path through Nginx instead —
        // see docker/ and frontend/nginx.conf.
        //
        // Overridable via VITE_API_PROXY_TARGET so the backend can run on a
        // different host or port without editing code.
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
