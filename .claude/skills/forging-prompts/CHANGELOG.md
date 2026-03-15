# Changelog

## v1.3.0 (2026-02-01)

### Added
- CLAUDE.md as required artifact in Step 10 — create if missing, update if exists
- Git and documentation questions added to Category 4 (Architecture & Structure) in questionnaire

### Changed
- Step 10 now creates/updates CLAUDE.md with project context for the executing agent

### Design Decisions
- CLAUDE.md is required because the skill runs inside Claude Code and produces output for Claude Code
- For mid-project use, CLAUDE.md likely already exists — skill appends feature context rather than overwriting

## v1.2.0 (2026-02-01)

### Added
- Quick forge path: depth selection (quick/full) at start of workflow
- Adaptive questionnaire: categories 1-3 always asked, 4-12 assessed for relevance
- Quick forge example in examples.md

### Changed
- Reference files (questionnaire.md, challenge.md, research.md) unified in ~/.claude/skills/forging-shared/ to prevent drift
- Questionnaire changed from mandatory-all to adaptive protocol
- STATE.md template updated with depth and categories asked/skipped tracking
- Self-Evolution section now directs to forging-shared/ for reference file updates

### Removed
- "Ask ALL categories. Do not skip." directive — replaced by adaptive protocol
- Local copies of questionnaire.md, challenge.md, research.md (now shared)

## v1.1.0 (2026-02-01)

### Added
- Plan mode guard: detects when user is in plan mode and advises using forging-plans or exiting plan mode first

### Fixed
- Resumption example: replaced `claude --resume` with guidance to use the interactive session picker and select the forked session specifically

## v1.0.0 (2026-02-01)

### Added
- Initial release
- Mid-project prompt perfection via forked sessions
- Exhaustive 12-category questionnaire
- Two-phase challenge protocol (self-critique + sub-agent)
- Mandatory prior-art research with quality filtering
- State-based resumption via STATE.md
- Full transcript logging for human reference
- Research quality standards (accept/caution/reject criteria)

### Design Decisions
- Separate skill from forging-plans for clean separation of concerns
- Designed for `claude --continue --fork-session` workflow
- Own copies of reference files (questionnaire, challenge, research) for full modularity
- Same exhaustive Q&A depth as forging-plans
- No project context scanning needed (forked session already has context)
- No plan mode integration (prompt goes back to original session)
