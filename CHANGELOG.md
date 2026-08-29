# Changelog

## 0.2.0
- **Fix: `eval.items:` metric gate was dead code.** The gate now restricts
  firing to only the metrics listed in `eval.items:` (or all metrics when
  omitted). Previously every metric gated regardless, defeating the documented
  contract and the "list only price metrics" guidance. (eval_signal.py)
- **Fix: `fold.py` source_count now counts distinct sources**, not raw cluster
  length (duplicate sources no longer inflate "folded from N sources").
- **Fix: `fold.py` no longer raises BrokenPipeError** when stdout is closed
  early (e.g. piped into `head`).
- **Docs:** corrected `fold.py` description from "char-trigram" to "word-level
  TF-IDF"; fixed the `--noise` usage example (repeated `--noise a --noise b`,
  not the literal `gossip|clickbait`); clarified first-run baseline differs by
  mode (diff fires once, threshold is silent).
- **Schema:** added `on_signal:` to `tracker-schema.md` (git_commit_push
  shape) so the field is discoverable; it was referenced but undocumented.
- **Safety:** `.gitignore` now covers all INTEL_DIR shapes and state-file
  globs, preventing accidental commits of runtime state via `on_signal:`
  git pushes. `loop-prompt.md` resolves state dir from `INTEL_DIR` (single
  source of truth) instead of a hardcoded `./.intel`.
- **Platforms:** gated `platforms` to `[linux, macos]` — `notify_bot.sh` and
  cron wiring are POSIX/bash and untested on Windows.
- **Testing:** added `tests/skills/test_personal_intel_agent_skill.py`
  (behavior contracts, stdlib+pytest, no network), `scripts/run_tests.sh`, and
  `.github/workflows/ci.yaml` (frontmatter lint + self-tests + pytest).

## 0.1.0
- Initial release: news watch (READ→FOLD→SIGNAL→DISCOVER) + metric/price
  monitor (diff/threshold `eval:` gate), open `memory.md` user model, and
  multi-channel delivery (feed/file/rss/audio/bot).
