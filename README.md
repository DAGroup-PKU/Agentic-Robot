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
| `content/rollout-comparison.json` | Source and aggregate values for the historical rollout time/token comparison |
| `assets/styles.css` | Base visual design and responsive layout |
| `assets/sidebar.css` | Left navigation, compact homepage, and mobile drawer |
| `assets/app.js` | Search, filters, navigation, copy link, local refresh |
| `templates/layout.html` | Shared page shell, header and footer |
| `build.py` | Page composition and route generation |

The current RoboDojo article summarizes the saved evaluation evidence. Zero-shot is scoped to execution without further coding-agent iteration; the historical scoring panel is not held out. The real-world article covers exploration and execution on physical robots, with three local task videos and diagrams adapted to the journal palette.

## Add a post

1. Add a body HTML file under `content/articles/`. Use `<h2 id="stable-section-id">` for automatically generated contents links.
2. Add its cover under `assets/` and an entry in `content/posts.json`, following an existing entry. `slug` becomes `/posts/<slug>/`; `projects` links it to one or more existing project slugs. Reading time is computed from the body.
3. Keep posts in the desired display order. The Blogs page filters come from the post categories. Set `results_path` to a path in the simulation report, `external-physical` for the current physical report, or a complete HTTPS URL for an independent report.

Every blog header includes an Interactive Webpage button using its `results_path`. Set `authors` in the post record to display the author byline. Each article ends with a citation block and Copy BibTeX button. Set a stable `citation_key` in the post record; citations use the canonical `url` in `content/site.json`, preserve author order, and omit equal-contribution marks from the BibTeX author names. Article bodies can use `{{RESULTS_URL}}` and `{{PHYSICAL_URL}}`. The current post also uses `{{TICTACTOE_PRIMITIVES}}` to include `content/articles/tictactoe-primitive-example.html`; its stage interactions are defined in `assets/app.js`. Treat body files as trusted authored HTML; the generator is not designed to ingest untrusted submissions.

## Add a project

Add a record to `content/projects.json`, then add its image. Its stable page, directory card, and related articles are generated automatically. Project records supply report destinations for blog links. Local project routes remain available, but are hidden from the navigation; the homepage is populated from blog posts. Use the `projects` field of posts to associate updates with it. Environment filters derive from the content. No empty “coming soon” projects are included.

For an independent interactive app, set the project's `results_path` and evidence `path` fields to its complete HTTPS URLs. This requires no layout or routing changes. See `ARCHITECTURE.md` for the longer-term publishing plan.

## Static export

```bash
python build.py
```

This generates `public/`: HTML, CSS, JavaScript, images and SVGs. A static host supporting directory `index.html` routes can serve it. For a host subdirectory, build with `python build.py --base-path /agentic-robot`. Validate the output with `python scripts/check_static.py public --base-path /agentic-robot` (omit the base-path flag for a root build). No Python runtime is required in production. Preview-only polling runs on localhost and stops if the development endpoint is unavailable.

## GitHub Pages

The GitHub repository remains private. The public blog is hosted separately at https://agent-x-robot.bijianxin292430887.chatgpt.site/. The organization’s current plan does not support GitHub Pages for this private repository. A manual `.github/workflows/pages.yml` workflow is included for future hosting: it builds, checks internal links and assets, and publishes `public/` when explicitly dispatched. Once Pages hosting is available, select **GitHub Actions** in repository Settings → Pages before running it. Pushes do not trigger deployment. The workflow reads the configured base path, so repository hosting and custom domains use the same source. Generated output and Python caches are ignored by Git.

## Evidence

Initial copy and assets come from the existing local `../evaluation-atlas/out/` build and its public reports. Key sources: `comparison.json`, `execution-evidence.json`, `primitive-stats.json`, and the physical REC02 report. Simulation and physical success denominators stay separate; timing figures have different measurement boundaries; primitive links are source integrations, not runtime call counts.

## Navigation and homepage

