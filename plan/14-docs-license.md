# Task 14 — Project documentation & license

## Objective
Provide the user-facing and legal documents the project ships with.

## What must be done
- Add an MIT license (the project is freshly written and not bound by the reference's GPL-3.0).
- Write a README covering: what the plugin does, the requirement to paste a `jstsToken` cookie
  (where to get it, that it lasts ~3 weeks, and what happens when it expires), the optional
  User-Agent, configuration options, install instructions, and a note on responsible use / rate
  limiting given Babelio's text-and-data-mining reservation.
- Add a changelog to track released versions.

## Acceptance criteria
- An MIT `LICENSE` file is present.
- The README accurately explains setup, the cookie requirement, and responsible-use guidance.
- A changelog exists and is referenced by the release workflow.

## Dependencies
- Task 01 (repo exists). Content should be kept in sync as later tasks land.

## Out of scope
- Release automation (Task 13).

## References
- Specification §Decisions (MIT license), §Other notes (TDM reservation / responsible use).
