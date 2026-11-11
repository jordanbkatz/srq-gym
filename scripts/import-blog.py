#!/usr/bin/env python3
"""Import the original SRQ blog without rewriting its words.

The Wix sitemap is the inventory; each publicly served post supplies JSON-LD
metadata and a server-rendered article body. Only Wix presentation wrappers and
image expansion controls are removed. Images remain source URLs in this file;
the separate image importer creates the optimized local assets and manifest.
"""

import argparse
import concurrent.futures
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.request
import urllib.error


ROOT = Path(__file__).resolve().parent.parent
SOURCE = "https://www.srqhealthandfitness.com"
SITEMAP = SOURCE + "/blog-posts-sitemap.xml"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SEMANTIC = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "strong", "b", "em", "i", "u", "s", "sup", "sub", "code", "pre", "hr", "br", "table", "thead", "tbody", "tfoot", "colgroup", "col", "tr", "th", "td", "figure", "figcaption", "a"}
REMOVE = {"script", "style", "button", "svg"}


class Node:
    def __init__(self, tag="", attrs=(), parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        return "".join(child.text() if isinstance(child, Node) else child for child in self.children)


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, value):
        self.stack[-1].children.append(value)


def normalize_text(value):
    return re.sub(r"\s+", " ", value).strip()


def original_image_url(value):
    if not value:
        return ""
    if value.startswith("//"):
        value = "https:" + value
    if "static.wixstatic.com/media/" in value:
        return value.split("/v1/", 1)[0]
    return value


def image_info(node):
    attrs = node.attrs
    info = {"src": original_image_url(attrs.get("data-pin-media") or attrs.get("src", "")), "alt": attrs.get("alt", "")}
    parent = node.parent
    while parent is not None:
        if parent.tag == "wow-image" and parent.attrs.get("data-image-info"):
            data = json.loads(parent.attrs["data-image-info"])
            image = data.get("imageData", {})
            if image.get("uri"):
                uri = image["uri"]
                info["src"] = uri if uri.startswith("http") else "https://static.wixstatic.com/media/" + uri
            if image.get("width") and image.get("height"):
                info.update(width=image["width"], height=image["height"])
            break
        parent = parent.parent
    return info


def attribute(name, value):
    return f' {name}="{html.escape(str(value), quote=True)}"'


def semantic_html(node, images):
    if isinstance(node, str):
        return html.escape(node, quote=False)
    if node.tag in REMOVE:
        return ""
    if node.tag == "img":
        image = image_info(node)
        if not image["src"]:
            raise ValueError("Article image has no source")
        images.append(image)
        return "<img" + attribute("src", image["src"]) + attribute("alt", image["alt"]) + ">"
    children = "".join(semantic_html(child, images) for child in node.children)
    tag = node.tag
    if tag == "div" and "data-ricos-paragraph" in node.attrs:
        # Wix uses div instead of p for an intentional empty paragraph.
        tag = "p"
    if tag not in SEMANTIC:
        return children
    attrs = ""
    if tag == "a":
        href = node.attrs.get("href", "")
        if href:
            attrs += attribute("href", href)
        if node.attrs.get("target") == "_blank":
            attrs += ' target="_blank" rel="noopener noreferrer"'
    elif tag in {"ol", "li"}:
        for name in ("start", "value", "reversed", "type"):
            if name in node.attrs:
                attrs += attribute(name, node.attrs[name] or "")
    elif tag in {"td", "th"}:
        for name in ("colspan", "rowspan"):
            if name in node.attrs:
                attrs += attribute(name, node.attrs[name])
    if tag in VOID:
        return f"<{tag}{attrs}>"
    return f"<{tag}{attrs}>{children}</{tag}>"


