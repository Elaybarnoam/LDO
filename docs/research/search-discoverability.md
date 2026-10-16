# LDO search discoverability: evidence and recommended actions

**Scope update:** the owner has chosen discovery entirely within GitHub repository
pages and features. The active plan is [GitHub-only discoverability](github-discoverability.md).
Website deployment, Search Console setup and off-GitHub promotion below are
historical alternatives considered during research, outside the accepted scope.

Research date: 2026-10-16. Scope: Google Search, Google AI search features,
independent AI search tools, and the public LDO repository. This is a research
note, not a deployment. Recommendations below are judgments based on the cited
guidance; they are not measured ranking improvements or probability estimates.

## Recommendation

Build a small static GitHub Pages project site, verify its URL-prefix property in
Google Search Console, and publish useful, clearly named technical pages linked
to the source repository. Then obtain relevant references by sharing reproducible
work with interested communities. Keep the existing repository and LDO name;
consistently pair the acronym with its descriptive title.

The reason for a separate site is control over published HTML and verification,
not an inherent ranking bonus for GitHub Pages. GitHub documents Pages as static
hosting from repository files. [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)

## Current observations

| Check | Observation | Interpretation |
| --- | --- | --- |
| Anonymous repository request | HTTP 200; README prose present in the HTML response | Core content is available without login or a JavaScript-only application shell |
| Indexing exclusions in that response | No `X-Robots-Tag` header or robots/googlebot meta directive found | No such exclusion was observed; this does not establish Google's actual crawl/index status |
| Title and description | GitHub includes the descriptive project summary in both | Existing repository metadata is already useful; repeat changes alone are unlikely to solve discovery |
| GitHub metadata | Public; eight relevant topics; homepage unset | Internal discoverability work exists; no project website is linked |
| Pages API | Repository Pages endpoint returned HTTP 404 | No Pages deployment was available through that endpoint at audit time |
| Search samples | Exact owner/repository and project-title searches did not return LDO in the results supplied by the available search service | A weak visibility signal, not a Google index exclusion diagnosis or a verified Google ranking |

