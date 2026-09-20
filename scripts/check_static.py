"""Check generated internal links, fragments and asset paths before deployment."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = set()
        self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for key in ("href", "src", "poster"):
            if attrs.get(key):
                self.links.append(attrs[key])


def check(root, base_path):
    root = root.resolve()
    prefix = "/" + base_path.strip("/") if base_path.strip("/") else ""
    pages = {p: Document(p.read_text()) for p in root.rglob("*.html")}
    count = 0
    for file, page in pages.items():
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            path = unquote(url.path)
            if path.startswith("/"):
                if prefix and not (path == prefix or path.startswith(prefix + "/")):
                    raise ValueError(f"Link escapes deployment prefix in {file}: {link}")
                target = root / path[len(prefix):].lstrip("/")
            else:
                target = file.parent / path if path else file
            if target.is_dir():
                target /= "index.html"
            if not target.exists():
                raise ValueError(f"Missing target in {file}: {link}")
            if url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                raise ValueError(f"Missing anchor in {file}: {link}")
            count += 1
    if not pages:
        raise ValueError("No HTML pages found")
    print(f"Checked {count} internal links/assets across {len(pages)} pages at {prefix or '/'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--base-path", default="")
    args = parser.parse_args()
    check(args.directory, args.base_path)
