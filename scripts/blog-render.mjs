import fs from 'node:fs';
import path from 'node:path';

export const blogPath = '/blog-personal-training-sarasota-fit';
const origin = 'https://www.srqhealthandfitness.com';
const root = path.resolve(import.meta.dirname, '..');
export const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const date = value => new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(new Date(value));
const articlePath = post => `/post/${post.slug}`;

export function readBlog() {
  const posts = JSON.parse(fs.readFileSync(path.join(root, 'content/blog-posts.json'), 'utf8'));
  const images = JSON.parse(fs.readFileSync(path.join(root, 'content/blog-image-manifest.json'), 'utf8'));
  if (posts.length === 0) throw new Error('The blog archive is empty.');
  return { posts, images };
}

function imageFor(source, images) {
  const image = images[source];
  if (!image) throw new Error(`Blog image has not been migrated: ${source}`);
  return image;
}

function responsiveSources(image) {
  return image.cardWidth === image.width ? `${image.src} ${image.width}w` : `${image.cardSrc} ${image.cardWidth}w, ${image.src} ${image.width}w`;
}

function cover(post, images, featured = false) {
  if (!post.coverImage?.src) return '';
  const image = imageFor(post.coverImage.src, images);
  return `<img src="${escapeHtml(image.cardSrc)}" srcset="${escapeHtml(responsiveSources(image))}" sizes="${featured ? '(max-width: 768px) 100vw, 60vw' : '(max-width: 500px) 100vw, (max-width: 900px) 50vw, 33vw'}" width="${image.cardWidth}" height="${image.cardHeight}" alt="${escapeHtml(post.coverImage.alt)}" loading="lazy" decoding="async">`;
}

function featuredPost(post, images, index) {
  return `<a class="blog-featured" href="${articlePath(post)}">
    ${cover(post, images, index === 0)}
    <div class="blog-featured-copy">${index === 0 ? '<span class="blog-featured-label">Latest article</span>' : ''}
      <h3>${escapeHtml(post.title)}</h3>
      <div class="blog-meta"><time datetime="${escapeHtml(post.publishedAt)}">${date(post.publishedAt)}</time> · ${post.readingMinutes} min read</div>
    </div>
  </a>`;
}

function postCard(post, images) {
  const search = `${post.title} ${post.excerpt}`.toLocaleLowerCase();
  return `<article class="blog-card" data-blog-card data-year="${post.publishedAt.slice(0, 4)}" data-search="${escapeHtml(search)}">
    <a class="blog-card-link" href="${articlePath(post)}">
      <div class="blog-photo">${cover(post, images)}</div>
      <div class="blog-body">
        <h3>${escapeHtml(post.title)}</h3>
        <p>${escapeHtml(post.excerpt)}</p>
        <div class="blog-meta">${escapeHtml(post.author)}<br><time datetime="${escapeHtml(post.publishedAt)}">${date(post.publishedAt)}</time> · ${post.readingMinutes} min read</div>
        <span class="blog-read">Read article →</span>
      </div>
    </a>
  </article>`;
}

export function archiveMarkup({ posts, images }) {
  const years = [...new Set(posts.map(post => post.publishedAt.slice(0, 4)))].sort().reverse();
  return `<header class="blog-intro"><div class="inner">
      <p class="label">Tips from our trainers</p>
      <h1 class="big-title">Know more.<br><span>Train better.</span></h1>
      <p class="blog-intro-copy">Training advice, healthy habits, and stories from SRQ Health & Fitness Studio. Explore the full archive.</p>
    </div></header>
    <section class="section blog-archive" data-blog-archive aria-label="Blog articles"><div class="inner">
      <div class="blog-featured-grid">${posts.slice(0, 3).map((post, index) => featuredPost(post, images, index)).join('\n')}</div>
      <div class="blog-toolbar" id="all-articles" style="scroll-margin-top:110px">
        <h2>All articles</h2>
        <div class="blog-controls">
          <label for="blog-search">Search articles<input id="blog-search" type="search" placeholder="Search by title or topic" autocomplete="off"></label>
          <label for="blog-year">Year<select id="blog-year"><option value="">All years</option>${years.map(year => `<option value="${year}">${year}</option>`).join('')}</select></label>
        </div>
      </div>
      <p class="blog-results-count" data-blog-count role="status" aria-live="polite" tabindex="-1">${posts.length} articles</p>
      <div class="blog-grid">${posts.map(post => postCard(post, images)).join('\n')}</div>
      <p class="blog-empty" data-blog-empty hidden>No articles match your search. Try another topic or choose a different year.</p>
      <nav class="blog-pagination" data-blog-pagination aria-label="Article pages" hidden>
        <button type="button" data-previous>← Previous</button><span data-page-label></span><button type="button" data-next>Next →</button>
      </nav>
    </div></section>`;
}

