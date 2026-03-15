# Examples

## Contents
- [Full Forge Example: Adding Theme Support](#full-forge-example-adding-theme-support)
- [Quick Forge Example: Adding a Delete Button](#quick-forge-example-adding-a-delete-button)
- [Resumption Example](#resumption-example)

## Full Forge Example: Adding Theme Support

### Setup
User is working on a markdown editor (Session A). They want to add theme support.

```bash
# In a new terminal tab:
claude --continue --fork-session
# Forked session now has all project context from Session A
```

### Skill Activation
```
User: /forging-prompts I want to add theme support
```

Skill detects project context (React, TypeScript, CSS modules, existing component patterns).

### Depth Selection
```
Skill: "How deep should we go? Quick or Full?"
User: "Full — this touches a lot of the codebase"
```

### Questionnaire (abbreviated — adaptive protocol)
```
--- Categories 1-3 (always asked) ---

Skill: "I can see this is a React/TypeScript markdown editor using CSS modules.
You want to add theme support. Let me ask some questions."

Q: What does theme support mean specifically? (color scheme, font, layout, all?)
A: Color scheme only — light and dark mode, plus custom user themes.

Q: I see you're using CSS modules in src/components/. Should themes work
   through CSS custom properties, a theme provider context, or CSS modules?
A: CSS custom properties with a React context for switching.

Q: Should theme preference persist across sessions?
A: Yes, localStorage.

--- Adaptive assessment for categories 4-12 ---

Skill: "Based on your answers and the codebase, here's my recommendation:"

| Category | Recommendation | Reason |
|----------|---------------|--------|
| 4. Architecture & Structure | Ask | Theme provider + CSS refactor is architectural |
| 5. Edge Cases & Error Handling | Ask | Custom themes can break layout |
| 6. Scale & Performance | Skip | Client-side only, no scale concerns |
| 7. Security & Privacy | Skip | No sensitive data in themes |
| 8. Integration & Dependencies | Ask | highlight.js theming integration |
| 9. Testing & Verification | Ask | Need visual verification strategy |
| 10. Deployment & Operations | Skip | No deployment changes needed |
| 11. Trade-offs & Priorities | Ask | MVP scope of theme support |
| 12. Scope & Boundaries | Ask | What's v1 vs future theme features |

User: "Agreed"

[Skill asks full question sets for selected categories]
```

### Prior-Art Research
```
Searched: "React CSS custom properties theming best practices 2026"
Found: Official React docs recommend CSS custom properties for theming.
Found: prefers-color-scheme media query for system theme detection.
Found: Common pitfall — flash of unstyled content on SSR with themes.
Note: This project is client-only, so SSR flash is not relevant.
```

### Gap Analysis
```
- Missing: What about syntax highlighting themes? The editor uses highlight.js.
- Missing: Should there be a theme preview in settings?
- Assumption: Only light/dark + custom — confirmed no "sepia" or other presets.
- Integration concern: Existing CSS modules may need refactoring to use custom properties.
```

### Challenge Phase
```
Self-critique found:
- Prompt doesn't mention how custom themes are defined (JSON? CSS file? UI builder?)
- No mention of accessibility contrast requirements for themes
- "localStorage" doesn't handle the case where user is logged in across devices

Sub-agent found:
- The prompt references "existing component patterns" but doesn't specify which files
- No fallback strategy if a custom theme has missing properties
- Edge case: what if a custom theme makes text unreadable? (contrast check)
```

### Final Prompt (architect/prompt.md)
```markdown
Add theme support (color scheme) to the markdown editor.

## Requirements
- Two built-in themes: light and dark
- Custom user themes via JSON configuration
- Theme switching via React context provider
- CSS custom properties for all color values
- System theme detection via prefers-color-scheme
- Persistence via localStorage
- Fallback to light theme for missing custom properties
- Minimum 4.5:1 contrast ratio validation for custom themes

## Implementation Notes
- Follow existing component pattern in src/components/Editor/
- Refactor hardcoded colors in *.module.css to custom properties
- highlight.js themes need to switch alongside editor themes
- No server-side rendering concerns (client-only app)

## Verification
- Toggle between light/dark — all UI elements update
- Create a custom theme JSON — loads and applies correctly
- Delete localStorage — falls back to system preference
- Custom theme with low contrast — shows warning
```

### Handoff
```
User switches back to Session A (original tab).
Pastes: "Read architect/prompt.md and implement this"
Session A has full project context + the perfected prompt.
```

## Quick Forge Example: Adding a Delete Button

### Setup
Same forked session workflow. User wants a small, well-understood feature.

```
User: /forging-prompts Add a delete button to the document list
```

### Depth Selection
```
Skill: "I can see this is a React/TypeScript app with a DocumentList
component in src/components/DocumentList/. How deep should we go?"
User: "Quick"
```

### Questionnaire (categories 1-3 only)
```
Q: What exactly should the delete button do?
A: Remove the document from the list and delete it from localStorage.

Q: Should there be a confirmation dialog?
A: Yes, a simple "Are you sure?" dialog.

Q: Any constraints? What must it NOT do?
A: Must not delete without confirmation. No bulk delete — single document only.

Q: Does anything like this already exist?
A: No, documents can only be created right now.

Categories 4-12: Skipped — Quick forge path
```

### Gap Analysis + Self-Critique
```
Gap: What happens to the active document if it's deleted?
User: Navigate to the next document, or show empty state if none left.

Self-critique:
- Missing: Should the button be visible always or on hover?
- Missing: Keyboard shortcut for delete?
Resolution: Visible always (icon button). No keyboard shortcut for v1.
```

### Final Prompt
```markdown
Add a delete button to the document list component.

## Requirements
- Delete icon button on each document row in DocumentList
- Confirmation dialog: "Delete {name}? This cannot be undone."
- On confirm: remove from localStorage, update document list state
- If active document deleted: navigate to next document or show empty state
- Single document only — no bulk delete

## Implementation Notes
- Add to existing DocumentList component in src/components/DocumentList/
- Use existing Button component pattern from src/components/Button/
- Follow existing state management pattern (useState + localStorage sync)

## Verification
- Click delete → confirmation appears
- Cancel → nothing happens
- Confirm → document removed, list updates
- Delete active document → navigates to next
- Delete last document → empty state shown
```

## Resumption Example

### Scenario
User forked session, started the skill, completed questionnaire, then closed terminal.

### On Re-invocation
```
# Run claude --resume (with no ID) to open the interactive session picker.
# Browse the list and select the FORKED session — not your original working session.
# The forked session is the one where you ran /forging-prompts.
#
# Important: "claude --resume" without an ID does NOT auto-resume the last session.
# It shows a picker so you can choose the right one.
claude --resume
```

```
Skill reads architect/STATE.md:
  Current Stage: prior-art-research
  Depth: full
  Categories Asked: [1, 2, 3, 4, 5, 8, 9, 11, 12]
  Categories Skipped: [6 — no scale, 7 — no security, 10 — no deploy changes]
  Key Decisions: [list]

Skill: "I see you completed the questionnaire and were about to start
prior-art research. Resume from there, or start over?"

User: "Resume"

Skill continues from Step 4.
```
