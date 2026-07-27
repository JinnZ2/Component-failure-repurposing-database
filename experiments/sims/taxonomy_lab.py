#!/usr/bin/env python3
"""
taxonomy_lab.py — falsification harness for QUANTITY_TAXONOMY.md
CC0-1.0.  stdlib only.  single file.

CLAIM UNDER TEST
    Every binding in real code reduces to
        (BINDING_TOPOLOGY, QUANTITY_TYPE over 7 axes, INERT RESIDUE)

THREE EXPERIMENTS
    E1 COVERAGE       can every binding be typed?
                      untypable bindings -> candidate missing axis
    E2 ORTHOGONALITY  are the 7 axes independent?
                      if axis A is determined by axis B, A is redundant
    E3 RESIDUE        is residue actually inert?
                      permute label values; behavior must not change

E2 is the cheapest and sharpest. Run it first.
"""

import ast
import json
import math
import random
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from itertools import combinations
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────
# SPEC — the seven axes
# ─────────────────────────────────────────────────────────────────────

AXES = {
    "extensivity":  ["EXTENSIVE", "INTENSIVE", "NONE"],
    "conservation": ["CONSERVED", "MONOTONE", "PRODUCIBLE", "NONE"],
    "domain":       ["FLOORED", "SIGNED", "BOUNDED", "CEILINGED", "NONE"],
    "datum":        ["ABSOLUTE", "RELATIVE", "NONE"],
    "dimension":    ["DIMENSIONLESS", "DIMENSIONED", "NONE"],
    "transfer":     ["DEBIT_CREDIT", "COPY", "CONSUME", "EQUILIBRATE"],
    "cost":         ["ERASE", "COPY", "TRANSFORM"],
}

UNTYPED = "?"          # human has not judged yet
UNTYPABLE = "FAIL"     # human judged: no axis value fits  -> THIS IS THE DATA


# ─────────────────────────────────────────────────────────────────────
# BINDING TOPOLOGY — recoverable from source, no judgement required
# ─────────────────────────────────────────────────────────────────────

@dataclass
class BindingSite:
    name: str
    file: str
    scope: str              # "module" | "func:<name>" | "class:<name>"
    scope_kind: str
    first_write: int        # line
    last_read: int          # line, -1 if never read
    n_writes: int
    n_reads: int
    augmented: bool         # participates in x += ... (accumulator shape)
    is_param: bool
    is_loop_var: bool
    literal_kinds: list     # observed RHS literal types
    axes: dict = field(default_factory=dict)

    @property
    def lifetime(self):
        return max(0, self.last_read - self.first_write)

    @property
    def key(self):
        return f"{self.file}::{self.scope}::{self.name}"


class BindingExtractor(ast.NodeVisitor):
    """Walks one module. Emits a BindingSite per (scope, name)."""

    def __init__(self, filename):
        self.filename = filename
        self.scope_stack = [("module", "module")]
        self.sites = {}

    # -- scope helpers -------------------------------------------------
    @property
    def scope(self):
        return self.scope_stack[-1][0]

    @property
    def scope_kind(self):
        return self.scope_stack[-1][1]

    def _site(self, name, lineno):
        k = (self.scope, name)
        if k not in self.sites:
            self.sites[k] = BindingSite(
                name=name, file=self.filename, scope=self.scope,
                scope_kind=self.scope_kind, first_write=lineno,
                last_read=-1, n_writes=0, n_reads=0, augmented=False,
                is_param=False, is_loop_var=False, literal_kinds=[],
                axes={a: UNTYPED for a in AXES},
            )
        return self.sites[k]

    def _write(self, name, lineno, **flags):
        s = self._site(name, lineno)
        s.n_writes += 1
        s.first_write = min(s.first_write, lineno)
        for f, v in flags.items():
            if v:
                setattr(s, f, True)
        return s

    def _read(self, name, lineno):
        k = (self.scope, name)
        if k in self.sites:
            s = self.sites[k]
            s.n_reads += 1
            s.last_read = max(s.last_read, lineno)

    # -- scoped constructs ---------------------------------------------
    def _enter(self, node, kind):
        self.scope_stack.append((f"{kind}:{node.name}", kind))

    def visit_FunctionDef(self, node):
        self._enter(node, "func")
        for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            self._write(a.arg, node.lineno, is_param=True)
        for a in (node.args.vararg, node.args.kwarg):
            if a is not None:
                self._write(a.arg, node.lineno, is_param=True)
        self.generic_visit(node)
        self.scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self._enter(node, "class")
        self.generic_visit(node)
        self.scope_stack.pop()

    # -- bindings -------------------------------------------------------
    def _targets(self, t):
        if isinstance(t, ast.Name):
            yield t.id
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                yield from self._targets(e)
        elif isinstance(t, ast.Starred):
            yield from self._targets(t.value)

    def _literal_kind(self, node):
        if isinstance(node, ast.Constant):
            return type(node.value).__name__
        if isinstance(node, (ast.List, ast.Tuple)):
            return "seq"
        if isinstance(node, ast.Dict):
            return "map"
        return None

    def visit_Assign(self, node):
        lk = self._literal_kind(node.value)
        for t in node.targets:
            for n in self._targets(t):
                s = self._write(n, node.lineno)
                if lk:
                    s.literal_kinds.append(lk)
        self.visit(node.value)

    def visit_AnnAssign(self, node):
        for n in self._targets(node.target):
            self._write(n, node.lineno)
        if node.value:
            self.visit(node.value)

    def visit_AugAssign(self, node):
        for n in self._targets(node.target):
            self._write(n, node.lineno, augmented=True)
            self._read(n, node.lineno)
        self.visit(node.value)

    def visit_For(self, node):
        for n in self._targets(node.target):
            self._write(n, node.lineno, is_loop_var=True)
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self._read(node.id, node.lineno)


