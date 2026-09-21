"""Build the Agent × Robot journal with Python's standard library."""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from datetime import date
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "public"


def esc(value):
    return html.escape(str(value), quote=True)


def read_json(name):
    return json.loads((ROOT / "content" / name).read_text())


def article_citation(post, site):
    authors = [name.rstrip("*") for name in post["authors"]]
    published = date.fromisoformat(post["date"])
    url = site["url"].rstrip("/") + f'/posts/{post["slug"]}/'
    fields = [
        ("author", " and ".join(authors)),
        ("title", "{" + post["title"] + "}"),
        ("year", str(published.year)),
        ("month", published.strftime("%B")),
        ("day", str(published.day)),
        ("url", url),
    ]
    bibtex = "@misc{" + post["citation_key"] + ",\n" + ",\n".join(
        "  " + key + " = {" + value + "}" for key, value in fields
    ) + "\n}"
    return f'''<section class="article-citation" aria-labelledby="citation-title" data-citation>
      <div class="citation-heading"><h3 id="citation-title">Cite this article</h3><button type="button" class="citation-copy" data-copy-citation>Copy BibTeX</button></div>
      <p class="citation-reference">{esc(', '.join(authors))}. {esc(post['title'])}. <em>{esc(site['name'])}</em>, {esc(post['date_label'])}. <a href="{esc(url)}">Article link ↗</a></p>
      <pre tabindex="0" aria-label="BibTeX citation"><code data-citation-text>{esc(bibtex)}</code></pre>
      <span class="citation-status" data-citation-status role="status" aria-live="polite"></span>
    </section>'''


