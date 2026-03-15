# Challenge Protocol

## Contents
- [Quick Forge Override](#quick-forge-override)
- [Phase A: Self-Critique](#phase-a-self-critique)
- [Phase B: Sub-Agent Challenge Review](#phase-b-sub-agent-challenge-review)
- [Reconciliation](#reconciliation)
- [When to Re-run](#when-to-re-run)

Two-phase adversarial review. Run BOTH phases sequentially. This is mandatory for the **full** forge path.

## Quick Forge Override

If depth is set to **Quick**, run Phase A (self-critique) only. Skip Phase B (sub-agent review) and the Reconciliation step. Present self-critique results directly to user.

## Phase A: Self-Critique

Review the artifact (prompt or plan) against each question below. Document all issues found.

### Completeness

1. Is every requirement from the questionnaire addressed?
2. Are there requirements that were implied but never stated?
3. Are success criteria specific and measurable?
4. Is the scope clearly bounded?
5. Are all dependencies and integrations accounted for?

### Clarity

1. Could any instruction be misinterpreted? How?
2. Are there ambiguous terms that need definition?
3. Is the ordering of steps logical and unambiguous?
4. Would a fresh Claude with no prior context understand this perfectly?
5. Are there implicit assumptions that should be made explicit?

### Feasibility

1. Is every requirement technically achievable?
2. Are there hidden complexities that the artifact underestimates?
3. Are resource estimates realistic?
4. Are there single points of failure?
5. Does the artifact handle the case where a step fails?

### Consistency

1. Do any requirements contradict each other?
2. Is the terminology consistent throughout?
3. Do the success criteria match the stated requirements?
4. Are trade-off decisions applied consistently?

### Research Alignment

1. Does the artifact align with best practices found during research?
2. Are there known pitfalls from prior art that aren't addressed?
3. Does it reinvent something that already exists?
4. Are the technology choices supported by the research findings?

### Adversarial Scenarios

1. What's the worst that could happen during execution?
2. How would a malicious or careless implementer break this?
3. What if the user's assumptions are wrong?
4. What happens 6 months from now when context is lost?
5. What would a skeptical senior engineer challenge about this artifact?

### Output

Document all issues found in this format:

```markdown
### Self-Critique Results

| # | Severity | Category | Issue | Suggested Fix |
|---|----------|----------|-------|---------------|
| 1 | High | Completeness | Missing error handling for X | Add error handling section |
| 2 | Medium | Clarity | "Process data" is ambiguous | Specify: parse JSON from API response |
```

Present to user. Ask which to fix.

## Phase B: Sub-Agent Challenge Review

After self-critique is resolved, spawn an independent sub-agent:

```
Use a sub-agent to perform an adversarial review.

Instructions for the sub-agent:
"You are a critical reviewer whose job is to find flaws. Read the following files:
- architect/prompt.md (or the current plan)
- architect/transcript.md

Your task:
1. List every gap, ambiguity, inconsistency, or weakness you find
2. Rate each issue: Critical / High / Medium / Low
3. For each issue, suggest a specific fix
4. Identify anything that was ASSUMED but never CONFIRMED
5. Identify anything that contradicts the research findings
6. Find at least 3 things to critique (even if the artifact seems solid)

Be thorough and adversarial. Don't be kind — be accurate."
```

### Reconciliation

After sub-agent returns:
1. Compare sub-agent findings with self-critique findings
2. Identify NEW issues the self-critique missed (these are the valuable ones)
3. Present all unique issues to user
4. Fix confirmed issues
5. Document what was fixed and what was intentionally kept:
   - **Normal mode**: Append to `architect/transcript.md`
   - **Plan mode** (Mode 2): Write to plan.md as a `## [Iteration] Challenge Results` section — plan mode restricts writing to plan.md only

## When to Re-run

Re-run the full challenge protocol after:
- Major changes to the artifact (not minor wording tweaks)
- New research findings that change assumptions
- User explicitly requests another review round