def extract(paths):
    sites = []
    for p in paths:
        src = Path(p).read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src, filename=str(p))
        except SyntaxError as e:
            print(f"  skip {p}: {e}", file=sys.stderr)
            continue
        ex = BindingExtractor(str(p))
        ex.visit(tree)
        sites.extend(ex.sites.values())
    return sites


# ─────────────────────────────────────────────────────────────────────
# HEURISTIC PRE-TYPING — a PROPOSAL, not an answer.
# Every guess must be confirmed or overridden by hand.
# The guesses exist only to cut annotation labor, and they are
# deliberately conservative: unknown stays unknown.
# ─────────────────────────────────────────────────────────────────────

def pretype(s: BindingSite):
    g = dict(s.axes)
    if s.augmented and "int" in s.literal_kinds:
        g["extensivity"] = "EXTENSIVE"
        g["conservation"] = "MONOTONE"
        g["domain"] = "FLOORED"
    if s.is_loop_var:
        g["extensivity"] = "EXTENSIVE"
        g["conservation"] = "MONOTONE"
        g["datum"] = "RELATIVE"
    if "bool" in s.literal_kinds:
        g["extensivity"] = "NONE"
        g["dimension"] = "DIMENSIONLESS"
        g["cost"] = "ERASE"
    if "str" in s.literal_kinds:
        g["transfer"] = "COPY"
        g["dimension"] = "NONE"
    if s.n_writes == 1 and s.n_reads > 1:
        g["transfer"] = g["transfer"] if g["transfer"] != UNTYPED else "COPY"
    return g


# ─────────────────────────────────────────────────────────────────────
# WORKSHEET I/O
# ─────────────────────────────────────────────────────────────────────

def save(sites, path):
    Path(path).write_text(json.dumps(
        [asdict(s) | {"lifetime": s.lifetime} for s in sites],
        indent=1), encoding="utf-8")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────
# E1 — COVERAGE.  Untypable bindings are the payload.
# ─────────────────────────────────────────────────────────────────────

def experiment_coverage(rows):
    total = len(rows)
    per_axis = {}
    for a in AXES:
        vals = Counter(r["axes"][a] for r in rows)
        per_axis[a] = {
            "typed": total - vals[UNTYPED] - vals[UNTYPABLE],
            "unjudged": vals[UNTYPED],
            "FAIL": vals[UNTYPABLE],
        }
    print(f"\nE1 COVERAGE   n={total} bindings\n")
    print(f"  {'axis':<14}{'typed':>8}{'unjudged':>10}{'FAIL':>7}")
    for a, d in per_axis.items():
        print(f"  {a:<14}{d['typed']:>8}{d['unjudged']:>10}{d['FAIL']:>7}")
    fails = [r for r in rows if UNTYPABLE in r["axes"].values()]
    if fails:
        print(f"\n  {len(fails)} bindings no axis value fits — MISSING AXIS CANDIDATES:")
        for r in fails[:25]:
            bad = [a for a, v in r["axes"].items() if v == UNTYPABLE]
            print(f"    {r['name']:<24} {r['scope']:<22} axes={bad}")
    return per_axis


