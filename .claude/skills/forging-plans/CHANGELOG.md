# Changelog

## v1.3.0 (2026-02-01)

### Added
- CLAUDE.md as required artifact in Step 10 — persistent project context that survives context clears (build commands, conventions, architect/ directory guide)
- TODO.md as required artifact in Step 10 — persistent task tracker replacing session-scoped TaskCreate/TaskUpdate. Executing agent must update after every significant step
- `architect/ Directory` section in CLAUDE.md template — explicitly directs executing agent to plan.md and labels other files as reference-only
- Plan copy saved to `architect/plan.md` during Mode 2 finalize — plan lives in-project, not just `~/.claude/plans/`
- Git and documentation questions added to Category 4 (Architecture & Structure) in questionnaire
- Mode 2 finalize updates CLAUDE.md with phase progress from the plan

### Changed
- Handoff instructions (Step 11) now reference CLAUDE.md and TODO.md as saved artifacts
- Example output updated to include CLAUDE.md, TODO.md, and architect/plan.md with role annotations

### Design Decisions
- CLAUDE.md is required (not a question) because the skill runs inside Claude Code and produces output for Claude Code — it's execution infrastructure
- TODO.md is required because Claude Code's TaskCreate/TaskUpdate are session-scoped and don't survive context clears — persistent task tracking must be on disk
- Git init is a questionnaire question (not required) because version control preferences vary
- architect/ directory guide prevents executing agent from confusing prompt.md (spec) with plan.md (instructions)

## v1.2.0 (2026-02-01)

### Added
- Quick forge path: depth selection (quick/full) at start of workflow
- Adaptive questionnaire: categories 1-3 always asked, 4-12 assessed for relevance
- Quick forge example in examples.md

### Changed
- Removed self-encoded Mode 2 instructions from Mode 1 workflow
  - Perfected prompts are now clean specifications without embedded workflow meta-instructions
  - Mode 2 handles plan iteration independently
- Reference files (questionnaire.md, challenge.md, research.md) unified in ~/.claude/skills/forging-shared/ to prevent drift
- Questionnaire changed from mandatory-all to adaptive protocol
- STATE.md template updated with depth and categories asked/skipped tracking
- Self-Evolution section now directs to forging-shared/ for reference file updates

### Removed
- Step 9 (Self-Encode Mode 2 Techniques) — prompt output is now a clean spec
- "Ask ALL categories. Do not skip." directive — replaced by adaptive protocol
- `research/sources.md` from artifacts table — research is in transcript.md
- Local copies of questionnaire.md, challenge.md, research.md (now shared)

## v1.1.0 (2026-02-01)

### Added
- Mode 2 guard: detects when user is in plan mode without Mode 1 artifacts and advises running Mode 1 first
- Expanded Mode 1 handoff instructions guiding user through the full Mode 1 → Mode 2 transition

### Changed
- Mode 2 now writes only to plan.md (plan mode's sole writable file) instead of architect/ files
- Mode 2 reads architect/ files from Mode 1 as read-only reference
- Iteration findings stored as temporary `## [Iteration]` sections in plan.md, stripped during finalize
- Added finalize step (Step 6) to Mode 2 workflow
- Resumption in Mode 2 detects `[Iteration]` sections in plan.md instead of reading STATE.md
- Mode Detection section now validates readiness before entering Mode 2

### Fixed
- challenge.md: Inconsistent "plan" terminology in body replaced with neutral "artifact"

### Research
- Plan mode Write/Edit restrictions are prompt-level, not tool-level (system prompt injection)
- Plan file written via Edit tool, stored in `~/.claude/plans/`
- "Clear context and proceed" wipes conversation, retains plan.md + CLAUDE.md only

## v1.0.0 (2026-02-01)

### Added
- Initial release
- Mode 1: Prompt Perfection (normal mode)
- Mode 2: Plan Iteration (plan mode)
- Exhaustive 12-category questionnaire
- Two-phase challenge protocol (self-critique + sub-agent)
- Mandatory prior-art research with quality filtering
- State-based resumption via STATE.md
- Self-encoding of Mode 2 techniques into perfected prompts
- Full transcript logging for human reference
- Research quality standards (accept/caution/reject criteria)

### Design Decisions
- Single skill with two modes (not two separate skills) for shared techniques
- Exhaustive-always Q&A depth (may evolve to adaptive in future versions)
- Both-sequentially challenge approach for maximum thoroughness
- Output files in project-local `architect/` directory
- Execution prompt embedded in plan.md (not separate file) to avoid duplication
- architect/ directory excluded from execution context via embedded directive
