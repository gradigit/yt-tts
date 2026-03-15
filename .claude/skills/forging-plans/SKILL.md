---
name: forging-plans
description: Perfects rough ideas into implementation-ready prompts and plans through adaptive questioning, gap analysis, mandatory prior-art research, and adversarial challenge phases. Activates when user asks to "forge a plan", "perfect this prompt", "flesh out this idea", "forging-plans", or mentions prompt/plan perfection. Operates in two modes based on context.
license: MIT
metadata:
  version: "1.3.0"
  author: gradigit
  tags:
    - planning
    - prompt-engineering
    - research
    - workflow
  triggers:
    - "forge a plan"
    - "perfect this prompt"
    - "flesh out this idea"
    - "forging-plans"
---

# Forging Plans

Transforms rough ideas into perfected prompts and plans through a structured, multi-phase pipeline with adaptive clarification, mandatory research, and adversarial challenge phases.

## Mode Detection

Detect current mode and validate readiness:

**If in normal mode** → Mode 1 (Prompt Perfection). Proceed with workflow.

**If in plan mode** → Check for Mode 1 artifacts before starting Mode 2:
1. Check if `architect/prompt.md` exists
2. Check if `architect/transcript.md` exists

| Artifacts Found | Action |
|----------------|--------|
| Both exist | Mode 1 completed. Proceed with Mode 2 (Plan Iteration). |
| Neither exists | Mode 1 was skipped. Show the guidance below. |
| Partial | Mode 1 was interrupted. Check `architect/STATE.md` and advise resuming Mode 1 first. |

**Mode 1 skipped guidance** (when user is in plan mode with no architect/ artifacts):
> You're in plan mode, but the prompt perfection phase hasn't been run yet. The prompt you're working from may have gaps that will carry through to the plan and execution.
>
> I recommend:
> 1. Exit plan mode (Shift+Tab or /plan)
> 2. Run `/forging-plans` in normal mode — I'll perfect your prompt through Q&A, research, and adversarial challenge
> 3. Once done, I'll guide you back to plan mode with the perfected prompt
>
> Want to exit and start with prompt perfection, or proceed with planning as-is?

If the user chooses to proceed anyway, run Mode 2 normally but note that results will be limited without Mode 1 context.

## Mode 1: Prompt Perfection

### Workflow

```
- [ ] 1. Capture rough idea
- [ ] 2. Depth selection (quick or full)
- [ ] 3. Adaptive questionnaire (see questionnaire.md)
- [ ] 4. Prior-art research (see research.md) [full only]
- [ ] 5. Gap analysis + improvement suggestions
- [ ] 6. Draft prompt v1
- [ ] 7. Self-critique (see challenge.md)
- [ ] 8. Sub-agent challenge review (see challenge.md) [full only]
- [ ] 9. Iterate until user approves
- [ ] 10. Save all artifacts to architect/
- [ ] 11. Present final prompt + handoff instructions
```

### Step 1: Capture Rough Idea

Ask user for their rough idea. Accept any format: sentence, paragraph, bullet points, pasted text.

Save raw input immediately to `architect/transcript.md`:
```markdown
# Forging Plans Transcript
## Project Context: {new project | existing project — summary}
## Raw Input
{user's rough idea}
---
```

### Step 2: Depth Selection

Present the user with a depth choice:

> **How deep should we go?**
>
> - **Quick** — Core questions only (categories 1-3), skip research, self-critique only (no sub-agent), one iteration max. Good for small, well-understood features where you already know what you want.
> - **Full** (default) — Adaptive questionnaire (categories 1-3 + recommended), prior-art research, full challenge protocol. Good for complex, ambiguous, or high-stakes features.

If the user doesn't choose, default to **Full**.

Record the choice in `architect/STATE.md`:
```markdown
# Forge State
## Depth: {quick | full}
```

### Step 3: Adaptive Questionnaire

Run the questionnaire from [questionnaire.md](../forging-shared/questionnaire.md). The file contains the adaptive protocol and quick forge override — follow it based on the depth selected in Step 2.

Use the `AskUserQuestion` tool for structured questions. Group related questions (max 4 per call). For open-ended questions, ask directly in text.

Append every Q&A pair to `architect/transcript.md` under a `## Questionnaire` section.

After each batch, update `architect/STATE.md`:
```markdown
# Forge State
## Current Stage: questionnaire
## Mode: 1
## Depth: {quick | full}
## Categories Asked: [list]
## Categories Skipped: [list with reasons]
## Categories Remaining: [list]
## Key Decisions:
- {decision}: {rationale}
```

### Step 4: Prior-Art Research [full only]

**Skip for quick path.** Record `"Research: Skipped — Quick forge path"` in transcript.

For full path: follow the research protocol in [research.md](../forging-shared/research.md).

Search for: existing solutions, similar implementations, relevant documentation, best practices, known pitfalls.

Deep crawl: do not stop at landing pages. Follow relevant links. Read sub-pages. Find actual documentation, not just overviews.

Save findings to `architect/transcript.md` under `## Prior-Art Research`.

### Step 5: Gap Analysis

