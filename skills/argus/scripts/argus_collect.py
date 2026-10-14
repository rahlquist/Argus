#!/usr/bin/env python3
"""argus_collect.py — deterministic metric collection for Argus trackers.

Replaces prose ``extract:`` instructions ("first release tag_name") with named,
testable collectors. The agent no longer interprets data; it runs a collector
and reads a value. A failed fetch becomes a structural error instead of a value
the model might invent.

Spec (JSON on stdin or via ``--spec FILE``)::

    {"slug": "demo",
     "metrics": [{"name": "lemonade_version", "unit": "version",
                  "collector": "github.release_tag", "args": {"repo": "lemonade-sdk/lemonade"}}]}

Inline call syntax is also accepted::

    {"name": "lemonade_version", "unit": "version",
     "collector": "github.release_tag(repo=\"lemonade-sdk/lemonade\")"}

Output drops straight into ``state/<slug>.current.json``::

    {"slug": ..., "collected_at": ..., "last_run": "YYYY-MM-DD",
     "metrics": {"<name>": {"value": ..., "unit": ..., "url": ...,
                            "collector": ..., "deterministic": true, "error": null}}}

Usage::

    argus_collect.py --spec spec.json [--set name=value]... [--out PATH]
    argus_collect.py --from-tracker trackers/x.yaml [--set name=value]... [--out PATH]
    argus_collect.py --self-test

``--from-tracker`` needs PyYAML; without it, pass the metrics block as JSON.
``llm_extract`` is the explicit escape hatch for sources no collector can read:
its value must be supplied with ``--set`` and it is always marked
``deterministic: false``.

Stdlib only (PyYAML is optional and only used by ``--from-tracker``).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_CALL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*(?:\((.*)\))?$", re.DOTALL)
DEFAULT_TIMEOUT = 30


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# spec parsing
# ---------------------------------------------------------------------------


def _split_args(text: str) -> list:
    parts, buf, quote = [], [], None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch == ",":
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if quote:
        raise ValueError("unterminated quoted value")
    tail = "".join(buf)
    if tail.strip():
        parts.append(tail)
    return [p.strip() for p in parts if p.strip()]


def _unquote(text: str):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        inner = text[1:-1]
        return inner.replace("\\\\", "\\").replace('\\"', '"').replace("\\'", "'")
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    return text


def parse_collector_spec(text: str) -> tuple:
    """Parse ``name`` or ``name(k=v, ...)`` into ``(name, kwargs)``."""
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("empty collector spec")
    match = _CALL_RE.match(raw)
    if not match:
        raise ValueError(f"malformed collector spec: {text!r}")
    name, inner = match.group(1), match.group(2)
    if inner is None:
        return name, {}
    if inner.strip() == "":
        return name, {}
    kwargs = {}
    for part in _split_args(inner):
        if "=" not in part:
            raise ValueError(f"collector argument needs name=value: {part!r}")
        key, value = part.split("=", 1)
        kwargs[key.strip()] = _unquote(value)
    return name, kwargs


def resolve_collector(metric: dict) -> tuple:
    name, kwargs = parse_collector_spec(metric.get("collector") or "")
    args = metric.get("args") or {}
    if not isinstance(args, dict):
        raise ValueError("metric 'args' must be a mapping")
    merged = dict(kwargs)
    merged.update(args)
    return name, merged


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _dig(obj, path):
    """Traverse a dotted path; numeric segments index lists."""
    if path in (None, "", "."):
        return obj
    cur = obj
    for seg in str(path).split("."):
        if isinstance(cur, (list, tuple)):
            cur = cur[int(seg)]
        elif isinstance(cur, dict):
            cur = cur[seg]
        else:
            raise KeyError(f"cannot descend into {type(cur).__name__} at {seg!r}")
    return cur


def _json_from_url(ctx, url):
    body = ctx.fetch(url)
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", errors="replace")
    return json.loads(body)


# ---------------------------------------------------------------------------
# collectors — each returns (value, source_url)
# ---------------------------------------------------------------------------


def c_file_json_path(ctx, path, json_path=None, **kw):
    doc = json.loads(ctx.read_file(path))
    return _dig(doc, json_path), path


def c_file_json_set(ctx, path, json_path=None, key=None, **kw):
    doc = json.loads(ctx.read_file(path))
    items = _dig(doc, json_path)
    values = [item.get(key) if isinstance(item, dict) else item for item in items]
    return sorted({str(v) for v in values if v is not None}), path


def c_file_count_glob(ctx, path, pattern="*", **kw):
    return int(ctx.count_glob(path, pattern)), path


def c_http_json_path(ctx, url, json_path=None, **kw):
    return _dig(_json_from_url(ctx, url), json_path), url


def c_http_regex(ctx, url, pattern, group=1, **kw):
    body = ctx.fetch(url)
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", errors="replace")
    match = re.search(pattern, body, re.MULTILINE)
    if not match:
        raise ValueError(f"pattern did not match: {pattern!r}")
    return match.group(int(group)), url


def c_github_release_tag(ctx, repo, prerelease=False, **kw):
    url = f"https://api.github.com/repos/{repo}/releases?per_page=1"
    data = _json_from_url(ctx, url)
    if not data:
        raise ValueError(f"no releases for {repo}")
    return data[0]["tag_name"], url


def c_github_latest_commit_date(ctx, repo, **kw):
    url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
    data = _json_from_url(ctx, url)
    if not data:
        raise ValueError(f"no commits for {repo}")
    return str(data[0]["commit"]["author"]["date"])[:10], url


def c_github_issue_state(ctx, repo, number, **kw):
    url = f"https://api.github.com/repos/{repo}/issues/{number}"
    data = _json_from_url(ctx, url)
    return data.get("state"), url


COLLECTORS = {
    "file.json_path": c_file_json_path,
    "file.json_set": c_file_json_set,
    "file.count_glob": c_file_count_glob,
    "http.json_path": c_http_json_path,
    "http.regex": c_http_regex,
    "github.release_tag": c_github_release_tag,
    "github.latest_commit_date": c_github_latest_commit_date,
    "github.issue_state": c_github_issue_state,
}

NONDETERMINISTIC = {"llm_extract"}


# ---------------------------------------------------------------------------
# collection
# ---------------------------------------------------------------------------


def collect_metric(metric: dict, ctx, provided=None) -> dict:
    provided = provided or {}
    name = metric.get("name")
    out = {
        "unit": metric.get("unit", "status"),
        "url": metric.get("url"),
        "collector": metric.get("collector"),
        "deterministic": True,
        "error": None,
    }
    try:
        collector_name, kwargs = resolve_collector(metric)
    except ValueError as exc:
        return {**out, "value": "<error>", "error": str(exc)}

    if collector_name in NONDETERMINISTIC:
        out["deterministic"] = False
        if name in provided:
            return {**out, "value": provided[name]}
        return {
            **out,
            "value": "<error>",
            "error": f"{collector_name} needs an agent-supplied value: --set {name}=<value>",
        }

    fn = COLLECTORS.get(collector_name)
    if fn is None:
        known = ", ".join(sorted(COLLECTORS))
        return {**out, "value": "<error>", "error": f"unknown collector {collector_name!r} (known: {known})"}

    try:
        value, source_url = fn(ctx, **kwargs)
    except Exception as exc:
        return {**out, "value": "<error>", "error": f"{type(exc).__name__}: {exc}"}
    if source_url:
        out["url"] = source_url
    return {**out, "value": value}


def collect_all(spec_obj: dict, ctx, provided=None) -> dict:
    metrics = {}
    for metric in spec_obj.get("metrics") or []:
        if not isinstance(metric, dict) or not metric.get("name"):
            continue
        metrics[str(metric["name"])] = collect_metric(metric, ctx, provided)
    now_fn = getattr(ctx, "now", None)
    now = now_fn() if callable(now_fn) else datetime.now(timezone.utc)
    return {
        "slug": spec_obj.get("slug"),
        "collected_at": _iso_now(),
        "last_run": now.astimezone(timezone.utc).strftime("%Y-%m-%d"),
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# real I/O context
# ---------------------------------------------------------------------------


class StdCtx:
    def __init__(self, timeout=DEFAULT_TIMEOUT):
        self.timeout = timeout

    def read_file(self, path):
        return Path(path).expanduser().read_text(encoding="utf-8")

    def count_glob(self, path, pattern):
        return len(list(Path(path).expanduser().glob(pattern)))

    def fetch(self, url):
        headers = {"User-Agent": "argus-collect"}
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token and "api.github.com" in url:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310 - caller-supplied
            return resp.read()

    def now(self):
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_spec(args) -> dict:
    if args.from_tracker:
        try:
            import yaml  # type: ignore
        except ImportError:
            raise SystemExit(
                "--from-tracker needs PyYAML, which is not importable here.\n"
                "Pass the metrics block as JSON instead:  --spec -  < spec.json"
            )
        doc = yaml.safe_load(Path(args.from_tracker).expanduser().read_text(encoding="utf-8"))
        return {"slug": doc.get("slug"), "metrics": doc.get("metrics") or []}
    raw = Path(args.spec).expanduser().read_text(encoding="utf-8") if args.spec not in (None, "-") else sys.stdin.read()
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit("no spec supplied (use --spec FILE, --spec -, or --from-tracker)")
    spec_obj = json.loads(raw)
    if args.slug:
        spec_obj["slug"] = args.slug
    return spec_obj


def _parse_sets(pairs) -> dict:
    out = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"--set expects name=value, got {item!r}")
        key, value = item.split("=", 1)
        out[key.strip()] = value
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        run_self_test()
        return 0

    parser = argparse.ArgumentParser(description="Argus deterministic metric collector")
    parser.add_argument("--spec", help="JSON spec file, or - for stdin")
    parser.add_argument("--from-tracker", help="tracker YAML (requires PyYAML)")
    parser.add_argument("--slug")
    parser.add_argument("--set", action="append", default=[], dest="sets")
    parser.add_argument("--out", help="write collected metrics here (e.g. state/<slug>.current.json)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)

    spec_obj = _load_spec(args)
    result = collect_all(spec_obj, StdCtx(timeout=args.timeout), provided=_parse_sets(args.sets))
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)

    failed = [n for n, m in result["metrics"].items() if m.get("error")]
    return 1 if failed else 0


class _FakeCtx:
    def __init__(self, files=None, http=None):
        self.files = files or {}
        self.http = http or {}

    def read_file(self, path):
        return self.files[path]

    def count_glob(self, path, pattern):
        return 3

    def fetch(self, url):
        return self.http[url]

    def now(self):
        return datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def run_self_test() -> None:
    ctx = _FakeCtx(
        files={"/scan.json": json.dumps({"repos": [{"name": "b"}, {"name": "a"}]})},
        http={"https://api.example/r": json.dumps([{"tag_name": "v9"}])},
    )
    got = collect_all(
        {
            "slug": "demo",
            "metrics": [
                {"name": "set", "unit": "status", "collector": "file.json_set",
                 "args": {"path": "/scan.json", "json_path": "repos", "key": "name"}},
                {"name": "tag", "unit": "version", "collector": "http.json_path",
                 "args": {"url": "https://api.example/r", "json_path": "0.tag_name"}},
                {"name": "note", "unit": "status", "collector": "llm_extract",
                 "args": {"prompt": "x"}},
            ],
        },
        ctx,
        provided={"note": "agent-supplied"},
    )
    assert got["metrics"]["set"]["value"] == ["a", "b"], got
    assert got["metrics"]["tag"]["value"] == "v9", got
    assert got["metrics"]["note"]["deterministic"] is False
    assert got["metrics"]["note"]["value"] == "agent-supplied"
    assert "last_run" in got
    print("self-test OK: file/json_set, http/json_path, llm_extract escape hatch")


if __name__ == "__main__":
    raise SystemExit(main())
