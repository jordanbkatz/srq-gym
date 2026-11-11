import { defineConfig } from 'vite';
import { blogPlugin } from './scripts/blog-render.mjs';

export default defineConfig({
  plugins: [blogPlugin()],
  server: {
    host: true,
    port: 5173,
  },
});