Review all Q&A answers and research findings (if available). Identify:

1. **Missing information**: What did the user not mention that matters?
2. **Contradictions**: Do any answers conflict with each other or with research?
3. **Unstated assumptions**: What is being assumed but never confirmed?
4. **Missing constraints**: What limits exist that haven't been discussed?
5. **Missing success criteria**: How will we know the output is correct?

Present all gaps to the user. Ask follow-up questions for each.

### Step 6: Draft Prompt v1

Synthesize everything into a structured prompt. The prompt must:

1. Clearly state the goal
2. Include all requirements and constraints from Q&A
3. Reference relevant prior art and best practices found (if research was done)
4. Specify success criteria and verification methods
5. Include context that Claude needs but can't infer

The prompt should be a clean specification — no workflow meta-instructions.

Save draft to `architect/prompt.md` as v1.

### Step 7: Self-Critique

Run Phase A (self-critique) from [challenge.md](../forging-shared/challenge.md).

Structured self-review of the prompt against challenge questions. Document all issues found.

### Step 8: Sub-Agent Challenge Review [full only]

**Skip for quick path.**

Run Phase B (sub-agent review) from [challenge.md](../forging-shared/challenge.md).

Spawn a sub-agent with instructions:
> "You are a critical reviewer. Read architect/prompt.md and architect/transcript.md. Your job is to find flaws, gaps, ambiguities, and weaknesses. Be adversarial. List every issue you find, ranked by severity."

Reconcile findings from both phases. Present all issues to user. Fix confirmed issues.

### Step 9: Iterate

Present the refined prompt to the user. Ask:
1. Does this capture everything accurately?
2. Is anything missing or wrong?
3. Should any part be rephrased or restructured?

**Quick path**: One iteration max. Incorporate feedback and finalize.
**Full path**: Repeat Steps 6-8 as needed until user approves.

### Step 10: Save Artifacts

Save to project root `architect/` directory:

| File | Purpose | Reader |
|------|---------|--------|
| `transcript.md` | Full Q&A log, research, challenge results | Human |
| `STATE.md` | Current stage + key decisions summary | AI (resumption) |
| `prompt.md` | Perfected prompt (final version) | Human + AI |

**Generate CLAUDE.md** (required): Create a `CLAUDE.md` in the project root with:

```markdown
# {Project Name}

{One-line description from Core Vision}

## Build Commands
{Build, test, and run commands from questionnaire and research}

## Project Structure
{Key directories and their purpose}

## Conventions
{Coding conventions, naming patterns, architectural decisions from Q&A}

## architect/ Directory

**Read `architect/plan.md` for implementation instructions.** This is the execution plan — follow it phase by phase.

The other files in architect/ are pre-planning artifacts. Do not treat them as instructions:
- `prompt.md` — the original specification used to generate the plan. Reference only. The plan supersedes it.
- `transcript.md` — Q&A log from the planning process. Reference only. Useful if you need to understand why a decision was made.
- `STATE.md` — planning skill state. Ignore during execution.

## Current Phase
Phase: {not started}
Next step: {what to do next}

## Phase Progress
{List phases from the plan with status: pending}
```

The CLAUDE.md serves as persistent context that survives context clears. It is the executing agent's primary orientation file.

**Generate `TODO.md`** (required): Create a `TODO.md` in the project root. This is the executing agent's persistent task tracker — it replaces Claude Code's session-scoped TaskCreate/TaskUpdate which don't survive context clears.

```markdown
# TODO

## Current Phase: {phase name}

### In Progress
- [ ] {current step being worked on}

### Completed
- [x] {step} — {brief outcome or note}

### Blocked / Issues
- {description of blocker and what was tried}

### Deviations from Plan
- {anything that changed from architect/plan.md and why}
```

**CRITICAL: The executing agent MUST update `TODO.md` after every significant step** — completing a file, passing a test, hitting an error, making a decision that deviates from the plan. Context can be cleared at any moment. If TODO.md is current, a fresh session reads CLAUDE.md → TODO.md → architect/plan.md and knows exactly where to resume. If TODO.md is stale, the agent has to re-derive state by reading source files, which is slow and error-prone.

Also update CLAUDE.md's "Current Phase" and "Next step" fields when transitioning between phases.

**Copy plan to project** (required, during Mode 2 finalize): After Mode 2 produces the final plan, save a copy to `architect/plan.md` so the plan is on disk in the project — not only in `~/.claude/plans/`. This ensures a new session can read the plan without knowing the plans directory hash.

### Step 11: Handoff Instructions

Present to user:
```
Artifacts saved:
  architect/prompt.md — perfected prompt
  CLAUDE.md — project context for executing agent
  TODO.md — persistent task tracker (agent updates this during execution)

To continue:
1. /clear to reset context
2. Enter plan mode (Shift+Tab)
3. Paste architect/prompt.md contents as first message
4. Once Claude drafts a plan, invoke /forging-plans for Mode 2 iteration
5. Approve final plan → "clear context and proceed" → execution begins

CLAUDE.md persists across context clears — the executing agent reads it automatically.
architect/ files persist on disk for Mode 2 reference but are ignored during execution.
```

