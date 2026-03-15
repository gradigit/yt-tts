# Examples

## Contents
- [Mode 1 Example: Full Forge](#mode-1-example-full-forge)
- [Mode 1 Example: Quick Forge](#mode-1-example-quick-forge)
- [Mode 2 Example: Plan Iteration](#mode-2-example-plan-iteration)
- [Resumption Examples](#resumption-examples)

## Mode 1 Example: Full Forge

### Input
User: "I need a CLI tool that converts markdown to slides"

### Skill Activation
Skill detects normal mode → Mode 1 activates.

### Depth Selection
```
Skill: "How deep should we go? Quick or Full?"
User: "Full"
```

### Questionnaire (abbreviated — adaptive protocol)
```
--- Categories 1-3 (always asked) ---

Q: What exactly is this? One sentence.
A: A CLI tool that takes a markdown file and produces a slide deck.

Q: What format should the slides be? (HTML, PDF, PowerPoint, reveal.js)
A: HTML-based, viewable in browser. Like reveal.js but simpler.

Q: Single file or multi-file input?
A: Single markdown file. Use --- as slide separator.

Q: Who's the audience?
A: Developers who want to make quick presentations without leaving the terminal.

--- Adaptive assessment for categories 4-12 ---

Skill: "Based on your answers, here's my recommendation:"

| Category | Recommendation | Reason |
|----------|---------------|--------|
| 4. Architecture & Structure | Ask | CLI tool needs clear component design |
| 5. Edge Cases & Error Handling | Ask | Markdown parsing has many edge cases |
| 6. Scale & Performance | Skip | Single-file CLI tool, no scale concerns |
| 7. Security & Privacy | Skip | No sensitive data, local file processing |
| 8. Integration & Dependencies | Ask | Parser, template engine choices matter |
| 9. Testing & Verification | Ask | Need to verify output quality |
| 10. Deployment & Operations | Ask | npm/brew distribution decision needed |
| 11. Trade-offs & Priorities | Ask | MVP vs polished — important for scope |
| 12. Scope & Boundaries | Ask | Must define what's v1 vs future |

User: "Looks right. Skip 6 and 7."

[Skill asks full question sets for selected categories]
```

### Prior-Art Research
```
Found: reveal.js, Marp, Slidev, mdx-deck, remark
Key finding: Marp already does this well. Present to user.
User decision: Proceed anyway — want something lighter with custom theme support.
```

### Gap Analysis
```
- Missing: What about speaker notes? Images? Code highlighting?
- Missing: Package distribution (npm? brew? standalone binary?)
- Assumption: User wants a new tool, not a plugin for existing one — confirmed.
```

### Challenge Phase
```
Self-critique found:
- No mention of accessibility (keyboard nav, screen readers)
- No offline support requirement stated
- "Simpler than reveal.js" is vague — needs specific differentiators

Sub-agent found:
- The prompt doesn't specify what "custom theme support" means technically
- No mention of live reload during development
- Missing: how to handle markdown features that don't map to slides (footnotes, TOC)
```

### Final Prompt (architect/prompt.md)
```markdown
Build a CLI tool called "deckr" that converts Markdown files into
browser-viewable HTML slide presentations.

## Core Requirements
- Input: Single .md file using --- as slide separator
- Output: Self-contained HTML file viewable in any modern browser
- Syntax: Standard CommonMark + code highlighting via highlight.js
- Themes: CSS-based theming with 3 built-in themes (light, dark, terminal)
- Custom themes: Load user CSS file via --theme flag
...

## Verification
- Convert sample.md with 10 slides — renders correctly in browser
- Code blocks are syntax highlighted
- Custom theme CSS applies without errors
- --- inside code fences does NOT split slides
```

## Mode 1 Example: Quick Forge

### Input
User: "I want to add a --config flag to load settings from a JSON file"

### Depth Selection
```
Skill: "How deep should we go? Quick or Full?"
User: "Quick — this is straightforward"
```

### Questionnaire (categories 1-3 only)
```
Q: What exactly is this?
A: A --config flag that loads tool settings from a JSON file instead of CLI args.

Q: What settings should be configurable?
A: Theme, output directory, slide dimensions, and highlight.js theme.

Q: What must it NOT do?
A: No YAML or TOML — JSON only. No merging with CLI args — config wins if present.

Q: Does anything like this already exist in the codebase?
A: No, all config is currently CLI flags.

Categories 4-12: Skipped — Quick forge path
```

### Gap Analysis + Self-Critique
```
Gap: What happens if the JSON is malformed?
User: Show error with line number and exit 1.

Self-critique:
- Missing: What's the default config file name? (.deckrrc? deckr.config.json?)
- Missing: Should --config accept a path or always look in cwd?
Resolution: User confirms: --config <path> explicit only, no auto-discovery.
```

### Final Prompt
```markdown
Add a --config flag to deckr that loads settings from a JSON file.

## Requirements
- --config <path> loads a JSON file with keys: theme, outputDir, dimensions, highlightTheme
- Config values override defaults but CLI args are not merged (config wins entirely)
- Malformed JSON: print error with line number, exit code 1
- Missing file: print "Config file not found: <path>", exit code 1
- No auto-discovery — only explicit --config <path>

## Verification
- --config valid.json applies all settings
- --config malformed.json shows parse error with line number
- --config missing.json shows file not found error
```

## Mode 2 Example: Plan Iteration

### Context
User completed Mode 1, cleared context, entered plan mode, and pasted the perfected prompt. Claude generated a plan with 15 tasks. User invokes /forging-plans to iterate.

### Step 1: Review Plan + Mode 1 Artifacts
```
Skill reads plan.md (current plan) and architect/ files:
- architect/transcript.md — original Q&A across selected categories
- architect/STATE.md — key decisions from Mode 1
- architect/prompt.md — the perfected prompt

Cross-checking plan against original requirements...
```

### Plan Review
```
Issues found:
1. Task 3 (Parse markdown) doesn't account for nested code blocks containing ---
2. Task 7 (Theme system) is vague about CSS variable structure
3. No task for generating speaker notes HTML (requirement from Q&A Category 2)
4. Task 12 (Tests) only covers happy path
```

### Research + Challenge (written to plan.md as temporary sections)
```
## [Iteration] Research Findings
Searched: "markdown slide parser edge cases"
Found: Common issue with --- inside code fences. Marp uses regex
lookahead. Remark-based parsers handle this natively.
Recommendation: Use remark/unified ecosystem for parsing.

## [Iteration] Challenge Results
Self-critique: Plan doesn't address content overflow on long slides.
Need a max-height strategy.

Sub-agent: "Tight coupling between parsing and rendering. If user later
wants PDF export, this architecture makes it hard. Suggest separating
parse → AST → render into distinct steps."
```

### Finalize
```
Plan updated with fixes. [Iteration] sections removed.
Execution prompt verified at end of plan.md. Plan is clean.
User accepts → "Yes, clear context and proceed" → execution begins.
```

## Resumption Examples

### Mode 1 Resumption
User ran Mode 1, completed questionnaire, then closed terminal.

```
Skill reads architect/STATE.md:
  Current Stage: prior-art-research
  Mode: 1
  Depth: full
  Categories Asked: [1, 2, 3, 4, 5, 8, 9, 10, 11, 12]
  Categories Skipped: [6 — no scale concerns, 7 — no security concerns]
  Key Decisions: [list]

Skill: "I see you completed the questionnaire and were about to start
prior-art research. Resume from there, or start over?"

User: "Resume"

Skill continues from Step 4.
```

### Mode 2 Resumption
User was iterating on a plan in plan mode, then closed terminal.

```
Skill detects plan mode. Reads plan.md — finds [Iteration] sections:
  - [Iteration] Research Findings (complete)
  - [Iteration] Challenge Results (partial — self-critique done, no sub-agent)

Skill: "I see you were iterating on the plan. Research is done, and
self-critique is complete. Sub-agent review hasn't run yet. Resume
from the sub-agent challenge, or start a fresh review?"

User: "Resume"

Skill continues from Phase B of the challenge protocol.
```