export function renderHome(template, data) {
  return template.replace('<!-- BLOG_CONTENT -->', archiveMarkup(data));
}

function shell(template, body, title, description, pathname, structuredData, image) {
  let head = template.slice(0, template.indexOf('<body>'));
  const header = template.slice(template.indexOf('<body>') + 6, template.indexOf('  <!-- ═══════════════ HOME'));
  const footer = template.slice(template.indexOf('  <!-- FOOTER -->'));
  head = head.replace(/<title>[\s\S]*?<\/title>/, () => `<title>${escapeHtml(title)}</title>`)
    .replace(/(<meta name="description" content=")[^"]*/, (_, prefix) => prefix + escapeHtml(description))
    .replace(/(<link rel="canonical" href=")[^"]*/, (_, prefix) => prefix + origin + pathname)
    .replace(/(<meta property="og:title" content=")[^"]*/, (_, prefix) => prefix + escapeHtml(title))
    .replace(/(<meta property="og:description" content=")[^"]*/, (_, prefix) => prefix + escapeHtml(description))
    .replace(/(<meta property="og:url" content=")[^"]*/, (_, prefix) => prefix + origin + pathname)
    .replace(/(<meta name="twitter:title" content=")[^"]*/, (_, prefix) => prefix + escapeHtml(title))
    .replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>/g, '');
  if (image) {
    head = head.replace(/(<meta (?:property="og:image"|name="twitter:image") content=")[^"]*/g, `$1${origin}${image.src}`)
      .replace(/(<meta property="og:image:width" content=")[^"]*/, `$1${image.width}`)
      .replace(/(<meta property="og:image:height" content=")[^"]*/, `$1${image.height}`);
  }
  if (pathname.startsWith('/post/')) head = head.replace('property="og:type" content="website"', 'property="og:type" content="article"');
  head = head.replace('</head>', () => `<script type="application/ld+json">${JSON.stringify(structuredData).replace(/</g, '\\u003c')}</script>\n</head>`);
  return `${head}<body>${header}${body}${footer}`
    .replace(/<a href="#"([^>]*onclick="showPage\('(home|about|services|contact)'\)[^>]*>)/g, (_, attributes, name) => `<a href="/${name === 'home' ? '' : `#${name}`}"${attributes}`)
    .replace(/(<a [^>]*)( class="active")([^>]*>Home<\/a>)/, '$1$3')
    .replace(/(<a [^>]*href="\/blog-personal-training-sarasota-fit")/, '$1 class="active"');
}

export function renderArchive(template, data) {
  const content = renderHome(template, data);
  const start = content.indexOf('  <div id="page-blog"');
  const end = content.indexOf('</div><!-- END BLOG -->', start) + '</div><!-- END BLOG -->'.length;
  const body = content.slice(start, end).replace('class="page"', 'class="page active"').replace('loading="lazy"', 'loading="eager" fetchpriority="high"');
  return shell(template, body, 'Blog | SRQ Health & Fitness Studio', 'Explore personal training, fitness, nutrition, and healthy aging articles from SRQ Health & Fitness Studio in Sarasota.', blogPath, {
    '@context': 'https://schema.org', '@type': 'Blog', name: 'SRQ Health & Fitness Blog', url: `${origin}${blogPath}`,
    blogPost: data.posts.map(post => ({ '@type': 'BlogPosting', headline: post.title, url: `${origin}${articlePath(post)}`, datePublished: post.publishedAt })),
  }, data.posts[0]?.coverImage?.src ? imageFor(data.posts[0].coverImage.src, data.images) : undefined);
}

export function localArticleHtml(post, data) {
  let imageIndex = 0;
  return post.html.replace(/<img\b[^>]*>/g, tag => {
    const remote = tag.match(/\bsrc="([^"]*)"/)?.[1]?.replace(/&amp;/g, '&');
    const image = imageFor(remote, data.images);
    return tag.replace(/\s(?:src|srcset|sizes|width|height|loading|decoding)="[^"]*"/g, '')
      .replace(/>$/, ` src="${image.src}" srcset="${responsiveSources(image)}" sizes="(max-width: 800px) calc(100vw - 40px), 736px" width="${image.width}" height="${image.height}" loading="${imageIndex++ === 0 ? 'eager' : 'lazy'}" decoding="async">`);
  }).replace(/\bhref="([^"]*)"/g, (attribute, href) => {
    let url;
    try { url = new URL(href.replace(/&amp;/g, '&'), post.sourceUrl); } catch { return attribute; }
    if (!['www.srqhealthandfitness.com', 'srqhealthandfitness.com'].includes(url.hostname)) return attribute;
    const knownPages = { '/': '/', '/who-we-are': '/#about', '/who-we-are-personal-trainer': '/#about', '/what-we-do': '/#services', '/what-we-do-personal-trainers': '/#services', '/contact': '/#contact', '/contact-1': '/#contact', '/contact-personal-trainer-sarasota': '/#contact', '/book-a-session': '/#contact', '/book-a-session-with-personal-traine': '/#contact', [blogPath]: blogPath };
    const target = knownPages[url.pathname.replace(/\/$/, '') || '/'] ?? (url.pathname.startsWith(`${blogPath}/hashtags/`) ? blogPath : data.posts.some(candidate => articlePath(candidate) === url.pathname.replace(/\/$/, '')) ? url.pathname : null);
    return target ? `href="${escapeHtml(target + (target.includes('#') ? '' : url.hash))}"` : attribute;
  });
}