The homepage contains blog cards with a date, estimated reading time, title, summary, and Read Blog / Interactive Webpage links. The RoboDojo card includes a locally hosted tic-tac-toe video. Cards occupy one of two equal desktop columns and stack on mobile. Results, the category radar, and detailed findings live inside the blog, not in its preview card. The complete article collection is at `/blogs/`, displayed as a vertical list of bordered modules with a compact video on the left and text on the right. New posts add new rows; narrow screens stack each module’s media and text. The article video is centered at 80% of the main prose column width. Use `{{ARTICLE_VIDEO}}` in a post body to place it after the opening results summary; otherwise it appears before the body. On desktop, hover or focus Blogs in the left sidebar to reveal its entries. Projects is hidden from navigation, and blog evidence links go directly to external reports and their sections. Disclosure buttons support click and keyboard operation; on small screens, the left rail expands into a navigation drawer. The lists derive from the content files. The sidebar shows Home and Blogs, omitting Projects, About, collection-wide submenu links, and descriptive taglines.

## RoboDojo media provenance

The tic-tac-toe video is copied without edits from `../evaluation-atlas/out/videos/7047d73917c9-0-2.mp4`. Its report metadata records a successful earlier development episode on 2026-09-14; it is not scored-batch footage or a representative sample. The video uses native playback controls and does not autoplay. The poster comes from the same saved report build. The transparent category radar is generated by `scripts/build_radar.py` from `content/robodojo-results.json` and `content/pi05-reference.json`. The latter records the 18 official π0.5 task values, source URL, asset hash, and leaderboard version (2026.9.20). All curves use unweighted task means within the same six categories, including zeros; π0.5 is explicitly labeled as a separate official evaluation. To regenerate the SVG, run `python scripts/build_radar.py` in an environment with matplotlib installed; the ordinary site build and hosting require no plotting dependency. `content/robodojo-results.json` is an unchanged copy of that report’s `comparison.json` (snapshot 2026-09-17). Refresh the snapshot and radar together if results change. The public URL rejected automated retrieval during this edit; the local report artifacts were used.

For another video blog, set `video` (local asset filename), `video_label`, and `video_caption` alongside the existing image fields, which supply the poster. The `results_snapshot` field records the evidence file for editorial reference; charts and results belong in the article body.

## Real-world article

`content/articles/agents-in-the-real-world.html` adapts the supplied “Agents in the Real World: From Exploration to Execution” article. Its three videos are copied unchanged from the supplied share folder into `assets/real-world/`; the two SVG diagrams retain their content and geometry with journal colors. The article provides its own media gallery, so its post record sets `article_media: false` to avoid repeating the preview video. Its report links open the `astra-hanoi-r01` run. The original standalone source is preserved.

The real-world blog cover uses the Hanoi recording from 00:35 through the end, encoded at 2× speed (`assets/real-world/hanoi-cover-from-35s-2x.mp4`), with a poster extracted at 00:35. The three original article videos remain unchanged and appear together in a three-column row. The opening Summary shows overall success rates, reported time to first success, and average execution times.

Ethernet rollout means are computed from the five selected recordings per model in the local report export, with inputs retained in `content/real-world-rollout-times.json`: Astra 22.235 min (5/5 successful), Fable 11.086 min (0/5 successful). The chart displays only Astra’s Ethernet rollout time; recording duration includes agent time.

## ChatGPT Sites hosting

`.openai/hosting.json` identifies the separate Sites project and its `out/` static output. The Sites publishing checkout includes generated assets; the GitHub repository still ignores them. Build with `python build.py --output out`, then package only `.openai/hosting.json` and `out/`.

For Sites delivery, the Ethernet hardware recording exceeds the per-asset limit. Re-encode the generated copy (preserving the original in `assets/`) before packaging:

```bash
ffmpeg -y -i assets/real-world/01_ethernet_hardware_control.mp4 -vf scale=960:-2 -c:v libx264 -preset fast -crf 25 -threads 2 -c:a copy -movflags +faststart out/assets/real-world/01_ethernet_hardware_control.mp4
```

The delivery copy keeps the full timeline; only resolution and compression change.

The opening Summary and Result combines overall and per-task success in model cards, followed by exploration and execution charts. Asterisks mark shorter times only where both agents completed the task. The old `evaluation-results` anchor points to the summary cards; task-method links target the report’s `strategyTabs` selector. Public task labels consistently use “Hanoi tower sorting”.