# ─────────────────────────────────────────────────────────────────────
# E2 — ORTHOGONALITY.  The axis-independence test.
#
#   U(A|B) = (H(A) - H(A|B)) / H(A)      uncertainty coefficient
#   U = 1.0  ->  A is FULLY determined by B  ->  A is redundant
#   U = 0.0  ->  B says nothing about A
#
#   Small corpora inflate U. So we build a null by shuffling B
#   and report an empirical p-value.
# ─────────────────────────────────────────────────────────────────────

def _H(labels):
    n = len(labels)
    if n == 0:
        return 0.0
    c = Counter(labels)
    return -sum((k / n) * math.log2(k / n) for k in c.values())


def _H_cond(a, b):
    n = len(a)
    if n == 0:
        return 0.0
    buckets = defaultdict(list)
    for x, y in zip(a, b):
        buckets[y].append(x)
    return sum(len(v) / n * _H(v) for v in buckets.values())


def _U(a, b):
    ha = _H(a)
    if ha == 0:
        return float("nan")
    return (ha - _H_cond(a, b)) / ha


def experiment_orthogonality(rows, trials=2000, seed=0):
    rng = random.Random(seed)

    print(f"\nE2 ORTHOGONALITY   trials={trials}\n")
    print(f"  {'A':<14}{'B':<14}{'U(A|B)':>8}{'U(B|A)':>8}{'p':>8}  verdict")
    results = []
    for x, y in combinations(AXES, 2):
        # align: only rows where BOTH axes are judged
        pairs = [(r["axes"][x], r["axes"][y]) for r in rows
                 if r["axes"][x] not in (UNTYPED, UNTYPABLE)
                 and r["axes"][y] not in (UNTYPED, UNTYPABLE)]
        if len(pairs) < 10:
            print(f"  {x:<14}{y:<14}{'—':>8}{'—':>8}{'—':>8}  "
                  f"skipped: only {len(pairs)} judged pairs (need 10)")
            continue
        A = [p[0] for p in pairs]
        B = [p[1] for p in pairs]
        uab, uba = _U(A, B), _U(B, A)
        # a constant column carries no entropy — nothing to be determined by.
        # report it, do not silently score it.
        if math.isnan(uab) and math.isnan(uba):
            print(f"  {x:<14}{y:<14}{'—':>8}{'—':>8}{'—':>8}  "
                  f"degenerate: both axes constant over n={len(pairs)}")
            results.append((x, y, uab, uba, float("nan"), "degenerate"))
            continue
        obs = max(v for v in (uab, uba) if not math.isnan(v))
        # null: destroy the relationship, keep the marginals
        null = 0
        Bs = list(B)
        for _ in range(trials):
            rng.shuffle(Bs)
            cand = [v for v in (_U(A, Bs), _U(Bs, A)) if not math.isnan(v)]
            if cand and max(cand) >= obs:
                null += 1
        p = (null + 1) / (trials + 1)
        if p < 0.05 and obs > 0.9:
            verdict = "REDUNDANT — collapse these"
        elif p < 0.05 and obs > 0.5:
            verdict = "coupled — not independent"
        elif p < 0.05:
            verdict = "weak coupling"
        else:
            verdict = "independent"
        ab = "—" if math.isnan(uab) else f"{uab:.3f}"
        ba = "—" if math.isnan(uba) else f"{uba:.3f}"
        print(f"  {x:<14}{y:<14}{ab:>8}{ba:>8}{p:>8.4f}  {verdict}")
        results.append((x, y, uab, uba, p, verdict))
    return results


# ─────────────────────────────────────────────────────────────────────
# E3 — RESIDUE INERTNESS.  The ID question, made behavioral.
#
#   Take a program + fixed input. Permute the VALUES of every literal
#   bound to a name the annotator marked as pure convention residue.
#   Run again. Compare output.
#
#   identical  -> residue confirmed inert; only the edge mattered
#   different  -> the label smuggled a quantity; reduction is WRONG
# ─────────────────────────────────────────────────────────────────────

def _const_key(v):
    """Type-tagged literal key.

    Plain equality conflates True/1/1.0 — they hash alike, so a dict keyed on
    the bare value would merge distinct literals and rewrite the wrong ones.
    Identity does not work either: the permuter re-parses the source, so its
    Constant objects are fresh and `is` fails for floats and large ints.
    """
    return (type(v).__name__, v)


