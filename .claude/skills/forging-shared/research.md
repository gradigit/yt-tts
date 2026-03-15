# Research Protocol

## Contents
- [Quick Forge Override](#quick-forge-override)
- [Research Objectives](#research-objectives)
- [Search Strategy](#search-strategy)
- [Quality Filters](#quality-filters)
- [Output Format](#output-format)
- [Research Scope Limits](#research-scope-limits)

Mandatory prior-art and implementation research for the **full** forge path. All research must meet the quality standards below.

## Quick Forge Override

If depth is set to **Quick**, skip research entirely. Record in transcript:
```
## Prior-Art Research
Skipped — Quick forge path
```
Proceed directly to gap analysis.

## Research Objectives

### For Prompt Perfection (Mode 1 / forging-prompts)
Search for:
1. **Existing solutions**: Does this already exist? Open source projects, commercial products, internal tools
2. **Similar implementations**: How have others solved similar problems?
3. **Best practices**: What do official docs and authoritative sources recommend?
4. **Known pitfalls**: What goes wrong? What are common mistakes?
5. **Technology landscape**: What tools, libraries, and frameworks are relevant? What do the docs for frameworks already in use recommend?

### For Plan Iteration (Mode 2)
Search for:
1. **Implementation patterns**: How is this typically built?
2. **Official documentation**: API docs, framework guides, library references
3. **Architecture examples**: Reference architectures for similar systems
4. **Performance benchmarks**: What results do others achieve?
5. **Migration/integration guides**: How to connect the pieces?

## Search Strategy

### Step 1: Broad Search
Run 2-3 web searches with different angles:
- Direct: `"{topic} implementation best practices {year}"`
- Alternative: `"{topic} tutorial guide {year}"`
- Problem-focused: `"{topic} common mistakes pitfalls"`

### Step 2: Deep Crawl
For each promising result:
1. Read the main page content
2. Identify relevant links on the page (documentation sections, API references, guides)
3. Follow those links and read the sub-pages
4. If it's documentation: navigate the sidebar/table of contents and read relevant sections
5. Do NOT stop at the landing page — the real information is usually 1-2 clicks deeper

### Step 3: Official Sources
Always search for and prioritize:
- Official documentation (docs.X.com, X.readthedocs.io)
- GitHub repositories (README, examples, issues)
- RFC/specification documents
- Academic papers (for algorithmic topics)

### Step 4: Cross-Reference
For any factual claim:
- Verify it appears in at least 2 independent sources
- If only 1 source: flag as "unverified" in findings
- If sources conflict: document both positions and the conflict

## Quality Filters

### ACCEPT (High Quality)
- Official documentation from the project/framework
- Well-maintained GitHub repos with active contributors
- Content from recognized domain experts (check author credentials)
- Conference talks and proceedings
- Peer-reviewed research
- Stack Overflow answers with high votes AND recent activity
- Content published within the last 2 years

### ACCEPT WITH CAUTION (Medium Quality)
- Blog posts from reputable engineering teams (company blogs)
- Tutorial sites with working code examples
- Stack Overflow answers that are older but highly upvoted
- Wikipedia (good for overviews, not for implementation details)

### REJECT (Low Quality)
- AI-generated SEO content (signs: generic advice, no code examples, keyword stuffing)
- Blog posts with no code examples or concrete details
- Outdated documentation (>2 years old, unless foundational)
- Content behind paywalls that can't be fully read
- Forum posts with no upvotes or verification
- Content that just restates the obvious without adding insight
- "Top 10 best X" listicles without depth
- Sources that contradict official documentation

### How to Identify AI-Generated SEO Spam
Red flags:
- Excessive use of "In today's fast-paced world..." or "Let's dive in..."
- Generic advice that applies to anything ("always write clean code")
- No specific code examples, versions, or concrete details
- Keyword-dense headings with thin content underneath
- Lists of vague benefits without implementation guidance

## Output Format

**Normal mode** (Mode 1 / forging-prompts): Save all research to `architect/transcript.md` under `## Prior-Art Research`.
**Plan mode** (Mode 2): Write research to plan.md as a `## [Iteration] Research Findings` section instead — plan mode restricts writing to plan.md only.

Template:

```markdown
## Prior-Art Research

### Existing Solutions
| Solution | URL | Relevance | Quality | Notes |
|----------|-----|-----------|---------|-------|
| {name} | {url} | High/Med/Low | Accepted/Caution/Rejected | {why} |

### Key Findings
1. {Finding with source citation}
2. {Finding with source citation}

### Unverified Claims
- {Claim}: found only in {source}. Needs verification.

### Conflicts
- {Topic}: Source A says X, Source B says Y. {Your analysis of which is correct and why.}

### Sources
- [{Title}]({URL}) — Quality: {rating} — Accessed: {date}
```

## Research Scope Limits

- Spend no more than 5-8 web searches per research phase
- Follow no more than 3 levels of links deep from any starting page
- If a topic has extensive official documentation, prioritize reading that over searching for more sources
- If research reveals the problem is already solved by an existing tool: present this to the user as a finding and ask whether to proceed with the original plan or adopt the existing solution
