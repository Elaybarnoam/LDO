# AI search discovery: crawler access and LDO

**Scope update:** the current project plan uses GitHub repository features only.
The Pages recommendation below is an unselected research alternative; see
[the accepted GitHub-only plan](github-discoverability.md).

Research date: 2026-10-16. Scope: official provider documentation; practical recommendations are identified separately from documented behavior. No external settings were changed.

## Documented crawler distinctions

| Provider / agent | Purpose | Implication |
| --- | --- | --- |
| OpenAI `OAI-SearchBot` | Discovery for ChatGPT search | Allow it if ChatGPT search visibility is desired; blocking it excludes search-answer inclusion, although navigational links may remain. |
| OpenAI `GPTBot` | Collection that may contribute to foundation-model training | Independent of search access. Allowing training is not necessary to permit search discovery. |
| OpenAI `ChatGPT-User` | Certain user-initiated page visits | This is not the automatic search crawler or the control for search eligibility; robots rules may not apply to these requests. |
| Anthropic `Claude-SearchBot` | Search discovery and relevance | Blocking it prevents Anthropic search indexing and may reduce search visibility. |
| Anthropic `Claude-User` | User-directed retrieval | Blocking it prevents retrieval through these requests. |
| Anthropic `ClaudeBot` | Potential training collection | Separate from search and user retrieval. |

OpenAI recommends allowing its search crawler and published IP ranges; it describes approximately 24 hours for systems to adjust to robots changes. This is not an indexing or ranking deadline. [OpenAI crawler reference](https://developers.openai.com/api/docs/bots)

Anthropic documents robots.txt controls for its three agents, including support for Crawl-delay. Search and training choices should be considered separately. [Anthropic crawler reference](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler)

## Google AI search

Google says ordinary search best practices also apply to AI Overviews and AI Mode. Supporting pages must be indexed and eligible for snippets. It calls for crawl access, internal links, important information in text, and structured data consistent with visible content. Neither eligibility nor compliant implementation guarantees crawling, indexing, or display. Google explicitly says additional AI text files or special AI markup are unnecessary. [Google AI features guidance](https://developers.google.com/search/docs/appearance/ai-features)

Consequently, `llms.txt` should not be presented as a proven ranking mechanism or a prerequisite for Google AI results. The reviewed OpenAI and Anthropic crawler documentation likewise provides no ranking guarantee for that file. This conclusion concerns the reviewed guidance, not every possible future agent implementation.

## Practical recommendation for LDO

The repository owner can improve README text, descriptions, topics, documentation links, and public releases. A file named `robots.txt` inside the GitHub repository does not set the policy for `github.com`: crawler policy is evaluated at the host root, not inside an arbitrary project directory. [Robots location and scope](https://developers.google.com/crawling/docs/robots-txt/create-robots-txt)

For control over published HTML, create a small GitHub Pages project site with a clear title such as **LDO: Causal Visual Loop Detection**, a concise factual summary, installation instructions, results with limitations, citation details, and direct links to source and releases. GitHub Pages publishes repository-managed static files and supports custom domains. This is a practical recommendation, not a documented ranking bonus. [GitHub Pages overview](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)

On the default project URL `elaybarnoam.github.io/LDO/`, publishing `/LDO/robots.txt` would not establish the host-root policy. Manage `/robots.txt` through the owner-level site, or use a custom domain whose root the project controls. Verify the final deployed location and effective directives before assuming the intended policy applies.

Prioritize accessible, factual HTML over crawler-specific tricks. Keep core explanations available as text rather than only videos, plots, or client-rendered interfaces; provide stable links to the method and reproducibility instructions. Measure actual indexing and referrals rather than treating crawler access as evidence of citations or favorable rankings.