These observations came from anonymous HTTP checks and GitHub's read-only API.
Public source: [repository](https://github.com/Elaybarnoam/LDO). Google requires
crawler access, a successful HTTP response and indexable content for eligibility;
meeting these requirements does not guarantee indexing.
[Technical requirements](https://developers.google.com/search/docs/essentials/technical)

GitHub's inspected robots policy includes a named `OAI-SearchBot` group with
path-specific restrictions. It does not contain a blanket prohibition for the
repository root `/Elaybarnoam/LDO`; some routes, such as tree/raw routes and
certain query parameters, are restricted. This is a policy observation, not proof
of access by every provider or network. A repository file cannot change the
host's policy. [GitHub robots.txt](https://github.com/robots.txt),
[robots scope](https://developers.google.com/crawling/docs/robots-txt/create-robots-txt)

## Priority 1: descriptive identity and relevant queries

Use **LDO: Causal Visual Loop Detection** consistently across the README, site,
release descriptions and author profile. In introductory prose, naturally explain
the relationship to **visual loop-closure detection**, **visual place recognition**,
**MegaLoc**, **SuperPoint/LightGlue**, and **independent geometric evaluation**.
Do not advertise inertial fusion or downstream SLAM benefits as implemented.

Suggested initial discovery targets, without claims about their search volume:

- `LDO visual loop detection`
- `Elay Barnoam loop closure`
- `MegaLoc LightGlue loop closure`
- `visual place recognition geometric evaluation`
- `loop closure supported contradicted unknown matches`

Google recommends words users would search for in titles, main headings, link
text and other descriptive locations. This supports accurate descriptive naming;
it does not mean repeating keywords or renaming the repository guarantees rank.
[Search Essentials](https://developers.google.com/search/docs/essentials),
[title guidance](https://developers.google.com/search/docs/appearance/title-link)

## Priority 2: an owner-controlled, crawlable project site

Suggested default address: `https://elaybarnoam.github.io/LDO/`, subject to Pages
setup and availability. A custom domain is optional. Use static HTML or a static
documentation generator; make core content and navigation available without
requiring client-side JavaScript.

Start with five substantive pages:

| Page | What it should answer |
| --- | --- |
| Overview | What is LDO, who wrote it, what works today, and where are source/releases? |
| Quickstart | What can someone reproduce on CPU, and what requires external models/data? |
| Method | How do retrieval, original assignments, operational verification and independent assessment differ? |
| Results and limitations | What do saved counts show, what failed promotion, and what remains unknown? |
| Contribute and cite | Which starter tasks exist, where are questions handled, and what license/citation applies? |

Use a distinct descriptive HTML title and summary for each page. Add ordinary
`<a href>` navigation and links from the README, repository homepage field and
author profile. Keep result tables, definitions and captions as text in addition
to figures; a GIF alone does not explain a method to a text reader.
[Crawlable links](https://developers.google.com/search/docs/crawling-indexing/links-crawlable),
[Google AI guidance](https://developers.google.com/search/docs/appearance/ai-features)

Use stable URLs, sensible self-canonical URLs and an XML sitemap listing the real
published pages. A sitemap helps discovery; it does not guarantee indexing or
increase ranking by itself. Avoid creating many near-duplicate promotional pages.
[Sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap),
[canonical URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)

## Priority 3: verify and measure with Search Console

For the proposed Pages URL, add a **URL-prefix property** for the exact HTTPS
project prefix. Verify using Google's supplied HTML tag or verification file,
which requires the owner's Google account. A tag can be placed in the Pages HTML;
it cannot be inserted into GitHub's repository-page `<head>` through a README.
Do not attempt to verify ownership of the `github.com` or `github.io` domain.
[Ownership verification](https://support.google.com/webmasters/answer/9008080)

After deployment and verification:

1. Inspect the homepage URL for access, indexing and canonicalization problems.
2. Submit the project sitemap and request homepage indexing once.
3. Record indexing status and any stated exclusion reason.
4. Review impressions, queries and clicks periodically as data becomes available.
5. Fix a diagnosed problem before requesting another crawl.

Google says recrawling can take days to weeks, with no inclusion guarantee;
repeated requests do not make the same URL crawl faster. A `site:` query is only a
rough public check: its results are not exhaustive.
[Recrawl requests](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl),
[site-operator limitations](https://developers.google.com/search/docs/monitor-debug/search-operators/all-search-site)

## Priority 4: earn relevant references with useful work

Publish one substantial technical walkthrough explaining a question that LDO can
answer: for example, why higher judged match precision can coexist with losing a
useful revisit event. Include the actual table, failure case, reproduction command,
limits and links to the method and source. Share it where robotics/computer-vision
project posts are welcome, and link from the author's public project profile.

Relevant external pages can give readers context and crawlers a route to the
project. Google documents links as discovery and relevance signals. No particular
number of links guarantees a position. References should arise from useful work,
not purchased ranking links or automated issue/comment promotion.
[Link guidance](https://developers.google.com/search/docs/crawling-indexing/links-crawlable),
[spam policies](https://developers.google.com/search/docs/essentials/spam-policies)

## Priority 5: make accurate evidence easy for AI search to retrieve

Google AI Overviews and AI Mode use the ordinary search foundation. Google says
supporting pages must be indexed and snippet-eligible, with no special AI text
files or schema required. A practical LDO response is short, factual explanations,
clear tables, stable method links and honest scope statements, backed by the
existing evidence record. These improve accessibility and clarity; they do not
guarantee a citation.
[Google AI requirements](https://developers.google.com/search/docs/appearance/ai-features)

OpenAI separates `OAI-SearchBot` for search from `GPTBot` for potential training.
Allowing model training is not required to permit ChatGPT search discovery.
Anthropic similarly distinguishes search, user retrieval and training agents.
Check the deployed host's policy and any CDN challenges against the current
provider guidance. [OpenAI bots](https://developers.openai.com/api/docs/bots),
[Anthropic crawlers](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler)

On a default project Pages site, `/LDO/robots.txt` does not govern the hostname.
Robots policy belongs at `/robots.txt` on the host, managed through an owner-level
Pages site or a custom domain as appropriate. Do not add a broad policy without
checking its effects on other projects hosted on the same hostname.
[Robots location](https://developers.google.com/crawling/docs/robots-txt/create-robots-txt)

Optional factual `SoftwareSourceCode` JSON-LD can describe the source repository,
author, programming language and license scope on the project site. It is a
semantic description, not a promised Google rich result or ranking factor.
Google's separate software-app rich result has additional requirements; do not
invent ratings or reviews to meet them.
[SoftwareSourceCode](https://schema.org/SoftwareSourceCode),
[software-app requirements](https://developers.google.com/search/docs/appearance/structured-data/software-app)

## Lower priorities and limits

- Keep the social preview for recognizable shared links. It is not an indexing
  request or a proven ranking mechanism.
- Do not treat badges, star counts or commit frequency as verified direct Google
  ranking controls; the reviewed primary guidance establishes no such rule.
- Do not prioritize `llms.txt` ahead of accessible content, verification and useful
  references. Google explicitly says extra AI files are unnecessary.
- Do not multiply generic AI-written articles merely to target more queries;
  Google warns against scaled content without added value.
- Search discovery, ranking, AI retrieval and AI citation are different outcomes.
  No credible numerical probability improvement can be assigned from this audit.

[Google generative-search optimization](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide),
[AI-content guidance](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content)

## Execution order and acceptance checks

| Order | Work | Reviewable result |
| --- | --- | --- |
| 1 | Align descriptive naming and prepare the five-page static site | Accurate titles, readable HTML, working links, real examples and explicit limits |
| 2 | Deploy Pages and link it from the repo | Public HTTPS pages return 200; core text appears in anonymous responses |
| 3 | Check crawler policy and metadata | No unintended robots/noindex exclusion; sitemap and canonicals reference deployed URLs |
| 4 | Verify Search Console with the owner account | Property verified; homepage inspection and sitemap submission recorded |
| 5 | Publish and share one substantive walkthrough | Useful public explanation linking to code, reproducible evidence and contribution tasks |
| 6 | Monitor after search data accumulates | Indexing state, impressions, queries, clicks and identifiable referrals reviewed separately |

The existing release, contribution issues and saved-evidence presentation support
this plan. They do not substitute for deployment, verification or actual search
performance measurements. Detailed crawler distinctions are in
[the companion research note](ai-search-crawlers.md).
