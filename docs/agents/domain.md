# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- `GLOSSARY.md` at the repository root
- `docs/adr/`: ADRs relevant to the area being changed

If these files do not exist, proceed silently. The `/domain-modeling` skill creates them lazily when terminology or decisions are resolved.

## File structure

This is a single-context repository:

/
├── GLOSSARY.md
├── docs/adr/
└── src/

## Use the glossary's vocabulary

When naming a domain concept in an issue, proposal, hypothesis or test, use the term defined in `GLOSSARY.md`. Avoid synonyms that the glossary explicitly rejects.

If a required concept is missing, reconsider whether the language belongs to the project or record the gap for `/domain-modeling`.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly instead of silently overriding the decision.