def build(base_path="", output_dir=None):
    base_path = "/" + base_path.strip("/") if base_path.strip("/") else ""
    if not re.fullmatch(r"(?:/[A-Za-z0-9_.-]+)*", base_path) or ".." in base_path.split("/"):
        raise ValueError("Base path must be a URL path such as /agentic-robot")
    out = Path(output_dir).resolve() if output_dir else OUT
    site = read_json("site.json")
    posts = read_json("posts.json")
    projects = read_json("projects.json")
    by_project = {p["slug"]: p for p in projects}
    # Validate references before replacing any generated page.
    for post in posts:
        post["body_html"] = (ROOT / "content/articles" / post["body"]).read_text()
        if "{{TICTACTOE_PRIMITIVES}}" in post["body_html"]:
            example = (ROOT / "content/articles/tictactoe-primitive-example.html").read_text()
            post["body_html"] = post["body_html"].replace("{{TICTACTOE_PRIMITIVES}}", example)
        post["reading_time"] = max(1, round(len(re.sub(r"<[^>]+>", " ", post["body_html"]).split()) / 200))
        post["date_label"] = date.fromisoformat(post["date"]).strftime("%b %d, %Y")
        for slug in post["projects"]:
            if slug not in by_project:
                raise ValueError(f"Unknown project {slug!r} in {post['slug']}")
    for item in posts + projects:
        if not (ROOT / "assets" / item["image"]).is_file():
            raise ValueError(f"Missing image: {item['image']}")
        if item.get("video") and not (ROOT / "assets" / item["video"]).is_file():
            raise ValueError(f"Missing video: {item['video']}")

    def report(path):
        if path.startswith(("https://", "http://")):
            return path
        return site["physical_url"] if path == "external-physical" else site["results_url"].rstrip("/") + "/" + path

    def external(label, path, cls="text-link"):
        return f'<a class="{cls}" href="{esc(report(path))}" target="_blank" rel="noopener noreferrer">{esc(label)} <span aria-hidden="true">↗</span><span class="sr-only"> (opens in a new tab)</span></a>'

    def photo(item, cls="", loading="lazy"):
        return f'<img class="{cls}" src="/assets/{esc(item["image"])}" alt="{esc(item["image_alt"])}" loading="{loading}" decoding="async">'

    def post_meta(p):
        return f'<div class="meta"><span>{esc(p["category"])}</span><span class="dot">·</span><time datetime="{p["date"]}">{p["date_label"]}</time><span class="dot">·</span><span>Est. {p["reading_time"]} min read</span></div>'

    def video(p):
        return f'<video controls muted playsinline preload="metadata" poster="/assets/{esc(p["image"])}" aria-label="{esc(p["video_label"])}"><source src="/assets/{esc(p["video"])}" type="video/mp4">Your browser cannot play this video. <a href="/assets/{esc(p["video"])}">Open the recording</a>.</video>'

    def post_card(p, filterable=False):
        attrs = ""
        if filterable:
            searchable = " ".join([p["title"], p["subtitle"], p["excerpt"], p["category"]] + [by_project[s]["short_name"] for s in p["projects"]])
            attrs = f' data-post data-category="{esc(p["category"])}" data-search="{esc(searchable.lower())}" data-featured="{str(p.get("featured", False)).lower()}"'
        media = f'<figure class="card-video">{video(p)}<figcaption>{esc(p["video_caption"])}</figcaption></figure>' if p.get("video") else f'<a class="card-image {esc(p["image_style"])}" href="/posts/{p["slug"]}/" aria-label="Read {esc(p["title"])}">{photo(p)}<span class="image-arrow" aria-hidden="true">↗</span></a>'
        return f'''<article class="post-card"{attrs}>
          {media}
          <div class="blog-card-copy">{post_meta(p)}<h3><a href="/posts/{p['slug']}/">{esc(p['title'])}</a></h3><p>{esc(p['excerpt'])}</p><div class="blog-card-actions"><a class="text-link" href="/posts/{p['slug']}/">Read Blog <span aria-hidden="true">↗</span></a>{external('Interactive Webpage', p['results_path'])}</div></div>
        </article>'''

    def project_card(p, compact=False):
        stats = "".join(f'<div><strong>{esc(m["value"])}</strong><span>{esc(m["label"])}</span></div>' for m in p["metrics"])
        return f'''<article class="project-card {'compact' if compact else ''}" data-project data-environment="{esc(p['environment'])}">
          <a class="project-picture" href="/projects/{p['slug']}/" aria-label="Explore {esc(p['name'])}">{photo(p)}<span class="project-number">{p['number']}</span></a>
          <div class="project-copy"><div class="eyebrow">{esc(p['environment'])}</div><h3><a href="/projects/{p['slug']}/">{esc(p['name'])}</a></h3><p>{esc(p['description'])}</p>
          {'' if compact else '<p class="mode">' + esc(p['mode']) + '</p><div class="metrics">' + stats + '</div>'}
          <a class="text-link" href="/projects/{p['slug']}/">Explore project <span aria-hidden="true">↗</span></a></div></article>'''

    layout = Template((ROOT / "templates/layout.html").read_text())
    pages = {}

    def page(path, title, description, body, active, kind=""):
        def nav_group(key, label, url, items):
            current = ' aria-current="page"' if active == key else ''
            entries = ''.join(f'<a href="{href}"><span>{esc(name)}</span><small>{esc(detail)}</small></a>' for name, detail, href in items)
            return f'''<div class="nav-group" data-nav-group><div class="nav-group-row"><a href="{url}"{current}>{label}</a><button class="submenu-toggle" aria-label="Show {label.lower()}" aria-expanded="false" aria-controls="nav-{key}">⌄</button></div><div class="nav-contents" id="nav-{key}" hidden>{entries}</div></div>'''
        current_home = 'aria-current="page"' if active == "home" else ''
        nav = f'<a class="nav-single" href="/" {current_home}>Home</a>'
        nav += nav_group("blogs", "Blogs", "/blogs/", [(p["title"], p["category"], f'/posts/{p["slug"]}/') for p in posts])
        pages[path] = layout.substitute(title=esc(title + " — " + site["name"]), description=esc(description), nav=nav, content=body, kind=kind, results_url=esc(site["results_url"]))

    categories = list(dict.fromkeys(p["category"] for p in posts))
    chips = '<button class="filter active" data-filter="all" aria-pressed="true">All blogs</button>' + "".join(f'<button class="filter" data-filter="{esc(c)}" aria-pressed="false">{esc(c)}</button>' for c in categories)
    page("index.html", "Home", site["description"], f'''
      <section class="journal-intro wrap"><div class="eyebrow"><span class="live-dot"></span> Agent × Robot</div>
        <div class="intro-row"><h1>Robot using Agent<br><em>in the physical world.</em></h1></div>
      </section>
      <section class="wrap home-blog-grid" aria-label="Latest blogs">{''.join(post_card(p) for p in posts)}</section>
    ''', "home", "home-page")

    page("blogs/index.html", "Blogs", "Research updates and lessons from Agent × Robot experiments.", f'''
      <section class="wrap page-intro"><div class="eyebrow">Agent × Robot / Blogs</div><h1>Notes from the<br><em>physical world.</em></h1><p class="lede">Research updates, working ideas, and lessons from our experiments.</p></section>
      <section class="wrap journal-list blog-archive" data-journal aria-label="Blog articles">
        <div class="journal-tools"><div class="filters" aria-label="Filter blog articles">{chips}</div><label class="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="m15 15 5 5"/></svg><span class="sr-only">Search blogs</span><input type="search" placeholder="Search blogs" data-search-input></label></div>
        <div class="post-grid">{''.join(post_card(p, True) for p in posts)}</div><p class="sr-only" data-search-status aria-live="polite"></p>
        <div class="empty-state" data-empty hidden><h3>No matching blogs.</h3><p>Try a different topic or browse all posts.</p><button class="button dark" data-reset>Show all blogs</button></div>
      </section>
    ''', "blogs", "blogs-page")

    project_filters = '<button class="filter active" data-project-filter="all" aria-pressed="true">All projects</button>' + "".join(f'<button class="filter" data-project-filter="{esc(e)}" aria-pressed="false">{esc(e)}</button>' for e in dict.fromkeys(p["environment"] for p in projects))
    page("projects/index.html", "Projects", "Explore Agent × Robot research projects, from simulation to physical manipulation.", f'''
      <section class="wrap page-intro"><div class="eyebrow">Agent × Robot / Projects</div><h1>Questions become<br><em>experiments.</em></h1><p class="lede">Each project has its own methods, results, and interactive evidence. Together, they explore what it takes for agents to work in the physical world.</p></section>
      <section class="wrap projects-directory" data-project-directory aria-label="Research projects"><div class="directory-toolbar"><div class="filters" aria-label="Filter projects">{project_filters}</div><span class="eyebrow" data-project-count>{len(projects)} projects</span></div><div class="project-grid">{''.join(project_card(p) for p in projects)}</div><p class="sr-only" data-project-status aria-live="polite"></p></section>
    ''', "projects")

    for p in projects:
        stats = ''.join(f'<div><strong>{esc(m["value"])}</strong><span>{esc(m["label"])}</span></div>' for m in p["metrics"])
        related = [post for post in posts if p["slug"] in post["projects"]]
        evidence = ''.join(f'<li>{external(e["label"], e["path"])}</li>' for e in p["evidence"])
        related_section = f'<section class="wrap related"><div class="section-heading"><h2>Blogs from this project</h2><a class="text-link" href="/blogs/">All blogs ↗</a></div><div class="post-grid">{"".join(post_card(post) for post in related)}</div></section>' if related else ''
        page(f"projects/{p['slug']}/index.html", p["name"], p["description"], f'''
          <section class="wrap project-intro"><a class="back-link" href="/projects/">← All projects</a><div class="eyebrow">Project {p['number']} / {esc(p['environment'])}</div><h1>{esc(p['name'])}</h1><p class="lede">{esc(p['description'])}</p><div class="project-actions">{external('Open interactive results', p['results_path'], 'button dark')}<span class="mode">{esc(p['mode'])}</span></div></section>
          <section class="wrap project-overview"><div class="project-hero-image">{photo(p, loading='eager')}</div><div class="project-overview-copy"><div class="eyebrow">The experiment</div><h2>{esc(p['short_name'])}</h2><p>{esc(p['summary'])}</p><div class="metrics">{stats}</div></div></section>
          <section class="wrap project-details"><div><div class="eyebrow">What we found</div><h2>A closer look at the results.</h2><ul class="findings">{''.join('<li>' + esc(f) + '</li>' for f in p['findings'])}</ul><div class="context-note"><strong>How to read these results</strong><p>{esc(p['limits'])}</p></div></div><aside class="evidence-panel"><div class="eyebrow">Go deeper</div><h3>Explore the evidence.</h3><p>Task-level results, methods and recordings live in the interactive report.</p><ul>{evidence}</ul></aside></section>
          {related_section}
        ''', "projects")

    for p in posts:
        body = p["body_html"].replace("{{RESULTS_URL}}", esc(site["results_url"])).replace("{{PHYSICAL_URL}}", esc(site["physical_url"]))
        article_media = f'<figure class="article-figure article-inline-media {esc(p["image_style"])}">{video(p) if p.get("video") else photo(p, loading="eager")}<figcaption>{esc(p["image_caption"])}</figcaption></figure>'
        if p.get("article_media", True):
            body = body.replace("{{ARTICLE_VIDEO}}", article_media) if "{{ARTICLE_VIDEO}}" in body else article_media + body
        headings = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
        toc = ''.join(f'<a href="#{esc(anchor)}">{title}</a>' for anchor, title in headings)
        report_links = ''.join(f'<a class="aside-project" href="{esc(report(by_project[slug]["results_path"]))}" target="_blank" rel="noopener noreferrer"><span class="eyebrow">{esc(by_project[slug]["environment"])}</span>{esc(by_project[slug]["short_name"])} <span aria-hidden="true">↗</span><span class="sr-only"> (opens in a new tab)</span></a>' for slug in p["projects"])
        related = sorted((post for post in posts if post["slug"] != p["slug"]), key=lambda post: -len(set(post["projects"]) & set(p["projects"])))[:2]
        related_section = f'<section class="wrap related"><div class="section-heading"><h2>Keep exploring</h2><a class="text-link" href="/blogs/">All blogs ↗</a></div><div class="post-grid">{"".join(post_card(post) for post in related)}</div></section>' if related else ''
        author_note = '<p class="author-note">' + esc(p['author_note']) + '</p>' if p.get('author_note') else ''
        page(f"posts/{p['slug']}/index.html", p["title"], p["excerpt"], f'''
          <header class="wrap article-header"><a class="back-link" href="/blogs/">← All blogs</a>{post_meta(p)}<h1>{esc(p['title'])}</h1><p class="lede">{esc(p['subtitle'])}</p><div class="article-header-actions">{external("Interactive Webpage", p["results_path"], "button dark")}</div><div class="byline"><div class="author-byline"><span class="author-label">Authors</span><div class="author-list">{''.join('<span class="author-name">' + esc(author) + '</span>' for author in p.get('authors', [site['name']]))}</div>{author_note}</div><button class="copy-link" data-copy>Copy link <span aria-hidden="true">↗</span></button><span class="sr-only" data-copy-status aria-live="polite"></span></div></header>
          <div class="wrap article-layout"><article class="prose">{body}<div class="article-cta"><div class="eyebrow">From the story to the evidence</div><h3>Inspect the experiment.</h3><p>Explore the task-level results, methods, and recordings.</p>{external('Open interactive report', p['results_path'], 'button dark')}</div>{article_citation(p, site)}</article><aside class="article-aside"><div class="sticky"><div class="eyebrow">In this article</div><nav class="toc" aria-label="Table of contents">{toc}</nav><div class="eyebrow">Interactive report</div>{report_links}</div></aside></div>
          {related_section}
        ''', "blogs", "article-page")

    page("about/index.html", "About", site["description"], '''
      <section class="wrap page-intro"><div class="eyebrow">About Agent × Robot</div><h1>From software agents<br>to <em>physical agency.</em></h1><p class="lede">A research blog about AI agents, robot policies, and the gap between a plan that sounds right and an action that works.</p></section>
      <section class="wrap about-grid"><div class="prose"><h2 id="questions">A shared set of questions.</h2><p>How can an agent turn an instruction into reliable robot behavior? What should be written into reusable code, and what needs to be reasoned about during execution? Where do these approaches break down?</p><p>Agent × Robot brings related projects together under those questions. Our first experiments examine coding agents in simulation and agent-assisted policies on physical robots. Each project keeps its own protocol, results, and limitations.</p><h2 id="evidence">Writing backed by evidence.</h2><p>The blogs explain the ideas and lessons. Project pages describe the experiments. Interactive reports let you inspect task-level results, recordings, execution traces, and the methods behind a claim.</p><p>We distinguish development feedback from evaluation, aggregate scores from individual trials, and observed outcomes from hypotheses. A useful negative result belongs alongside a successful demonstration.</p><h2 id="follow">Follow the work.</h2><p>Start with the latest research notes, or choose a project and work through its evidence. Future updates will connect back to the same project, so the story and the experiment can develop together.</p><div class="inline-actions"><a class="button dark" href="/blogs/">Read the blogs ↗</a><a class="text-link" href="/projects/">Explore projects ↗</a></div></div><aside class="about-principles"><span class="large-mark" aria-hidden="true">a × r</span><div><span class="eyebrow">01 / Blogs</span><p>The question and what we learned.</p></div><div><span class="eyebrow">02 / Projects</span><p>The experiment and its context.</p></div><div><span class="eyebrow">03 / Interactive reports</span><p>The evidence, open to inspection.</p></div></aside></section>
    ''', "about")
    page("404.html", "Page not found", "This page could not be found.", '<section class="wrap page-intro"><div class="eyebrow">404 / Page not found</div><h1>A small <em>detour.</em></h1><p class="lede">This page does not exist. The homepage is a good place to start.</p><a class="button dark" href="/">Back to home ↗</a></section>', "")

    out.mkdir(parents=True, exist_ok=True)
    for path, rendered in pages.items():
        if base_path:
            rendered = re.sub(r'''((?:href|src|poster)=["'])/(?!/)''', lambda match: match[1] + base_path + "/", rendered)
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp")
        temp.write_text(rendered)
        temp.replace(target)
    # Remove deleted content routes so a local preview cannot show stale articles.
    for old in out.rglob("*.html"):
        if str(old.relative_to(out)) not in pages:
            old.unlink()
    for directory in sorted((p for p in out.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    shutil.copytree(ROOT / "assets", out / "assets", dirs_exist_ok=True)
    (out / ".nojekyll").touch()
    return len(pages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-path", default="", help="URL prefix, e.g. /agentic-robot for GitHub Pages")
    parser.add_argument("--output", type=Path, default=OUT, help="Static output directory")
    args = parser.parse_args()
    count = build(args.base_path, args.output)
    print(f"Built {count} pages → {args.output.resolve()}")
