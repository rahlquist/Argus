# Collectors

Prose `extract:` instructions ("first release tag_name", "web search: 'amdxdna
Krackan kernel'") ask the model to interpret data on every tick. That makes the
anti-fabrication rule depend on model discipline, and it makes the spec
untestable.

A collector replaces the prose with a named, testable function:

```yaml
metrics:
  - name: lemonade_version
    unit: version
    collector: 'github.release_tag(repo="lemonade-sdk/lemonade")'
```

The agent runs the collector and reads a value. It no longer extracts.

## Usage

```bash
# from a tracker spec (needs PyYAML on the running interpreter)
python3 scripts/argus_collect.py --from-tracker trackers/amd-npu-krackan.yaml \
  --out state/amd-npu-krackan.current.json

# without PyYAML: pass the metrics block as JSON
python3 scripts/argus_collect.py --spec - --slug amd-npu-krackan \
  --out state/amd-npu-krackan.current.json < metrics.json
```

Output drops straight into the file `eval_signal.py` already consumes:

```json
{
  "slug": "amd-npu-krackan",
  "collected_at": "2026-10-17T13:00:00Z",
  "last_run": "2026-10-17",
  "metrics": {
    "lemonade_version": {
      "value": "v11.8.1", "unit": "version",
      "url": "https://api.github.com/repos/lemonade-sdk/lemonade/releases?per_page=1",
      "collector": "github.release_tag", "deterministic": true, "error": null
    }
  }
}
```

Exit code is `1` when any metric errored, `0` otherwise — usable as a gate.

## Built-in collectors

| Collector | Args | Returns |
|---|---|---|
| `github.release_tag` | `repo` | latest release tag name |
| `github.latest_commit_date` | `repo` | `YYYY-MM-DD` of the newest commit |
| `github.issue_state` | `repo`, `number` | `open` / `closed` |
| `http.json_path` | `url`, `json_path` | dotted path into a JSON response |
| `http.regex` | `url`, `pattern`, `group` | regex capture (default group 1) |
| `file.json_path` | `path`, `json_path` | dotted path into a local JSON file |
| `file.json_set` | `path`, `json_path`, `key` | sorted unique values (set-diff metrics) |
| `file.count_glob` | `path`, `pattern` | match count |
| `llm_extract` | `prompt` | **escape hatch** — see below |

Dotted paths index lists with numeric segments: `"0.tag_name"`.

GitHub collectors send `Authorization: Bearer $GITHUB_TOKEN` (or `$GH_TOKEN`)
when either is set in the environment.

## The escape hatch

Some sources no collector can read — a prose changelog, a rendered page, a
kernel mailing-list thread. `llm_extract` is the explicit, auditable exception:

```yaml
  - name: kernel_note
    unit: status
    collector: 'llm_extract(prompt="one-line amdxdna kernel status")'
```

Its value must be supplied by the agent:

```bash
python3 scripts/argus_collect.py --spec - --set kernel_note="amdxdna in mainline; VOE wheel missing"
```

Unsupplied, it returns an error rather than a guess. Supplied, the metric is
still marked `"deterministic": false` so the briefing can distinguish measured
values from interpreted ones.

**Rule:** if a metric can be read deterministically, it must not use
`llm_extract`.

## Failure semantics

A collector failure produces:

```json
{"value": "<error>", "error": "HTTPError: 403 Forbidden", "deterministic": true}
```

A failed fetch is structurally an error. It is never a silently reused previous
value, and it is never a fabricated one — matching the anti-fabrication rule in
`references/diff-metrics.md`.

## Migration from `extract:`

`extract:` still works; collectors are additive. Migrate a tracker when its
metric is mechanically readable:

| Old `extract:` | New `collector:` |
|---|---|
| `first release tag_name` | `github.release_tag(repo="owner/repo")` |
| `.[0].commit.author.date (YYYY-MM-DD)` | `github.latest_commit_date(repo="owner/repo")` |
| `open\|closed` | `github.issue_state(repo="owner/repo", number=341)` |
| `len(github_repos)` | `file.json_path(path="/scan.json", json_path="github_repos")` |
| `sorted set of github_repos[].name` | `file.json_set(path="/scan.json", json_path="github_repos", key="name")` |
| `web search: 'amdxdna Krackan kernel'` | `llm_extract(prompt="...")` — last resort |

## Tests

`scripts/argus_collect.py --self-test` and `tests/skills/test_argus_collect.py`
exercise the collectors with injected fixtures — no network, no disk.
