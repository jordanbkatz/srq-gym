# SRQ Gym

Static Vite website for SRQ Health & Fitness.

## Local development

```sh
npm ci
npm run dev
```

The blog archive is available at `/blog-personal-training-sarasota-fit`. Each
article keeps its original `/post/<slug>` URL. Vite serves these pages during
development and generates their complete static HTML, metadata, and sitemap for
production. The archive supports search, year filters, and pagination; all links
and article content are present even without JavaScript.

The migration includes all 137 original posts published from January 2020 through
November 2026. `content/blog-posts.json` retains the original wording, metadata,
captions, image descriptions, and source URLs. `content/blog-image-manifest.json`
maps source images to local WebP files. Article images are at most 1440px wide;
640px variants, responsive sources, and lazy loading keep page downloads small.

To refresh from the original website and verify the migration:

```sh
python3 scripts/import-blog.py
python3 scripts/optimize-blog-images.py
npm run build
python3 scripts/verify-blog.py --build-dir dist --report content/blog-migration-report.json
```

The import and verification scripts use Python's standard library. Image
conversion additionally requires ImageMagick (`magick`) and Google's `cwebp`.
Original responses and full-resolution downloads are cached in the system
temporary directory, outside this repository. Verification compares every
article's text and formatting with its source and checks the built article routes
and local WebP assets. The checked-in report records the latest result.

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
