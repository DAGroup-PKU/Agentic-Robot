# Agent × Robot

A dependency-free editorial site for the Agent × Robot umbrella. Blog posts link directly to their detailed interactive reports. The existing public evaluation sites are unchanged.

## Run locally

Requires Python 3.12 or newer. No package installation is needed.

```bash
git clone https://github.com/DAGroup-PKU/agentic-robot.git
cd agentic-robot
python serve.py
```

Open **http://localhost:8787**. Changes in `content/`, `assets/`, `templates/`, or `build.py` rebuild the site and refresh the browser. Build errors appear in the terminal and local browser. Server changes require a restart.

If this runs on a remote machine, forward port 8787 through your editor or SSH, then open the forwarded local URL:

```bash
ssh -L 8787:127.0.0.1:8787 your-server
```

Use `python serve.py --port 8788` for another port. The server binds to loopback by default. It is a development server, not a production server.

## Make an edit

| File | Purpose |
| --- | --- |
| `content/site.json` | Site description and interactive report URLs |
| `content/posts.json` | Article title, summary, date, cover, project relationships |
| `content/articles/*.html` | Article body, with semantic HTML and section IDs |
| `content/projects.json` | Project descriptions, methods, findings, evidence links |
| `content/robodojo-results.json` | Saved report comparison snapshot backing the blog’s reported results |
| `assets/styles.css` | Base visual design and responsive layout |
| `assets/sidebar.css` | Left navigation, compact homepage, and mobile drawer |
| `assets/app.js` | Search, filters, navigation, copy link, local refresh |
| `templates/layout.html` | Shared page shell, header and footer |
| `build.py` | Page composition and route generation |

The current RoboDojo article summarizes the saved evaluation evidence. Zero-shot is scoped to execution without further coding-agent iteration; the historical scoring panel is not held out. A real-world blog can be added later.

## Add a post

1. Add a body HTML file under `content/articles/`. Use `<h2 id="stable-section-id">` for automatically generated contents links.
2. Add its cover under `assets/` and an entry in `content/posts.json`, following an existing entry. `slug` becomes `/posts/<slug>/`; `projects` links it to one or more existing project slugs. Reading time is computed from the body.
3. Keep posts in the desired display order. The Blogs page filters come from the post categories. Set `results_path` to a path in the simulation report, `external-physical` for the current physical report, or a complete HTTPS URL for an independent report.

Set `authors` in the post record to display the author byline. Article bodies can use `{{RESULTS_URL}}` and `{{PHYSICAL_URL}}`. The current post also uses `{{TICTACTOE_PRIMITIVES}}` to include `content/articles/tictactoe-primitive-example.html`; its stage interactions are defined in `assets/app.js`. Treat body files as trusted authored HTML; the generator is not designed to ingest untrusted submissions.

## Add a project

Add a record to `content/projects.json`, then add its image. Its stable page, directory card, and related articles are generated automatically. Project records supply report destinations for blog links. Local project routes remain available, but are hidden from the navigation; the homepage is populated from blog posts. Use the `projects` field of posts to associate updates with it. Environment filters derive from the content. No empty “coming soon” projects are included.

For an independent interactive app, set the project's `results_path` and evidence `path` fields to its complete HTTPS URLs. This requires no layout or routing changes. See `ARCHITECTURE.md` for the longer-term publishing plan.

## Static export

```bash
python build.py
```

This generates `public/`: HTML, CSS, JavaScript, images and SVGs. A static host supporting directory `index.html` routes can serve it. For a host subdirectory, build with `python build.py --base-path /agentic-robot`. Validate the output with `python scripts/check_static.py public --base-path /agentic-robot` (omit the base-path flag for a root build). No Python runtime is required in production. Preview-only polling runs on localhost and stops if the development endpoint is unavailable.

## GitHub Pages

The repository is private and the website is not published. The organization’s current plan does not support GitHub Pages for this private repository. A manual `.github/workflows/pages.yml` workflow is included for future hosting: it builds, checks internal links and assets, and publishes `public/` when explicitly dispatched. Once Pages hosting is available, select **GitHub Actions** in repository Settings → Pages before running it. Pushes do not trigger deployment. The workflow reads the configured base path, so repository hosting and custom domains use the same source. Generated output and Python caches are ignored by Git.

## Evidence

Initial copy and assets come from the existing local `../evaluation-atlas/out/` build and its public reports. Key sources: `comparison.json`, `execution-evidence.json`, `primitive-stats.json`, and the physical REC02 report. Simulation and physical success denominators stay separate; timing figures have different measurement boundaries; primitive links are source integrations, not runtime call counts.

## Navigation and homepage

The homepage contains blog cards with a date, estimated reading time, title, summary, and Read Blog / Interactive Webpage links. The RoboDojo card includes a locally hosted tic-tac-toe video. Cards occupy one of two equal desktop columns and stack on mobile. Results, the category radar, and detailed findings live inside the blog, not in its preview card. The complete article collection is at `/blogs/`, displayed as a vertical list of bordered modules with a compact video on the left and text on the right. New posts add new rows; narrow screens stack each module’s media and text. The article video is centered at 80% of the main prose column width. Use `{{ARTICLE_VIDEO}}` in a post body to place it after the opening results summary; otherwise it appears before the body. On desktop, hover or focus Blogs in the left sidebar to reveal its entries. Projects is hidden from navigation, and blog evidence links go directly to external reports and their sections. Disclosure buttons support click and keyboard operation; on small screens, the left rail expands into a navigation drawer. The lists derive from the content files. The sidebar shows Home and Blogs, omitting Projects, About, collection-wide submenu links, and descriptive taglines.

## RoboDojo media provenance

The tic-tac-toe video is copied without edits from `../evaluation-atlas/out/videos/7047d73917c9-0-2.mp4`. Its report metadata records a successful earlier development episode on 2026-09-14; it is not scored-batch footage or a representative sample. The video uses native playback controls and does not autoplay. The poster and category radar come from the same saved report build. The radar’s white canvas and plot backgrounds are made transparent to blend with the blog; data geometry and model colors are unchanged. `content/robodojo-results.json` is an unchanged copy of that report’s `comparison.json` (snapshot 2026-09-17). Refresh the snapshot and radar together if results change. The public URL rejected automated retrieval during this edit; the local report artifacts were used.

For another video blog, set `video` (local asset filename), `video_label`, and `video_caption` alongside the existing image fields, which supply the poster. The `results_snapshot` field records the evidence file for editorial reference; charts and results belong in the article body.
