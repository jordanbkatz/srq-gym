# SRQ Gym

Static Vite website for SRQ Health & Fitness.

## Local development

```sh
npm ci
npm run dev
```

## Cloudflare Pages

- GitHub repository: `jordanbkatz/srq-gym`
- Pages project: `sqr-gym`
- Production branch: `main`
- Root directory: repository root
- Build command: `npm run build`
- Build output directory: `dist`
- Node.js: 22 (selected by `.node-version`)
- Intended URL: `https://sqr-gym.pages.dev`

Cloudflare builds the site from source; no server process or Vite dev server is needed in production. `wrangler.toml` declares the Pages output directory and runtime compatibility date. Git-connected Pages deployments automatically build changes pushed to `main`.

The contact form currently shows a local success message only. It does not send email or store submissions.
