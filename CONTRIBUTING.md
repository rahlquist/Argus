# Contributing — adding a skill

This repo is structured so adding another skill is a copy-paste, not a redesign.

## Steps

1. **Scaffold from the template**
   ```bash
   cp -r skills/_template skills/<your-skill-name>
   ```
   Use a lowercase-hyphen name (e.g. `pdf-wrangler`).

2. **Fill `SKILL.md` frontmatter**
   ```yaml
   ---
   name: your-skill-name
   description: "One sentence, <= 60 chars, ends with a period."
   version: 0.1.0
   author: Your Name (your-github-handle), Hermes Agent
   license: MIT
   platforms: [linux, macos, windows]
   metadata:
     hermes:
       tags: [short, descriptive, tags]
       related_skills: []
   ---
   ```
   Rules:
   - `description` ≤ 60 chars, one sentence, ends with `.`, no marketing words.
   - Credit the human first, then "Hermes Agent".
   - `platforms` from what the skill actually invokes (not guessed).

3. **Write the body** using the standard section order:
   `## When to Use` · `## Prerequisites` · `## Model/How it works` ·
   `## Procedure` (numbered steps, each with a checkable completion criterion) ·
   `## Pitfalls` · `## Verification`.
   Reference Hermes tools by name (`web_search`, `terminal`, `write_file`, `cronjob`, …), not raw shell.

4. **Add supporting files** under `references/` and `scripts/` as needed.
   Keep bulky logic in `scripts/` and point to it from `SKILL.md`.

5. **Register in the catalog** — add a row to [`skills/README.md`](../skills/README.md).

6. **Install & smoke-test**
   ```bash
   ./scripts/install-skill.sh <your-skill-name>
   ```
   Then exercise it in a Hermes session. For skills with a self-test
   (like `personal-intel-agent`'s `scripts/fold.py --self-test`), run it.

7. **Commit**
   ```bash
   git add skills/<your-skill-name> skills/README.md
   git commit -m "feat: add <your-skill-name> skill"
   ```

## Don'ts
- Don't nest skills under category folders — keep `skills/<name>` flat.
- Don't commit runtime state or secrets (`.intel/`, `.env`, `__pycache__/` are gitignored).
- Don't write machine-local absolute paths into `SKILL.md`; use repo-relative paths.
- Don't train a black box: if the skill keeps memory, make it visible/editable like `personal-intel-agent` does with `memory.md`.
