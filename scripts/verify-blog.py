#!/usr/bin/env python3
"""Verify migrated articles against cached original Wix HTML and the live archive.

Run after import/build: python3 scripts/verify-blog.py --source-dir /tmp/srq-blog-source
The import script retains original responses in that directory by default.
"""
from __future__ import annotations
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
BLOCKS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'figcaption', 'td', 'th', 'tr', 'table', 'ul', 'ol', 'figure', 'br', 'hr'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
IGNORED = {'script', 'style', 'svg', 'button'}

def media_key(s):
    m = re.search(r'/media/([^/?]+)', s or '')
    return m.group(1) if m else s

def normalize(s):
    return re.sub(r'\s+', ' ', s).strip()

class ArticleParser(HTMLParser):
    def __init__(self, source=False, built=False):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.built = built
        self.container_tag = 'section' if source else 'div'
        self.active = not (source or built)
        self.section_depth = 0
        self.ignored = []
        self.text = []
        self.images = []
        self.tags = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if (self.source and tag == 'section' and attrs.get('data-hook') == 'post-description') or (self.built and tag == 'div' and 'post-content' in attrs.get('class','').split()):
            self.active = True
            self.section_depth = 1
            return
        if not self.active:
            return
        if (self.source or self.built) and tag == self.container_tag:
            self.section_depth += 1
        if tag in IGNORED:
            self.ignored.append(tag)
        if self.ignored:
            return
        self.tags[tag] = self.tags.get(tag, 0) + 1
        if tag in BLOCKS:
            self.text.append(' ')
        if tag == 'img':
            self.images.append(attrs)
        if tag == 'a':
            self.links.append(attrs.get('href', ''))

    def handle_endtag(self, tag):
        if not self.active:
            return
        if tag in IGNORED and self.ignored and self.ignored[-1] == tag:
            self.ignored.pop()
            return
        if self.ignored:
            return
        if (self.source or self.built) and tag == self.container_tag:
            self.section_depth -= 1
            if not self.section_depth:
                self.active = False
                return
        if tag in BLOCKS:
            self.text.append(' ')

    def handle_data(self, data):
        if self.active and not self.ignored:
            self.text.append(data)

    @property
    def plain(self):
        return normalize(''.join(self.text))


def compare(posts, source_dir, archive_path=None):
    errors = []
    total_source_images = 0
    total_source_tables = 0
    total_words = 0
    source_slugs = {p.stem for p in source_dir.glob('*.html') if not re.fullmatch(r'archive-page-\d+',p.stem)}
    slugs = [p['slug'] for p in posts]
    if len(slugs) != len(set(slugs)):
        errors.append('Duplicate migrated slugs')
    if source_slugs != set(slugs):
        errors.append(f'Source/migrated slug sets differ: missing {sorted(source_slugs-set(slugs))}, extra {sorted(set(slugs)-source_slugs)}')
    archive = None
    if archive_path and archive_path.exists():
        archive = {p['slug']: p for p in json.loads(archive_path.read_text())}
        if set(archive) != set(slugs):
            errors.append('Complete archive and migrated slug sets differ')
    for post in posts:
        slug = post['slug']
        path = source_dir / f'{slug}.html'
        if not path.exists():
            continue
        source = ArticleParser(source=True)
        source.feed(path.read_text())
        target = ArticleParser()
        target.feed(post['html'])
        if source.plain != target.plain:
            a, b = source.plain, target.plain
            pos = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a),len(b)))
            errors.append(f'{slug}: body text differs at character {pos} (source {len(a)}, target {len(b)} characters)')
        if len(source.images) != len(target.images):
            errors.append(f'{slug}: image count differs ({len(source.images)} vs {len(target.images)})')
        for tag in ['table','tr','td','th','ul','ol','li','figcaption','blockquote','h1','h2','h3','h4','h5','h6']:
            if source.tags.get(tag,0) != target.tags.get(tag,0):
                errors.append(f'{slug}: {tag} count differs ({source.tags.get(tag,0)} vs {target.tags.get(tag,0)})')
        if source.links != target.links:
            errors.append(f'{slug}: original link destinations differ')
        for a,b in zip(source.images,target.images):
            if media_key(a.get('src','')) != media_key(b.get('src','')):
                errors.append(f'{slug}: original inline image source differs')
            if a.get('alt','') != b.get('alt',''):
                errors.append(f'{slug}: image alt text differs')
        if archive:
            original = archive.get(slug,{})
            image = original.get('media',{}).get('wixMedia',{}).get('image',{})
            if image and media_key(image.get('url','')) != media_key(post.get('coverImage',{}).get('src','')):
                errors.append(f'{slug}: original cover image differs')
            if original.get('owner',{}).get('name') != post.get('author'):
                errors.append(f'{slug}: author differs from archive')
            if original.get('minutesToRead') != post.get('readingMinutes'):
                errors.append(f'{slug}: reading time differs from archive')
            if original.get('title') != post.get('title'):
                errors.append(f'{slug}: title differs from complete archive')
            if original.get('excerpt') != post.get('excerpt'):
                errors.append(f'{slug}: excerpt differs from complete archive')
            for original_key,target_key in [('firstPublishedDate','publishedAt'),('lastPublishedDate','updatedAt')]:
                if original.get(original_key) != post.get(target_key):
                    errors.append(f'{slug}: {target_key} differs from archive')
        total_source_images += len(source.images)
        total_source_tables += source.tags.get('table',0)
        total_words += len(source.plain.split())
    return {
        'postCount': len(posts),
        'sourceCount': len(source_slugs),
        'archiveCount':len(archive) if archive else None,
        'sourceInlineImageOccurrences':total_source_images,
        'sourceTables':total_source_tables,
        'sourceWords':total_words,
        'checks': ['all article text (whitespace normalized only)', 'unique and complete slug set', 'titles, excerpts and dates vs complete archive when supplied', 'inline image count and alt text', 'heading, list, table, caption, blockquote and link counts'],
        'errors': errors,
        'passed': not errors,
    }