def download(url, path):
    if path.exists():
        return path.read_text(encoding="utf-8")
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "SRQ-blog-migration/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                value = response.read().decode("utf-8")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
            return value
        except Exception:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def extract(url, source):
    document = Document(source)
    nodes = list(document.root.walk())
    body = next((node for node in nodes if node.tag == "section" and node.attrs.get("data-hook") == "post-description"), None)
    if body is None:
        raise ValueError(f"Missing article body: {url}")
    title_node = next(node for node in nodes if node.tag == "h1" and node.attrs.get("data-hook") == "post-title")
    metadata = None
    for node in nodes:
        if node.tag == "script" and node.attrs.get("type") == "application/ld+json":
            candidate = json.loads(node.text())
            if candidate.get("@type") == "BlogPosting":
                metadata = candidate
                break
    if not metadata:
        raise ValueError(f"Missing article metadata: {url}")
    images = []
    content_html = semantic_html(body, images)
    source_text = normalize_text(body.text())
    migrated_text = normalize_text(Document(content_html).root.text())
    if source_text != migrated_text:
        raise ValueError(f"Article text changed during cleanup: {url}")
    cover = metadata.get("image", {})
    cover_url = original_image_url(cover.get("url", "") if isinstance(cover, dict) else cover)
    cover_image = next((dict(image) for image in images if image["src"] == cover_url), {"src": cover_url, "alt": ""})
    if not cover_image["src"] and images:
        cover_image = dict(images[0])
    read_time = re.search(r"(\d+)\s*min read", source)
    title = title_node.text()
    return {
        "slug": url.rstrip("/").rsplit("/", 1)[-1],
        "title": title,
        "excerpt": metadata.get("description", ""),
        "publishedAt": metadata["datePublished"],
        "updatedAt": metadata.get("dateModified", metadata["datePublished"]),
        "author": metadata.get("author", {}).get("name", ""),
        "readingMinutes": int(read_time.group(1)) if read_time else max(1, round(len(source_text.split()) / 200)),
        "sourceUrl": url,
        "coverImage": cover_image,
        "html": content_html,
        "images": images,
        "sourceText": source_text,
        "sourceTextSha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
    }


def archive_metadata(cache):
    """Read every paginated feed; its custom excerpts can differ from SEO text."""
    posts = {}
    for page in range(1, 101):
        url = SOURCE + "/blog-personal-training-sarasota-fit" + (f"/page/{page}" if page > 1 else "?page=1")
        try:
            source = download(url, cache / f"archive-page-{page}.html")
        except urllib.error.HTTPError as error:
            # Wix returns 404 for a page beyond the end of the archive.
            # The caller still requires an exact match against the sitemap.
            if error.code == 404 and posts:
                return posts
            raise
        document = Document(source)
        warmup_node = next(node for node in document.root.walk() if node.attrs.get("id") == "wix-warmup-data")
        warmup = json.loads(warmup_node.text())
        feed_posts = None
        for app in warmup.get("appsWarmupData", {}).values():
            for key, value in app.items():
                if key.startswith("feed-page"):
                    feed_posts = json.loads(value)["feedResponse"]["postFeedPage"]["posts"]["posts"]
                    break
        if feed_posts is None:
            raise ValueError(f"Missing archive metadata: {url}")
        if not feed_posts:
            return posts
        for post in feed_posts:
            if post["slug"] in posts:
                raise ValueError(f"Duplicate archive slug on page {page}")
            posts[post["slug"]] = post
        if len(feed_posts) < 20:
            return posts
    raise ValueError("Archive pagination exceeded 100 pages")


def apply_archive_metadata(post, metadata):
    if post["title"] != metadata["title"]:
        raise ValueError(f"Archive and article title disagree: {post['sourceUrl']}")
    post.update(
        excerpt=metadata.get("excerpt", ""),
        publishedAt=metadata["firstPublishedDate"],
        updatedAt=metadata["lastPublishedDate"],
        author=metadata.get("owner", {}).get("name", post["author"]),
        readingMinutes=metadata.get("minutesToRead", post["readingMinutes"]),
    )
    media = metadata.get("media", {})
    image = media.get("wixMedia", {}).get("image", {})
    if image.get("url"):
        post["coverImage"] = {
            "src": original_image_url(image["url"]),
            "alt": media.get("altText", image.get("altText", "")),
            "width": image["width"],
            "height": image["height"],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default="/tmp/srq-blog-source")
    parser.add_argument("--output", default=str(ROOT / "content/blog-posts.json"))
    parser.add_argument("--archive-metadata", help="Optional previously captured complete feed JSON array")
    args = parser.parse_args()
    cache = Path(args.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    sitemap = download(SITEMAP, cache / "blog-posts-sitemap.xml")
    # Match <loc>, not <image:loc>; sitemap URLs are authoritative inventory.
    urls = [html.unescape(value) for value in re.findall(r"<loc>(.*?)</loc>", sitemap)]
    if not urls or len(urls) != len(set(urls)):
        raise ValueError("Sitemap is empty or contains duplicate post URLs")
    def import_one(url):
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        return extract(url, download(url, cache / f"{slug}.html"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        posts = list(pool.map(import_one, urls))
    metadata = ({post["slug"]: post for post in json.loads(Path(args.archive_metadata).read_text(encoding="utf-8"))}
                if args.archive_metadata else archive_metadata(cache))
    if set(metadata) != {post["slug"] for post in posts}:
        raise ValueError("Sitemap and paginated archive inventories do not match")
    for post in posts:
        apply_archive_metadata(post, metadata[post["slug"]])
    posts.sort(key=lambda post: post["publishedAt"], reverse=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"posts": len(posts), "inlineImages": sum(len(post["images"]) for post in posts), "output": str(output), "allArticleTextMatchesSource": True}))


if __name__ == "__main__":
    main()