class _Permuter(ast.NodeTransformer):
    def __init__(self, names, mapping):
        self.names = set(names)
        self.mapping = mapping
        self.hits = 0

    def visit_Assign(self, node):
        tgt = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if any(t in self.names for t in tgt) and isinstance(node.value, ast.Constant):
            k = _const_key(node.value.value)
            if k in self.mapping:
                node.value = ast.copy_location(
                    ast.Constant(self.mapping[k]), node.value)
                self.hits += 1
        return node


def experiment_residue(program, residue_names, stdin_text="", trials=8, seed=0):
    rng = random.Random(seed)
    src = Path(program).read_text(encoding="utf-8")
    tree = ast.parse(src)

    # type-tagged, so True/1 and 1/1.0 stay distinct literals
    values, seen = [], set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant):
            tgt = [t.id for t in n.targets if isinstance(t, ast.Name)]
            if any(t in set(residue_names) for t in tgt):
                k = _const_key(n.value.value)
                if k not in seen:
                    seen.add(k)
                    values.append(n.value.value)

    print(f"\nE3 RESIDUE   program={program}")
    print(f"  residue names : {residue_names}")
    print(f"  literals found: {values}")
    if len(values) < 2:
        print("  ! need >=2 distinct literals to permute. no test.")
        return None

    base = subprocess.run([sys.executable, program], input=stdin_text,
                          capture_output=True, text=True, timeout=60)
    print(f"  baseline rc={base.returncode} out_len={len(base.stdout)}")

    verdicts = []
    for t in range(trials):
        idx = list(range(len(values)))
        rng.shuffle(idx)
        if all(i == j for i, j in enumerate(idx)):
            continue
        mapping = {_const_key(values[i]): values[j] for i, j in enumerate(idx)}
        tr = _Permuter(residue_names, mapping)
        new = ast.fix_missing_locations(tr.visit(ast.parse(src)))
        tmp = Path(program).with_suffix(f".perm{t}.py")
        tmp.write_text(ast.unparse(new), encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, str(tmp)], input=stdin_text,
                               capture_output=True, text=True, timeout=60)
            same = (r.stdout == base.stdout and r.returncode == base.returncode)
            verdicts.append(same)
            shown = {f"{a[0]}:{a[1]!r}": repr(b) for a, b in mapping.items()}
            print(f"  trial {t}: sites={tr.hits} map={shown} "
                  f"-> {'INERT' if same else 'BEHAVIOR CHANGED'}")
        finally:
            tmp.unlink(missing_ok=True)

    if not verdicts:
        print("  ! no distinct permutation produced")
        return None
    if all(verdicts):
        print("\n  VERDICT: residue inert. value carried no quantity. edge only.")
    else:
        print("\n  VERDICT: residue is LOAD-BEARING. the reduction is wrong here.")
        print("  -> the label smuggled ordering, indexing, or magnitude.")
        print("  -> candidate: labels need their own category, not 'convention'.")
    return verdicts


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

USAGE = """\
usage:
  taxonomy_lab.py extract <out.json> <file.py> [file.py ...]
      walk source, recover binding topology, attach heuristic guesses.
      then EDIT out.json by hand: set each axis, or "FAIL" if none fits.

  taxonomy_lab.py e1 <worksheet.json>          coverage / missing axes
  taxonomy_lab.py e2 <worksheet.json>          axis orthogonality
  taxonomy_lab.py e3 <prog.py> <name,name,..>  residue permutation
  taxonomy_lab.py selftest                     run on this file
"""


def main(argv):
    if len(argv) < 2:
        print(USAGE)
        return 1
    cmd = argv[1]

    if cmd == "extract":
        out, files = argv[2], argv[3:]
        sites = extract(files)
        for s in sites:
            s.axes = pretype(s)
        save(sites, out)
        print(f"{len(sites)} bindings -> {out}")
        print("EDIT IT. heuristic guesses are proposals, not data.")
        return 0

    if cmd == "e1":
        experiment_coverage(load(argv[2]))
        return 0

    if cmd == "e2":
        experiment_orthogonality(load(argv[2]))
        return 0

    if cmd == "e3":
        names = argv[3].split(",")
        experiment_residue(argv[2], names)
        return 0

    if cmd == "selftest":
        sites = extract([__file__])
        for s in sites:
            s.axes = pretype(s)
        rows = json.loads(json.dumps([asdict(s) for s in sites]))
        experiment_coverage(rows)
        experiment_orthogonality(rows, trials=500)
        print("\nnote: selftest types come from HEURISTICS ONLY.")
        print("any coupling seen here may be an artifact of the guesser,")
        print("not a property of the taxonomy. hand-annotate before believing it.")
        return 0

    print(USAGE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