def check_build(posts, build_dir):
    errors = []
    checked_images = set()
    checked_routes = 0
    for post in posts:
        slug = post['slug']
        path = build_dir/'post'/slug/'index.html'
        if not path.is_file():
            errors.append(f'{slug}: built route missing')
            continue
        html = path.read_text()
        actual = ArticleParser(built=True)
        actual.feed(html)
        expected = ArticleParser()
        expected.feed(post['html'])
        if actual.plain != expected.plain:
            errors.append(f'{slug}: built article body text differs from verified migrated content')
        for tag in ['img','table','tr','td','th','ul','ol','li','figcaption','blockquote','h1','h2','h3','h4','h5','h6','a']:
            if expected.tags.get(tag,0) != actual.tags.get(tag,0):
                errors.append(f'{slug}: built {tag} count differs')
        for original,image in zip(expected.images,actual.images):
            if original.get('alt','') != image.get('alt',''):
                errors.append(f'{slug}: built inline image alt differs')
            src = image.get('src','')
            if not src.startswith('/images/blog/') or not src.endswith('.webp'):
                errors.append(f'{slug}: built inline image is not local WebP')
            elif not (build_dir/src.lstrip('/')).is_file():
                errors.append(f'{slug}: built image file missing: {src}')
            else:
                checked_images.add(src)
            if not image.get('width') or not image.get('height'):
                errors.append(f'{slug}: built image dimensions missing')
            for entry in image.get('srcset','').split(','):
                if entry.strip():
                    url = entry.strip().split()[0]
                    if not (build_dir/url.lstrip('/')).is_file() or not url.endswith('.webp'):
                        errors.append(f'{slug}: built responsive image missing or not WebP: {url}')
                    else:
                        checked_images.add(url)
        for href in actual.links:
            if href.startswith('/post/'):
                path = build_dir/href.split('#')[0].split('?')[0].lstrip('/')
                if not path.is_dir() and not path.is_file():
                    errors.append(f'{slug}: internal article link missing: {href}')
        checked_routes += 1
    archive_path = build_dir/'blog-personal-training-sarasota-fit'/'index.html'
    if not archive_path.is_file():
        errors.append('Built original blog archive route missing')
    else:
        archive_html = archive_path.read_text()
        linked_slugs = set(re.findall(r'href="/post/([^/"#?]+)',archive_html))
        if linked_slugs != {p['slug'] for p in posts}:
            errors.append('Built blog archive does not link to every migrated article')
    return {'checkedPostRoutes':checked_routes,'checkedLocalWebpPaths':len(checked_images),'errors':errors,'passed':not errors}


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--source-dir', type=Path, default=Path('/tmp/srq-blog-source'))
    args.add_argument('--archive', type=Path, default=Path('/tmp/srq-blog-archive-posts.json'))
    args.add_argument('--report', type=Path)
    args.add_argument('--build-dir', type=Path)
    opts = args.parse_args()
    data = json.loads((ROOT/'content/blog-posts.json').read_text())
    posts = data if isinstance(data,list) else data['posts']
    report = compare(posts,opts.source_dir,opts.archive)
    if opts.build_dir:
        report['build'] = check_build(posts,opts.build_dir)
        report['passed'] = report['passed'] and report['build']['passed']
    if opts.report:
        opts.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    sys.exit(main())