export function renderPost(template, post, data) {
  const index = data.posts.indexOf(post);
  const newer = data.posts[index - 1];
  const older = data.posts[index + 1];
  const html = localArticleHtml(post, data);
  const updated = post.updatedAt && post.updatedAt.slice(0, 10) !== post.publishedAt.slice(0, 10);
  const body = `<main id="page-post" class="page active">
    <article>
      <header class="post-header">
        <a class="post-back" href="${blogPath}">← All articles</a>
        <p class="label">SRQ Health & Fitness Blog</p>
        <h1>${escapeHtml(post.title)}</h1>
        <div class="post-meta"><span>${escapeHtml(post.author)}</span><time datetime="${escapeHtml(post.publishedAt)}">${date(post.publishedAt)}</time><span>${post.readingMinutes} min read</span></div>
        ${updated ? `<p class="post-updated">Updated: <time datetime="${escapeHtml(post.updatedAt)}">${date(post.updatedAt)}</time></p>` : ''}
      </header>
      <div class="post-content">${html}</div>
    </article>
    <nav class="post-navigation" aria-label="More articles">
      ${newer ? `<a href="${articlePath(newer)}"><span>← Newer article</span>${escapeHtml(newer.title)}</a>` : ''}
      ${older ? `<a href="${articlePath(older)}"><span>Older article →</span>${escapeHtml(older.title)}</a>` : ''}
    </nav>
  </main>`;
  const image = post.coverImage?.src ? imageFor(post.coverImage.src, data.images) : undefined;
  return shell(template, body, `${post.title} | SRQ Health & Fitness`, post.excerpt, articlePath(post), [
    { '@context': 'https://schema.org', '@type': 'BlogPosting', headline: post.title, description: post.excerpt, datePublished: post.publishedAt, dateModified: post.updatedAt || post.publishedAt, author: { '@type': 'Organization', name: post.author }, publisher: { '@type': 'Organization', name: 'SRQ Health & Fitness Studio' }, mainEntityOfPage: `${origin}${articlePath(post)}`, ...(image ? { image: `${origin}${image.src}` } : {}) },
    { '@context': 'https://schema.org', '@type': 'BreadcrumbList', itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: `${origin}/` },
      { '@type': 'ListItem', position: 2, name: 'Blog', item: `${origin}${blogPath}` },
      { '@type': 'ListItem', position: 3, name: post.title, item: `${origin}${articlePath(post)}` },
    ] },
  ], image);
}

export function blogPlugin() {
  let data;
  let template;
  return {
    name: 'srq-blog-static-pages',
    buildStart() { data = readBlog(); template = fs.readFileSync(path.join(root, 'index.html'), 'utf8'); },
    transformIndexHtml(html) { return renderHome(html, readBlog()); },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const pathname = new URL(req.url, 'http://localhost').pathname.replace(/\/$/, '');
        if (pathname.startsWith(`${blogPath}/hashtags/`)) {
          res.statusCode = 302;
          res.setHeader('Location', blogPath);
          res.end();
          return;
        }
        if (pathname !== blogPath && !pathname.startsWith('/post/')) return next();
        try {
          const current = readBlog();
          const source = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
          const post = current.posts.find(candidate => articlePath(candidate) === pathname);
          if (pathname !== blogPath && !post) { res.statusCode = 404; res.end('Article not found'); return; }
          res.setHeader('Content-Type', 'text/html; charset=utf-8');
          res.end(post ? renderPost(source, post, current) : renderArchive(source, current));
        } catch (error) { next(error); }
      });
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: `${blogPath.slice(1)}/index.html`, source: renderArchive(template, data) });
      for (const post of data.posts) this.emitFile({ type: 'asset', fileName: `post/${post.slug}/index.html`, source: renderPost(template, post, data) });
      const entries = ['/', blogPath, ...data.posts.map(articlePath)];
      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${entries.map(url => `<url><loc>${escapeHtml(origin + url)}</loc></url>`).join('')}</urlset>\n` });
    },
  };
}
