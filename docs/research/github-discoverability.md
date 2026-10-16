# GitHub-only discoverability for LDO

The accepted scope is the repository, GitHub topics, documentation, releases,
issues, Discussions, the owner's profile and relevant GitHub resource lists.
No project website or off-GitHub promotion is part of this implementation.

## Implemented entry points

- The About description and README identify visual loop-closure detection,
  visual place recognition, MegaLoc, LightGlue and independent geometric evaluation.
- [Practical guides](../index.md#practical-guides) cover learned inference,
  correspondence evaluation and CPU result reproduction.
- [The precision/event walkthrough](../guides/precision-and-event-retention.md)
  explains a concrete saved finding, including a selected failure and limitations.
- [Starter issues #1–#3](https://github.com/Elaybarnoam/LDO/contribute) are linked
  directly from the README, roadmap, contribution guide and welcome discussion.
- The public research-preview release remains available; documentation additions
  are recorded under Unreleased rather than represented as new measured results.
- Resource-list candidates are reviewed for scope and contribution rules. A
  proposed entry remains a proposal until an independent maintainer accepts it.

## Resource-list fit

| Repository | Scope and decision |
| --- | --- |
| [gmberton/awesome-Visual-Place-Recognition](https://github.com/gmberton/awesome-Visual-Place-Recognition/blob/main/how-to-PR.md) | Requires a paper, venue/year and BibTeX. LDO has no publication entry; do not submit it as a paper. |
| [bas-db/intro-to-vpr](https://github.com/bas-db/intro-to-vpr#contributing) | Educational glossary contributions. A promotional software entry does not fit its term format. |
| [kanster/awesome-slam](https://github.com/kanster/awesome-slam#contributing) | Accepts fitting resources by PR; its code list is broad, but visible maintenance is old. |
| [SilenceOverflow/Awesome-SLAM](https://github.com/SilenceOverflow/Awesome-SLAM) | Invites PRs with a linked repository name and one-sentence introduction; inspect the relevant software section before proposing an entry. |

Use a factual entry describing a camera-only research tool, not a complete SLAM
system, a publication or a proven improvement to downstream localization. Submit
one scoped proposal rather than broadcasting issues or comments across projects.

## What these changes establish

Clear naming helps readers identify purpose. Topics organize GitHub discovery,
and `good first issue` labels help surface approachable work. Useful technical
guides give visitors something reproducible to evaluate and reference.
[GitHub topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics),
[contribution labels](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/encouraging-helpful-contributions-to-your-project-with-labels)

Google recommends relevant descriptive text and crawlable links; neither repository
changes nor a resource-list submission guarantees indexing or ranking. Repository
owners cannot insert verification tags into GitHub's page head or change the host's
robots policy through a repository file. Measure actual discovery separately from
implementation completion.
[Search Essentials](https://developers.google.com/search/docs/essentials),
[verification requirements](https://support.google.com/webmasters/answer/9008080)
