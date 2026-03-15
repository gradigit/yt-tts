---
name: forging-prompts
description: Perfects rough feature ideas into implementation-ready prompts for use mid-project. Designed for forked sessions where project context is already loaded. Activates when user asks to "forge a prompt", "sharpen this prompt", "flesh out this feature", "forging-prompts", or mentions mid-project prompt perfection.
license: MIT
metadata:
  version: "1.3.0"
  author: gradigit
  tags:
    - prompt-engineering
    - planning
    - workflow
  triggers:
    - "forge a prompt"
    - "sharpen this prompt"
    - "flesh out this feature"
    - "forging-prompts"
---

# Forging Prompts

Transforms rough feature ideas into perfected prompts through adaptive questioning, gap analysis, mandatory research, and adversarial challenge phases. Designed for mid-project use in forked sessions.

## Mode Guard

This skill is designed for **normal mode in a forked session**. If plan mode is detected, advise the user:
> This skill is designed for normal mode (not plan mode). It needs to write files to architect/ which plan mode restricts.
>
> If you want to perfect a prompt for a new project with plan mode integration, use `/forging-plans` instead.
> If you want to perfect a prompt mid-project, exit plan mode first (Shift+Tab or /plan), then invoke this skill.

## When to Use

Use this skill when adding a feature or making changes to an **existing project** mid-session:

1. You're working in Session A with full project context
2. You have a rough idea ("I want to add theme support")
3. You fork the session: `claude --continue --fork-session`
4. In the forked session, invoke this skill
5. The skill produces `architect/prompt.md`
6. You return to Session A and use the prompt

This skill assumes project context is already present from the fork. It does NOT scan or embed project context — the forked session already has it.

## Workflow

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
- [ ] 10. Save artifacts
- [ ] 11. Present handoff instructions
```

### Step 1: Capture Rough Idea

Ask user for their feature idea. Accept any format.

Since project context is already loaded, acknowledge what you know:
- "I can see this is a {framework} project with {structure}. You want to add {feature}. Let me ask some questions to flesh this out."

Save raw input to `architect/transcript.md`:
```markdown
# Forging Prompts Transcript
## Project: {project name from context}
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

Because project context is loaded, adapt questions:
- Skip questions you can already answer from context (but confirm your assumptions)
- Ask deeper, more targeted questions informed by the codebase
- Example: Instead of "What tech stack?" ask "Should this use the existing React component pattern in src/components, or does this feature need a different approach?"

Use the `AskUserQuestion` tool for structured questions (max 4 per call).

Append every Q&A pair to `architect/transcript.md` under `## Questionnaire`.

After each batch, update `architect/STATE.md`:
```markdown
# Forge State
## Current Stage: questionnaire
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

Focus research on:
- How others have implemented this feature with the same tech stack
- Official documentation for relevant libraries/frameworks already in use
- Known pitfalls specific to this combination of technologies

Save findings to `architect/transcript.md` under `## Prior-Art Research`.

### Step 5: Gap Analysis

Review Q&A answers, research findings (if available), AND existing project context. Identify:

1. **Missing information**: What about this feature hasn't been discussed?
2. **Contradictions**: Do answers conflict with existing project patterns?
3. **Integration concerns**: How does this feature interact with existing code?
4. **Unstated assumptions**: What is assumed but never confirmed?
5. **Missing success criteria**: How will we know this works?

Present gaps. Ask follow-up questions.

### Step 6: Draft Prompt v1

Synthesize into a structured prompt. The prompt must:

1. Clearly state the feature goal
2. Reference existing project patterns to follow (by file path)
3. Include all requirements and constraints from Q&A
4. Reference relevant prior art and best practices found (if research was done)
5. Specify success criteria and verification methods
6. NOT duplicate project context that the receiving session already has

The prompt should read like instructions to a developer who already knows the codebase.

Save to `architect/prompt.md`.

### Step 7: Self-Critique

Run Phase A (self-critique) from [challenge.md](../forging-shared/challenge.md).

Review prompt against challenge questions. Pay special attention to integration with existing code.

### Step 8: Sub-Agent Challenge Review [full only]

**Skip for quick path.**

Run Phase B (sub-agent review) from [challenge.md](../forging-shared/challenge.md).

Spawn sub-agent:
> "You are a critical reviewer. Read architect/prompt.md and architect/transcript.md. Find flaws, gaps, and ambiguities. Pay special attention to how this feature integrates with the existing codebase. Be adversarial."

Reconcile. Present issues. Fix confirmed ones.

### Step 9: Iterate

Present refined prompt. Ask for approval.

**Quick path**: One iteration max. Incorporate feedback and finalize.
**Full path**: Repeat Steps 6-8 as needed until user approves.

### Step 10: Save Artifacts

Save to project root `architect/` directory:

| File | Purpose | Reader |
|------|---------|--------|
| `transcript.md` | Full Q&A log, research, challenge results | Human |
| `STATE.md` | Current stage + key decisions summary | AI (resumption) |
| `prompt.md` | Perfected prompt (final version) | Human + AI |

**Update CLAUDE.md** (required): If `CLAUDE.md` exists, append or update the feature section. If it doesn't exist, create one with:

```markdown
# {Project Name}

{One-line description}

## Build Commands
{Build, test, and run commands}

## Conventions
{Key conventions from Q&A}

## Current Work
Feature: {feature name from this prompt}
Prompt: architect/prompt.md
```

For mid-project use, the CLAUDE.md likely already exists. Add the new feature's context without overwriting existing content.

### Step 11: Handoff Instructions

Present to user:
```
Your perfected prompt is saved at: architect/prompt.md

Next steps:
1. Switch back to your original terminal tab (Session A)
2. Use the prompt in one of these ways:
   a. Paste it directly: "Read architect/prompt.md and implement this"
   b. Enter plan mode first: Shift+Tab, then paste the prompt
   c. Just paste the prompt text directly
3. This forked session can be closed — all artifacts are on disk.
```

## Resumption

If `architect/STATE.md` exists when the skill is invoked, read it first. Ask:
- "I see you were at stage {X}. Resume from there, or start over?"

## Example

**Input** (in forked session with markdown editor context):
```
User: "I want to add theme support"
```

**Skill output** (after full pipeline):
```
architect/prompt.md — Perfected prompt referencing existing component
patterns, CSS conventions, and build pipeline. Ready to paste into
the original session.
```

For a detailed walkthrough, see [examples.md](examples.md).

## Self-Evolution

Update this skill when:
1. **On correction**: User identifies a gap in questioning → update questionnaire.md in forging-shared/
2. **On new pattern**: Discover effective challenge technique → update challenge.md in forging-shared/
3. **On research failure**: Source quality filter misses bad data → tighten research.md in forging-shared/
4. **On workflow friction**: User finds the fork workflow clunky → streamline

**Applied Learnings:**
- v1.3.0: CLAUDE.md as required artifact (create or update). Git/docs questions in Category 4.
- v1.2.0: Adaptive questionnaire (1-3 always, 4-12 assessed). Quick forge path. Unified reference files in forging-shared/.
- v1.1.0: Added plan mode guard. Improved session resumption guidance.
- v1.0.0: Initial version

Current version: 1.3.0. See [CHANGELOG.md](CHANGELOG.md) for history.
