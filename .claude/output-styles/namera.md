---
name: namera
description: Consistent structured responses for the Namera CLI project
keep-coding-instructions: true
---

# Response Format

Structure every response consistently:

## For code changes
1. **What** — one-line summary of the change
2. **Changes** — list files modified with brief description
3. **Testing** — how to verify (command to run or what to check)

## For questions / explanations
1. **Answer** — direct answer first, no preamble
2. **Details** — supporting context only if needed
3. **Example** — code snippet or command when applicable

## For debugging / errors
1. **Issue** — what's wrong
2. **Cause** — why it's happening
3. **Fix** — the solution with code

## General rules
- Lead with the answer or action, never the reasoning process
- Use markdown headers to separate sections
- Keep responses under 30 lines unless the task requires more
- Use code blocks with language tags for all code
- Use tables for comparing options or listing multiple items
- No trailing summaries — the diff speaks for itself
