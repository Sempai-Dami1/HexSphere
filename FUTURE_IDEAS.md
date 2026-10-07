# Future Ideas / Deferred Concepts

> STATUS: INFORMATIONAL ONLY — NOT ACTIVE DEVELOPMENT SCOPE

This document contains future ideas, observations, experiments,
and possible enhancements.

## Agent / Planner Rule

This file MUST NOT be treated as an implementation requirement.

When inspecting the repository for a phase, recovery review,
planning task, regression investigation, or implementation task:

- Do NOT convert ideas in this document into proposed scope.
- Do NOT create tasks from this document automatically.
- Do NOT modify code because an idea is documented here.
- Do NOT interpret an item as approved, prioritized, or scheduled.
- Do NOT reopen a frozen phase or contract because an idea appears here.

An item becomes active scope only when the user explicitly promotes
it into the current task or explicitly authorizes planning for it.

If an idea is relevant to a current task, mention it only as
deferred context unless the user explicitly activates it.

The authoritative source for current work remains:
- the current user request;
- the approved phase plan;
- the relevant phase checkpoint;
- DEVELOPMENT_BEST_PRACTICES.md;
- frozen contracts and tests.


# Future Ideas / Deferred Concepts

> STATUS: INFORMATIONAL ONLY — NOT ACTIVE DEVELOPMENT SCOPE

## Workbench — Part Selection / Inspection

### Observation

The 3D preview currently uses distinct colors for evaluated parts.
Hovering over a part displays its part ID/name.

This appears to provide an existing foundation for future part
selection and inspection.

### Possible Future Capability

Allow the user to:

1. Hover over a part to identify it.
2. Click a part to select it.
3. Display its recipe ID/type/transform/anchors.
4. Optionally enter an edit/inspection mode.
5. Reuse the existing guided controls to edit the selected part.
6. Re-evaluate the recipe and refresh the preview.

### Status

Deferred concept. Not approved for implementation.

---

## AI Object Recipe Generation

### Concept

Allow a user to describe an object in natural language and have an
AI provider generate an Object Recipe.

Example:

"Create a small wooden watchtower with four supports and a railing."

Possible pipeline:

User Prompt
    ↓
AI Provider
    ↓
Object Recipe JSON
    ↓
Recipe Validation
    ↓
Workbench Preview
    ↓
User Review
    ↓
Evaluation / Package 1.0
    ↓
Consumer such as Roblox Object Lab

### Architectural Principle

The AI should generate an Object Recipe rather than arbitrary
Python, Roblox Lua, or executable code.

The generated recipe must pass through the same validation and
evaluation pipeline as a human-authored recipe.

### Possible Future AI Provider UI

- Provider selection
- API key / credential configuration
- Model selection
- Prompt input
- Generate Recipe
- Validation result
- Preview before acceptance

### Security Considerations

API credentials must not be stored in recipe JSON or committed to
the repository.

### Status

Deferred concept. Not approved for implementation.

---

## Workbench → Roblox Object Lab

### Concept

Use the Object Recipe as the portable representation between the
Streamlit Workbench and Roblox Object Lab.

Target workflow:

Workbench
    ↓
Object Recipe JSON
    ↓
Roblox Object Lab
    ↓
Evaluate / Preview / Stage

### Status

Planned exploration / future integration work.
Not active until explicitly authorized.

---

## Raster-Only Objects

### Concept

Use the newly implemented Raster-Only Recipe mode to create objects
whose geometry is generated entirely from the raster representation.

Potential future test:

Raster Grid
    ↓
Object Recipe
    ↓
Package / Consumer
    ↓
Roblox Object Lab

### Status

Future integration experiment. Not current Workbench scope.