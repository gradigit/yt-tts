# Exhaustive Questionnaire

## Contents
- [Adaptive Protocol](#adaptive-protocol)
- [Quick Forge Override](#quick-forge-override)
- [Category 1: Core Vision](#category-1-core-vision)
- [Category 2: Requirements & Constraints](#category-2-requirements--constraints)
- [Category 3: Prior Art & Context](#category-3-prior-art--context)
- [Category 4: Architecture & Structure](#category-4-architecture--structure)
- [Category 5: Edge Cases & Error Handling](#category-5-edge-cases--error-handling)
- [Category 6: Scale & Performance](#category-6-scale--performance)
- [Category 7: Security & Privacy](#category-7-security--privacy)
- [Category 8: Integration & Dependencies](#category-8-integration--dependencies)
- [Category 9: Testing & Verification](#category-9-testing--verification)
- [Category 10: Deployment & Operations](#category-10-deployment--operations)
- [Category 11: Trade-offs & Priorities](#category-11-trade-offs--priorities)
- [Category 12: Scope & Boundaries](#category-12-scope--boundaries)
- [Adaptive Note](#adaptive-note)
- [After Questionnaire](#after-questionnaire)

Question categories for prompt and plan perfection. Follow the Adaptive Protocol below to determine which categories to ask. Categories 1-3 are always asked. Categories 4-12 are assessed for relevance.

Use `AskUserQuestion` tool for structured questions (max 4 per call). For open-ended questions, ask in text. Append all Q&A to `architect/transcript.md`.

> **Forked session context**: When running in a forked session with project context already loaded, adapt questions: skip questions you can answer from context (but confirm assumptions), and ask deeper questions informed by the codebase.

## Adaptive Protocol

Categories 1-3 (Core Vision, Requirements & Constraints, Prior Art & Context) are **always asked** — these are universally relevant regardless of project type or feature scope.

After completing categories 1-3:

1. **Assess relevance**: Based on the answers so far, evaluate which of categories 4-12 are relevant to this specific feature or project.

2. **Present recommendation**: Show the user a table:

   | Category | Recommendation | Reason |
   |----------|---------------|--------|
   | 4. Architecture & Structure | Ask | {reason} |
   | 5. Edge Cases & Error Handling | Ask | {reason} |
   | 6. Scale & Performance | Skip | {reason} |
   | ... | ... | ... |

3. **User confirms**: The user can accept the recommendation, add categories back, or remove additional ones.

4. **For selected categories**: Ask the FULL question set. Do not abbreviate.

5. **For skipped categories**: Record in transcript:
   ```
   ## Category N: {Name}
   Skipped — {reason from recommendation table}
   ```

All 12 categories remain in this file as the complete question bank. The adaptive protocol selects which to use, not which exist.

## Quick Forge Override

If depth is set to **Quick**, ask categories 1-3 only. Skip the adaptive assessment entirely. Record in transcript:
```
Categories 4-12: Skipped — Quick forge path
```
Proceed directly to gap analysis after categories 1-3.

## Category 1: Core Vision

1. What exactly is this? Describe it in one sentence.
2. What problem does it solve? Who has this problem?
3. Who is the primary audience/user? Secondary?
4. What does success look like? How will you measure it?
5. What's the single most important thing this must do well?

## Category 2: Requirements & Constraints

1. What must it do? (functional requirements — be specific)
2. What must it NOT do? (explicit exclusions)
3. What are hard constraints? (budget, technology, compatibility, platform)
4. What are soft constraints? (preferences, nice-to-haves)
5. Are there regulatory, legal, or compliance requirements?
6. What existing systems/conventions must it integrate with or follow?

## Category 3: Prior Art & Context

1. Does anything like this already exist? (competitor, internal tool, open source)
2. If yes: why not use it? What's missing or wrong with it?
3. What prior attempts have been made? What failed and why?
4. Are there reference implementations or inspirations?
5. What documentation, specs, or resources already exist for this?

## Category 4: Architecture & Structure

1. What's the high-level structure? (components, layers, modules)
2. What technologies, tools, or frameworks are required or preferred?
3. What are the key interfaces between components?
4. What data flows through the system? In what format?
5. Are there architectural patterns that must be followed? (MVC, event-driven, etc.)
6. What are the critical paths? Where does failure have the highest impact?
7. Should the project use version control from the start? (git init, .gitignore — if yes, what should be ignored?)
8. Should the project include initial documentation? (README, architecture docs, etc.)

## Category 5: Edge Cases & Error Handling

1. What happens when input is invalid or unexpected?
2. What are the boundary conditions? (empty input, max size, concurrent access)
3. What failure modes exist? How should each be handled?
4. What happens during partial failure? (network drops mid-operation, etc.)
5. Are there race conditions or timing-sensitive operations?
6. What error messages should users see? What should be logged?

## Category 6: Scale & Performance

1. What's the expected volume? (users, requests, data size)
2. What are the performance requirements? (latency, throughput)
3. Does it need to scale? How? (horizontally, vertically, not at all)
4. Are there resource constraints? (memory, CPU, storage, API rate limits)
5. What's the growth projection? (10x? 100x? Stable?)

## Category 7: Security & Privacy

1. What needs to be protected? (data, access, operations)
2. Who should have access? At what levels?
3. Are there authentication/authorization requirements?
4. Is sensitive data involved? (PII, credentials, financial data)
5. Are there data retention or deletion requirements?
6. What's the threat model? (who might attack this, and how?)

## Category 8: Integration & Dependencies

1. What external services, APIs, or systems does this interact with?
2. What are the input sources? Output destinations?
3. Are there third-party dependencies? What are their reliability guarantees?
4. What happens if a dependency is unavailable?
5. Are there versioning or backwards-compatibility requirements?

## Category 9: Testing & Verification

1. How will you verify this works correctly?
2. What are the key test scenarios? (happy path, error path, edge cases)
3. Are there existing test frameworks or conventions to follow?
4. What does "done" look like? What are the acceptance criteria?
5. Who reviews/approves the output? What's the review process?

## Category 10: Deployment & Operations

1. How will this be delivered? (deployed, installed, distributed)
2. What environments exist? (dev, staging, production)
3. How is configuration managed?
4. How is monitoring/observability handled?
5. What's the rollback strategy if something goes wrong?

## Category 11: Trade-offs & Priorities

1. Rank these by priority: speed, quality, simplicity, flexibility, cost
2. What are you willing to sacrifice? What's non-negotiable?
3. Is this a prototype/MVP or production-grade?
4. Optimize for: time to ship, long-term maintainability, or both?
5. What's the acceptable quality bar? (good enough vs. polished)

## Category 12: Scope & Boundaries

1. What's explicitly in scope for this iteration?
2. What's explicitly out of scope? (important to prevent scope creep)
3. What might change later? What should be designed for extensibility?
4. Are there related efforts happening in parallel?
5. What decisions have already been made that cannot be changed?

## Adaptive Note

Categories 4-10 use software-oriented language but apply to all project types. Adapt the questions:

| Software Term | Non-Software Equivalent |
|---------------|------------------------|
| Architecture | Structure / Organization / Outline |
| Edge Cases | Exceptions / Corner Cases / Unusual Scenarios |
| Scale | Volume / Audience Size / Distribution |
| Security | Confidentiality / Access Control / Sensitivity |
| Integration | Coordination / Dependencies / Related Work |
| Testing | Verification / Review / Quality Checks |
| Deployment | Delivery / Distribution / Publication |

If a selected category is clearly irrelevant to the project type (e.g., "Deployment" for a writing project), still ask ONE question from that category to confirm it's irrelevant, then note it as "N/A — confirmed irrelevant" in the transcript.

## After Questionnaire

Once all selected categories are complete:
1. Present a summary of all key decisions to the user
2. Ask: "Is this summary accurate? Anything to add or correct?"
3. Proceed to Prior-Art Research (Step 4)
