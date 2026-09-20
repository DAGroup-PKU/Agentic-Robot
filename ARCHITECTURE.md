# Growing Agent × Robot

## Current structure

```text
Agent × Robot
├── Home /                          blog cards → articles + interactive evidence
├── Blogs /blogs/                   narrative and project updates
│   └── /posts/<slug>/              one article, one or more related projects
├── Projects /projects/             directory of research efforts
│   ├── /projects/robodojo/         stable project context → interactive report
│   └── /projects/physical-manipulation/
└── About /about/                   shared research questions
```

Only Home and Blogs appear in the current navigation. Project and About routes remain available for future expansion; blog evidence links currently go directly to the external interactive reports.

The blog explains a result. A project page provides lasting context and collects its updates. An interactive report holds the detailed experimental evidence. More articles do not require more interactive applications.

## Future expansion

1. Choose the umbrella domain and review the initial article copy. Add social preview images and canonical URLs only after the domain is known.
2. Add independent reports using complete HTTPS URLs in each project's `results_path` and evidence `path` fields. The resolver already supports this. If multiple posts share many report versions, introduce a report registry so those addresses are managed in one place.
3. Add new projects through content records. RoboTwin and agent-assisted data collection can each have their own project page, protocol, and related updates when evidence is ready. No future results are implied by the current website.
4. Keep incompatible interactive applications separate behind stable links. Consolidate repeated components—video players, metric cards, protocol sections—when a second report actually needs them. A shared repository does not require one giant frontend.
5. Version experiment snapshots within each report. Journal articles should link to the snapshot used for their claims; a latest-results link can be offered separately. Record dataset/policy revision, run ID, protocol version, timestamp, and measurement definitions.
6. Introduce RSS, topic tags, and pagination as the journal grows. Introduce a CMS only if nontechnical editing becomes a real need; these JSON and HTML files keep the first iteration easy to review.

## Content boundaries

- Simulation and physical trials retain their own evaluation definitions and denominators.
- Historical diagnostics stay labeled separately from controlled comparisons.
- A post can cover multiple projects; each project can accumulate multiple posts.
- Project card numbers are directory identifiers, not rankings.
- Screenshots and diagrams load locally; large recordings remain in the existing interactive reports.

## Hosting

The current generator exports ordinary static files with no runtime dependency. Keep the editorial site on the main domain, and use stable project routes or subdomains for interactive reports. Add redirects if report hosting changes so old posts retain working evidence links.
