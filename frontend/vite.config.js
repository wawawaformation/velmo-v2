import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // Le front appelle /api/... en relatif ; Vite relaie vers l'API
      // FastAPI (make api / docker compose up api) — évite tout souci CORS
      // en dev, aucune URL en dur dans le code JS.
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