## Mode 2: Plan Iteration

> **Plan mode constraint**: Mode 2 runs in plan mode where only plan.md is writable. All Mode 2 output (research findings, challenge results, iteration state) goes into plan.md as temporary sections. Read architect/ files from Mode 1 for context — they are read-only reference.

### Workflow

```
- [ ] 1. Review plan + Mode 1 artifacts
- [ ] 2. Structured plan review (gaps, risks, dependencies)
- [ ] 3. Prior-art research for implementation approaches
- [ ] 4. Self-critique then sub-agent challenge on plan
- [ ] 5. Iterate with user until plan is approved
- [ ] 6. Finalize plan.md (strip iteration artifacts, embed execution prompt)
```

### Step 1: Review Plan + Mode 1 Artifacts

Read the current plan in plan.md. Also read Mode 1 artifacts for context:
- `architect/transcript.md` — original requirements, Q&A decisions, research
- `architect/STATE.md` — key decisions summary
- `architect/prompt.md` — the perfected prompt that initiated this plan

These are read-only reference. Mode 2 does not write to architect/.

### Step 2: Structured Plan Review

Evaluate the plan against the original prompt and Mode 1 artifacts:
- Are all requirements from the prompt addressed?
- Are dependencies between tasks identified?
- Are verification/testing strategies included for each component?
- Are edge cases and error scenarios handled?
- Is the task ordering logical?

### Step 3-4: Research + Challenge

Same protocols as Mode 1 but applied to the plan. Follow [research.md](../forging-shared/research.md) and [challenge.md](../forging-shared/challenge.md).

Write findings to plan.md as temporary iteration sections:
```markdown
## [Iteration] Research Findings
{research results}

## [Iteration] Challenge Results
{self-critique and sub-agent findings}
```

These sections are stripped during finalization (Step 6).

### Step 5: Iterate

Present findings and suggestions. Update the plan based on approved changes. Repeat Steps 2-4 as needed until user approves.

### Step 6: Finalize

Before the user accepts the plan:
1. Remove all `## [Iteration]` sections from plan.md
2. Ensure the plan is clean and execution-ready
3. Verify the execution prompt section is at the end:
   - Key decisions and trade-offs
   - Context the executing agent needs
   - Verification commands and success criteria
   - Directive to ignore architect/ directory
4. Save a copy of the finalized plan to `architect/plan.md` (persistent, in-project reference)
5. Update `CLAUDE.md` — set "Current Phase" to Phase 1, populate "Phase Progress" with phases from the plan

## Resumption

**Mode 1** (normal mode): If `architect/STATE.md` exists, read it. Ask user:
- "I see you were at stage {X}. Resume from there, or start over?"

**Mode 2** (plan mode): Check plan.md for `## [Iteration]` sections. If present, Mode 2 was interrupted mid-iteration. Ask user:
- "I see you were iterating on the plan. Resume from there, or start a fresh review?"

Also read `architect/STATE.md` for Mode 1 context (key decisions, completed categories).

## Research Quality Standards

All web research must follow [research.md](../forging-shared/research.md). Key rules:
- Official documentation first, always
- Reject information older than 2 years (unless foundational)
- Cross-reference factual claims across 2+ sources
- Deep crawl: follow links, read sub-pages, find actual content
- Reject AI-generated SEO spam and low-quality blog posts

## Example

**Input** (Mode 1):
```
User: "I need a CLI tool that converts markdown to slides"
```

**Output** (after full pipeline):
```
CLAUDE.md — Project context for executing agent (build commands, conventions, architect/ guide).
TODO.md — Persistent task tracker. Agent updates this after every step during execution.
architect/prompt.md — Original specification (reference only during execution).
architect/transcript.md — Q&A log and research (reference only during execution).
architect/STATE.md — Planning skill state (ignore during execution).
architect/plan.md — Finalized implementation plan (the execution instructions).
```

For complete step-by-step walkthroughs of both modes, see [examples.md](examples.md).

## Self-Evolution

Update this skill when:
1. **On correction**: User identifies a gap in questioning → update questionnaire.md in forging-shared/
2. **On new pattern**: Discover effective challenge technique → update challenge.md in forging-shared/
3. **On research failure**: Source quality filter misses bad data → tighten research.md in forging-shared/
4. **On workflow friction**: User finds a step unhelpful → streamline

**Applied Learnings:**
- v1.3.0: CLAUDE.md + TODO.md as required artifacts. Plan copied to architect/plan.md. architect/ directory guide in CLAUDE.md. Git/docs questions in Category 4. Execution continuity across context clears.
- v1.2.0: Adaptive questionnaire (1-3 always, 4-12 assessed). Quick forge path. Removed self-encoded Mode 2 instructions from prompt output. Unified reference files in forging-shared/.
- v1.1.0: Mode 2 writes to plan.md only (plan mode constraint). Added Mode 2 guard and transition guidance.
- v1.0.0: Initial version

Current version: 1.3.0. See [CHANGELOG.md](CHANGELOG.md) for history.
