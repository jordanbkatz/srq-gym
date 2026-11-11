#!/usr/bin/env python3
"""Download the imported blog's original images and create compact local WebPs.

Requires ImageMagick (`magick`) and Google's `cwebp`, both available via Homebrew.
Run after `python3 scripts/import-blog.py`:
    python3 scripts/optimize-blog-images.py
Original downloads stay in the system temporary directory, outside the repository.
Article images start at 1440px/quality 76 and target 250KB; cards start at
640px/quality 76 and target 80KB. Compression never falls below quality 65.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(tempfile.gettempdir()) / 'srq-gym-blog-image-cache'
MAX_WIDTH = 1440
CARD_WIDTH = 640
QUALITY = 76
MIN_QUALITY = 65
ARTICLE_MAX_BYTES = 250_000
CARD_MAX_BYTES = 80_000


def command(*args: str) -> str:
    return subprocess.check_output(args, stderr=subprocess.PIPE, text=True).strip()


def original_url(source: str) -> str:
    """Remove Wix presentation transforms so we never encode a blurred thumbnail."""
    source = html.unescape(source)
    if source.startswith('wix:image://v1/'):
        media_id = source.split('wix:image://v1/', 1)[1].split('/', 1)[0].split('#', 1)[0]
        return 'https://static.wixstatic.com/media/' + urllib.parse.quote(urllib.parse.unquote(media_id), safe='~_.-')
    parsed = urllib.parse.urlsplit(source)
    if parsed.hostname == 'static.wixstatic.com' and '/media/' in parsed.path:
        media_id = urllib.parse.unquote(parsed.path.split('/media/', 1)[1].split('/', 1)[0])
        return 'https://static.wixstatic.com/media/' + urllib.parse.quote(media_id, safe='~_.-')
    return source


def collect_sources(posts: list[dict]) -> list[str]:
    sources: list[str] = []
    for post in posts:
        cover = post.get('coverImage')
        if isinstance(cover, dict) and cover.get('src'):
            sources.append(cover['src'])
        elif isinstance(cover, str):
            sources.append(cover)
        for item in post.get('images', []):
            source = item.get('src') if isinstance(item, dict) else item
            if source:
                sources.append(source)
        sources.extend(re.findall(r'<img\b[^>]*\bsrc=[\"\']([^\"\']+)', post.get('html', ''), flags=re.I))
    return list(dict.fromkeys(source for source in sources if source and not source.startswith('data:')))


def download(url: str, output: Path) -> None:
    if output.exists() and output.stat().st_size:
        return
    error = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'SRQ-Blog-Migration/1.0'})
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
            if not body:
                raise ValueError('Empty image response')
            output.write_bytes(body)
            return
        except Exception as exc:
            error = exc
            time.sleep(attempt + 1)
    raise RuntimeError(f'Could not download {url}: {error}')


def dimensions(path: Path) -> tuple[int, int, int]:
    result = command('magick', 'identify', '-format', '%w %h %n\n', str(path)).splitlines()[0].split()
    return int(result[0]), int(result[1]), int(result[2])


def encode(original: Path, destination: Path, width: int, animated: bool) -> tuple[int, int, int]:
    if animated:
        subprocess.run(['magick', str(original), '-coalesce', '-auto-orient', '-resize', f'{width}x>', '-strip', '-define', 'webp:method=6', '-quality', str(QUALITY), str(destination)], check=True, capture_output=True)
    else:
        with tempfile.TemporaryDirectory(prefix='srq-webp-') as directory:
            resized = Path(directory) / 'resized.png'
            target_bytes = ARTICLE_MAX_BYTES if width > CARD_WIDTH else CARD_MAX_BYTES
            minimum_width = 960 if width > CARD_WIDTH else 480
            quality = QUALITY
            encode_width = width
            while True:
                subprocess.run(['magick', str(original), '-auto-orient', '-resize', f'{encode_width}x>', '-strip', str(resized)], check=True, capture_output=True)
                while True:
                    subprocess.run(['cwebp', '-quiet', '-q', str(quality), '-m', '6', '-mt', '-alpha_q', '90', '-metadata', 'none', str(resized), '-o', str(destination)], check=True, capture_output=True)
                    if destination.stat().st_size <= target_bytes or quality == MIN_QUALITY:
                        break
                    quality = max(MIN_QUALITY, quality - 6)
                actual_width, _, _ = dimensions(destination)
                if destination.stat().st_size <= target_bytes or actual_width <= minimum_width:
                    break
                # Texture-heavy photos occasionally need fewer pixels as well as
                # compression. Keep article images at least 960px when available.
                encode_width = max(minimum_width, int(actual_width * .9))
    actual_width, actual_height, _ = dimensions(destination)
    return actual_width, actual_height, destination.stat().st_size


def migrate(url: str, output_dir: Path) -> dict:
    identity = hashlib.sha256(url.encode()).hexdigest()[:16]
    suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    original = CACHE / f'{identity}{suffix if suffix else ".image"}'
    download(url, original)
    original_width, original_height, frames = dimensions(original)
    full = output_dir / f'{identity}.webp'
    full_width, full_height, full_bytes = encode(original, full, MAX_WIDTH, frames > 1)
    if original_width > CARD_WIDTH or full_bytes > CARD_MAX_BYTES:
        card = output_dir / f'{identity}-640.webp'
        card_width, card_height, card_bytes = encode(original, card, CARD_WIDTH, frames > 1)
    else:
        card, card_width, card_height, card_bytes = full, full_width, full_height, full_bytes
    return {
        'src': '/images/blog/' + full.name,
        'width': full_width,
        'height': full_height,
        'bytes': full_bytes,
        'cardSrc': '/images/blog/' + card.name,
        'cardWidth': card_width,
        'cardHeight': card_height,
        'cardBytes': card_bytes,
        'originalUrl': url,
        'originalWidth': original_width,
        'originalHeight': original_height,
        'originalBytes': original.stat().st_size,
        'originalSha256': hashlib.sha256(original.read_bytes()).hexdigest(),
        'animated': frames > 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'content/blog-posts.json')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'content/blog-image-manifest.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'public/images/blog')
    args = parser.parse_args()
    for dependency in ('magick', 'cwebp'):
        if not shutil.which(dependency):
            raise SystemExit(f'Missing image converter: {dependency}')
    data = json.loads(args.input.read_text())
    posts = data if isinstance(data, list) else data['posts']
    sources = collect_sources(posts)
    groups: dict[str, list[str]] = {}
    for source in sources:
        groups.setdefault(original_url(source), []).append(source)
    CACHE.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(migrate, url, args.output): url for url in groups}
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            results[url] = future.result()
    manifest = {source: results[original_url(source)] for source in sources}
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary_manifest = args.manifest.with_suffix('.tmp.json')
    temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    temporary_manifest.replace(args.manifest)
    full_bytes = sum(item['bytes'] for item in results.values())
    files = {item['src'] for item in results.values()} | {item['cardSrc'] for item in results.values()}
    print(json.dumps({
        'sourceReferences': len(sources), 'uniqueImages': len(results), 'webpFiles': len(files),
        'originalBytes': sum(item['originalBytes'] for item in results.values()),
        'articleImageBytes': full_bytes,
        'totalWebpBytes': sum((ROOT / 'public' / file.lstrip('/')).stat().st_size for file in files),
        'largestArticleImageBytes': max((item['bytes'] for item in results.values()), default=0),
        'animatedImages': sum(item['animated'] for item in results.values()),
    }, indent=2))


if __name__ == '__main__':
    main()
