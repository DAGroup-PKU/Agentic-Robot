"""Render the PyRUA-Lean post ("Code, Not Calls") from its results snapshot (standard library only).

    python scripts/build_pyrualean_post.py                  # article + project card
    python scripts/build_pyrualean_post.py --trim-snapshot  # first drop the batches the post does not use

Inputs
  content/pyrualean-results.json               exported by PyRUA-Lean's
                                                runs/research/efficiency_page.py --json; every
                                                statistic here is computed from its per-cell pairs
  content/articles/fewer-tokens-better-action.template.html prose with [[KEY]] tokens and [[CHART_*]] blocks
Outputs
  content/articles/fewer-tokens-better-action.html          the body read by build.py
  content/projects.json                         the numbers on the PyRUA-Lean project card

Every figure is interactive: each chart block carries its data as JSON, and
assets/pyrualean/charts.js draws it in the browser, with the exact numbers in its tooltips. The post reports GPT-6 Astra. Each benchmark
row merges the snapshot blocks listed in BENCHMARKS (batches of one benchmark with disjoint cells),
so a new batch is one more prefix there. To update the numbers: replace the snapshot, rerun this
script, then build the site as usual. Every number in the post comes from the snapshot, so prose,
tables, charts and card cannot drift apart. An unknown [[KEY]] is an error.
"""
from __future__ import annotations

import argparse
import bisect
import html
import json
import math
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "content" / "pyrualean-results.json"
TEMPLATE = ROOT / "content" / "articles" / "fewer-tokens-better-action.template.html"
ARTICLE = ROOT / "content" / "articles" / "fewer-tokens-better-action.html"

ARMS = ("rpent", "cells")
#: (key, name, snapshot blocks as prefix lists) of the main comparison, in table order.
BENCHMARKS = [
    ("libero", "LIBERO-PRO", [["e4d"], ["e5"], ["e6"]]),  # 12 tasks x seeds 0-4, 28 x 0-1, the 28 x 2-4
    # every task at five seeds: 12 x 5 (rt1); the other 38 at three (rt2, rt3) and two more (rt4), rt2b completing the
    # three rt2 tasks with a seed RoboTwin cannot initialize; a refused seed is replaced by the one RoboTwin picks or the
    # next one (rt4b-rt4h); the export keeps each task's first five valid seeds
    ("robotwin", "RoboTwin 2.0", [["rt1"], ["rt2"], ["rt3"], ["rt2b"], ["rt4"], ["rt4b"], ["rt4c"], ["rt4d"], ["rt4e"],
                                  ["rt4f"], ["rt4g"], ["rt4h"]]),
    # the 18 atomic Target50 tasks x seeds 1-5 (rc1); CoffeeSetupMug seed 4 renders only noise on every camera, so the
    # export keeps its seed 6 from rc2 instead (cells= filter)
    ("robocasa", "RoboCasa365 atomic", [["rc1"], ["rc2"]]),
    ("composite", "RoboCasa365 composite", [["rcc1"]]),  # 32 composite tasks x 5 seeds, 100 requests
]
#: Rows whose episodes ran with a budget of 100 model requests; every other row ran with 40.
BUDGET_100 = {"composite"}
#: Switch ablation on a subset of each benchmark's tasks, at the main comparison's five seeds: both arms lose the VLA
#: policy and/or the shared guides together. The first setting of a group is its baseline, the main comparison
#: restricted to the same cells. A setting is one snapshot block or several (a list, merged like a benchmark row); the
#: prose keys of a setting take the name of its first block.
ABLATION = [
    ("libero", "LIBERO-PRO", [("VLA + guides", "e4d"), ("VLA, no guides", "ng1"),
                              ("No VLA, guides", "nv1"), ("No VLA, no guides", "nvng1")]),
    ("robotwin", "RoboTwin 2.0", [("VLA + guides", "rt1"), ("VLA, no guides", "rtng1"),
                                  ("No VLA, guides", "rtnv1"), ("No VLA, no guides", "rtnvng1")]),
    # seeds 1-5, with CoffeeSetupMug's seed 6 for its seed 4 as in the main comparison (rc2 and rcnv3 hold only that cell)
    ("robocasa", "RoboCasa365 atomic", [("VLA", ["rc1", "rc2"]), ("No VLA", ["rcnv1", "rcnv3"])]),
]


def setting_blocks(prefix: str | list[str]) -> list[str]:
    """The snapshot blocks of one ablation setting."""
    return [prefix] if isinstance(prefix, str) else list(prefix)
CODE_COLOR, TOOL_COLOR = "#c26a40", "#4a68b5"  # validated pair on the #f5f4ef paper surface
#: GPT-6 Astra list prices in dollars per 1M tokens (OpenAI API, Standard tier, read 2026-09-24,
#: https://developers.openai.com/api/docs/pricing). Each episode's bill ("usd" in the snapshot) is
#: computed request by request from its token usage by runs/research/pricing.py of the pyrualean
#: repository. A request above 272K input tokens would cost 2x input and 1.5x output; none reached it.
PRICES = {"input": 10.00, "cached": 1.00, "cache_write": 12.50, "output": 50.00}


# -- data -------------------------------------------------------------------------------------


def load() -> dict:
    data = json.loads(SNAPSHOT.read_text())
    return {(b["section"], tuple(b["prefixes"])): b for b in data["blocks"]}


def used_blocks() -> set[tuple[str, tuple[str, ...]]]:
    """(section, prefixes) of every snapshot block the post reads."""
    used = {("main", tuple(p)) for _, _, lists in BENCHMARKS for p in lists}
    return used | {("ablation", (b,)) for _, _, settings in ABLATION for _, prefix in settings
                   for b in setting_blocks(prefix)}


def trim_snapshot() -> int:
    """Drop the snapshot blocks the post does not use (the export carries every batch), and the export's
    summary fields and run labels of the rest: the post computes everything from the per-instance pairs, and a
    block is named by its prefixes."""
    data = json.loads(SNAPSHOT.read_text())
    keep = used_blocks()
    before = len(data["blocks"])
    data["blocks"] = [{k: b[k] for k in ("section", "prefixes", "model", "n", "pairs") if k in b}
                      for b in data["blocks"] if (b["section"], tuple(b["prefixes"])) in keep]
    SNAPSHOT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return before - len(data["blocks"])


def merged(index: dict, prefix_lists: list[list[str]], section: str = "main") -> dict | None:
    """One benchmark row or ablation setting: the pairs, success@100 and curves of its blocks."""
    blocks = [index.get((section, tuple(p))) for p in prefix_lists]
    blocks = [b for b in blocks if b]
    if not blocks:
        return None
    # a cell counts once both arms finished an episode: one killed before its first request (the
    # gateway out of budget, say) is not a result, and its cell waits for a rerun
    pairs = [p for b in blocks for p in b["pairs"] if all(p[a]["input"] and p[a].get("usd") is not None for a in ARMS)]
    out = {"pairs": pairs}
    return out


# -- statistics from the per-cell pairs ---------------------------------------------------------


def solved_budgets(pairs: list[dict], arm: str, field: str) -> list[float]:
    """Sorted budgets (prompt tokens or requests up to the successful request) of an arm's solved cells."""
    return sorted(p[arm][field] for p in pairs if p[arm]["success"] and p[arm][field])


def budget_curve(pairs: list[dict], field: str, grid: list[float]) -> dict[str, list[int]]:
    """Cells each arm solves within each budget of the grid."""
    return {arm: [bisect.bisect_right(v, b) for b in grid]
            for arm, v in ((arm, solved_budgets(pairs, arm, field)) for arm in ARMS)}


def reach(pairs: list[dict], field: str) -> dict | None:
    """The budget each arm needs to solve as many cells as tool calling finally does (where its
    curve converges): the dashed line of Figure 4."""
    level = sum(p["rpent"]["success"] for p in pairs)
    need = {arm: solved_budgets(pairs, arm, field) for arm in ARMS}
    if not level or any(len(v) < level for v in need.values()):
        return None
    out = {"level": level, "rpent": need["rpent"][level - 1], "cells": need["cells"][level - 1]}
    out["ratio"] = out["rpent"] / out["cells"]
    return out


def both_solved(pairs: list[dict]) -> list[dict]:
    """Pairs both arms solved, with token and decision counts on both sides."""
    return [
        p for p in pairs
        if p["rpent"]["success"] and p["cells"]["success"]
        and p["rpent"]["input"] and p["cells"]["input"]
        and p["rpent"]["decisions"] and p["cells"]["decisions"]
    ]


def prompt(arm: dict) -> float:
    return arm["input"]


def price(arm: dict) -> float:
    """The episode's bill in dollars at GPT-6 Astra list prices (computed per request upstream)."""
    if arm.get("usd") is None:
        raise ValueError("a pair without a list-price bill; re-export the snapshot")
    return arm["usd"]


def output_usd(arm: dict) -> float:
    return (arm["output"] or 0) * PRICES["output"] / 1e6


def total_ratio(pairs: list[dict], f) -> float:
    """sum over pairs of f(RPent) / sum of f(code): the ratio of the two bills."""
    c = sum(f(p["cells"]) for p in pairs)
    return sum(f(p["rpent"]) for p in pairs) / c if c else float("nan")


def median_of(values) -> float | None:
    values = [v for v in values if v is not None]
    return st.median(values) if values else None


def summarize(row: dict) -> dict:
    """Every number the post quotes for one benchmark row or ablation setting."""
    ps = row["pairs"]
    both = both_solved(ps)
    s: dict = {
        "n": len(ps),
        "tasks": len({tuple(p["cell"][:2]) for p in ps}),
        "both": len(both),
        "succ": {arm: sum(p[arm]["success"] for p in ps) for arm in ARMS},


        "first": {arm: median_of(p[arm]["first_request"] for p in ps) for arm in ARMS},
    }
    failed = {arm: [p[arm] for p in ps if not p[arm]["success"]] for arm in ARMS}
    s["fail"] = {arm: {mode: sum(f["failure"] == mode for f in failed[arm]) for mode in ("cap", "gave_up")}
                 | {"n": len(failed[arm])} for arm in ARMS}
    s["gave_up_dec"] = {arm: median_of(f["decisions"] for f in failed[arm] if f["failure"] == "gave_up")
                        for arm in ARMS}
    s["pairs"] = ps
    s["reach"] = {field: reach(ps, field) for field in ("to_success", "success_request")}
    every = [p for p in ps if p["rpent"]["input"] and p["cells"]["input"]]
    s["all_ratio"] = total_ratio(every, prompt) if every else None
    if len(both) >= 2:
        s["ratio"] = total_ratio(both, prompt)
        s["price"] = total_ratio(both, price)
        s["median_ratio"] = st.median(p["rpent"]["input"] for p in both) / st.median(p["cells"]["input"] for p in both)
        s["wins"] = sum(p["cells"]["input"] < p["rpent"]["input"] for p in both) / len(both)
        s["req"] = {arm: st.mean(p[arm]["decisions"] for p in both) for arm in ARMS}
        s["req_ratio"] = total_ratio(both, lambda a: a["decisions"])
        s["tpr_ratio"] = s["ratio"] / s["req_ratio"]
        s["tts"] = {arm: median_of(p[arm]["to_success"] for p in both) for arm in ARMS}
        s["tts_dec"] = {arm: median_of(p[arm]["success_request"] for p in both) for arm in ARMS}
        s["steps_code_x"] = 1 / total_ratio(both, lambda a: a["env_steps"] or 0)
        s["out_code_x"] = 1 / total_ratio(both, lambda a: a["output"] or 0)
        s["usd"] = {arm: st.mean(price(p[arm]) for p in both) for arm in ARMS}
        s["mean_input"] = {arm: st.mean(p[arm]["input"] for p in both) for arm in ARMS}
        s["out_share"] = {arm: sum(output_usd(p[arm]) for p in both) / sum(price(p[arm]) for p in both)
                          for arm in ARMS}
    return s


def main_rows(index) -> list[tuple[str, str, dict]]:
    rows = []
    for key, name, prefix_lists in BENCHMARKS:
        row = merged(index, prefix_lists)
        if row and row["pairs"]:
            rows.append((key, name, summarize(row)))
    return rows


def ablation_rows(index) -> list[tuple[str, str, list[tuple[str, str, dict]]]]:
    groups = []
    for family, name, settings in ABLATION:
        out = []
        for setting, prefix in settings:
            blocks = setting_blocks(prefix)
            row = merged(index, [[b] for b in blocks], "ablation")
            if row and row["pairs"]:
                out.append((setting, blocks[0], summarize(row)))
        if out:
            groups.append((family, name, out))
    return groups


# -- formatting ---------------------------------------------------------------------------


def times(value, digits=1) -> str:
    return f"{value:.{digits}f}×"


def tokens(value) -> str:
    if value is None:
        return "–"
    return f"{value / 1e6:.2f}M" if value >= 1e6 else f"{value / 1e3:.0f}k"


def pct(share) -> str:
    return f"{100 * share:.0f}%"


def dollars(value) -> str:
    return f"${value:.2f}"


# -- numbers quoted in the prose --------------------------------------------------------------

NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}


def keys(rows, groups) -> dict[str, str]:
    k: dict[str, str] = {}
    for key, _, s in rows:
        up = key.upper()
        k[f"{up}_N"] = str(s["n"])
        k[f"{up}_TASKS"] = str(s["tasks"])
        k[f"{up}_BOTH"] = str(s["both"])
        k[f"{up}_SUCC_RPENT"] = str(s["succ"]["rpent"])
        k[f"{up}_SUCC_CODE"] = str(s["succ"]["cells"])
        rates = {arm: 100 * s["succ"][arm] / s["n"] for arm in ARMS}
        k[f"{up}_RATE_RPENT"] = f"{rates['rpent']:.1f}%"
        k[f"{up}_RATE_CODE"] = f"{rates['cells']:.1f}%"
        points = rates["cells"] - rates["rpent"]
        k[f"{up}_PTS"] = f"{'+' if points >= 0 else chr(0x2212)}{abs(points):.1f}"
        for arm, name in (("rpent", "RPENT"), ("cells", "CODE")):
            k[f"{up}_FIRST_{name}"] = tokens(s["first"][arm])
            fails = s["fail"][arm]
            if fails["n"]:
                k[f"{up}_CAP_SHARE_{name}"] = pct(fails["cap"] / fails["n"])
            # share of all task instances whose episode ran out of LLM calls (RQ1's failure kinds)
            k[f"{up}_CAP_RATE_{name}"] = f"{100 * fails['cap'] / s['n']:.1f}%"
            if s["gave_up_dec"][arm] is not None:
                k[f"{up}_GAVEUP_DEC_{name}"] = f"{s['gave_up_dec'][arm]:.0f}"
        if s["all_ratio"]:
            k[f"{up}_ALL_RATIO_PT"] = times(s["all_ratio"], 2)
        if "ratio" in s:
            k[f"{up}_RATIO_PT"] = times(s["ratio"])
            k[f"{up}_MEDIAN_PT"] = times(s["median_ratio"], 2)
            k[f"{up}_PRICE_PT"] = times(s["price"])
            k[f"{up}_CHEAPER"] = pct(s["wins"])
            k[f"{up}_REQ_RATIO_PT"] = times(s["req_ratio"])
            k[f"{up}_TPR_RATIO_PT"] = times(s["tpr_ratio"])
            # two decimals where the text multiplies them: calls factor x per-call factor = token factor
            k[f"{up}_RATIO_X2"] = times(s["ratio"], 2)
            k[f"{up}_REQ_RATIO_X2"] = times(s["req_ratio"], 2)
            k[f"{up}_TPR_RATIO_X2"] = times(s["tpr_ratio"], 2)
            k[f"{up}_STEPS_CODE_X"] = times(s["steps_code_x"])
            k[f"{up}_OUT_CODE_X"] = times(s["out_code_x"])
            for arm, name in (("rpent", "RPENT"), ("cells", "CODE")):
                k[f"{up}_USD_{name}"] = dollars(s["usd"][arm])
                k[f"{up}_OUT_SHARE_{name}"] = pct(s["out_share"][arm])
            for arm, name in (("rpent", "RPENT"), ("cells", "CODE")):
                k[f"{up}_REQ_{name}"] = f"{s['req'][arm]:.0f}"
                k[f"{up}_TTS_{name}"] = tokens(s["tts"][arm])
                k[f"{up}_TTS_DEC_{name}"] = f"{s['tts_dec'][arm]:.0f}"
        for budget in (500_000, 1_000_000, 3_000_000):
            tag = f"{budget // 100_000:02d}"  # 05 = 0.5M, 10 = 1M, 30 = 3M
            within = budget_curve(s["pairs"], "to_success", [budget])
            k[f"{up}_AT{tag}M_RPENT"] = pct(within["rpent"][0] / s["n"])
            k[f"{up}_AT{tag}M_CODE"] = pct(within["cells"][0] / s["n"])
        r_tok, r_req = s["reach"]["to_success"], s["reach"]["success_request"]
        if r_tok:
            k[f"{up}_REACH_LEVEL"] = f"{100 * r_tok['level'] / s['n']:.1f}%"
            k[f"{up}_REACH_RPENT"] = tokens(r_tok["rpent"])
            k[f"{up}_REACH_CODE"] = tokens(r_tok["cells"])
            k[f"{up}_REACH_X"] = times(r_tok["ratio"])
        if r_req:
            k[f"{up}_REACH_REQ_RPENT"] = f"{r_req['rpent']:.0f}"
            k[f"{up}_REACH_REQ_CODE"] = f"{r_req['cells']:.0f}"
            k[f"{up}_REACH_REQ_X"] = times(r_req["ratio"])
    shares = [s["out_share"][arm] for _, _, s in rows if "out_share" in s for arm in ARMS]
    if shares:
        k["OUT_SHARE_MAX"] = pct(max(shares))
    k["FIT_GAP"] = f"{math.ceil(fit_gap(rows)):.0f}"
    stepped = [s["steps_code_x"] for _, _, s in rows if "steps_code_x" in s]
    if stepped:
        k["STEPS_CODE_MAX"] = times(max(stepped))
    for family, _, settings in groups:
        pts = [s["ratio"] for _, _, s in settings if "ratio" in s]
        if pts:
            k[f"AB_RANGE_{family.upper()}"] = f"{min(pts):.1f}–{max(pts):.1f}×"
        for _, prefix, s in settings:
            tag = prefix.upper()
            k[f"AB_{tag}_N"] = str(s["n"])
            k[f"AB_{tag}_SUCC_RPENT"] = str(s["succ"]["rpent"])
            k[f"AB_{tag}_SUCC_CODE"] = str(s["succ"]["cells"])
            k[f"AB_{tag}_PTS"] = f"{100 * (s['succ']['cells'] - s['succ']['rpent']) / s['n']:+.0f}".replace("-", chr(0x2212))
            k[f"AB_{tag}_RATE_RPENT"] = pct(s["succ"]["rpent"] / s["n"])
            k[f"AB_{tag}_RATE_CODE"] = pct(s["succ"]["cells"] / s["n"])
            if "ratio" in s:
                k[f"AB_{tag}_RATIO_PT"] = times(s["ratio"])
                k[f"AB_{tag}_REQ_RPENT"] = f"{s['req']['rpent']:.0f}"
                k[f"AB_{tag}_REQ_CODE"] = f"{s['req']['cells']:.0f}"
                k[f"AB_{tag}_REQ_RATIO_PT"] = times(s["req_ratio"])
    # The four benchmarks together (the title's numbers): SR over all task instances, and prompt tokens
    # summed over the instances both agents solved, so the longest episodes (LIBERO-PRO) weigh most.
    n_all = sum(s["n"] for _, _, s in rows)
    solved = {arm: sum(s["succ"][arm] for _, _, s in rows) for arm in ARMS}
    both_tokens = {arm: sum(p[arm]["input"] for _, _, s in rows for p in both_solved(s["pairs"])) for arm in ARMS}
    k["POOLED_SR_RPENT"] = f"{100 * solved['rpent'] / n_all:.1f}%"
    k["POOLED_SR_CODE"] = f"{100 * solved['cells'] / n_all:.1f}%"
    k["POOLED_SR_REL"] = f"{100 * (solved['cells'] / solved['rpent'] - 1):.0f}%"
    k["POOLED_TOKENS_FEWER"] = f"{100 * (1 - both_tokens['cells'] / both_tokens['rpent']):.0f}%"
    k["POOLED_TOKEN_FACTOR"] = times(both_tokens["rpent"] / both_tokens["cells"])
    # per-benchmark ranges for the subtitle: relative SR gain and share of tokens saved
    rel = [100 * (s["succ"]["cells"] / s["succ"]["rpent"] - 1) for _, _, s in rows]
    saved = [100 * (1 - 1 / s["ratio"]) for _, _, s in rows if "ratio" in s]
    k["SR_REL_RANGE"] = f"{min(rel):.0f}–{max(rel):.0f}%"
    k["TOKENS_SAVED_RANGE"] = f"{min(saved):.0f}–{max(saved):.0f}%"
    k["TOTAL_MAIN_CELLS"] = str(sum(s["n"] for _, _, s in rows))
    k["TOTAL_TASKS"] = str(sum(s["tasks"] for _, _, s in rows))
    rt = next((s["tasks"] for key, _, s in rows if key == "robotwin"), None)
    if rt:
        k["ROBOTWIN_TASKS_PHRASE"] = ("all 50 RoboTwin 2.0 dual-arm tasks" if rt == 50
                                      else f"{rt} of the 50 RoboTwin 2.0 dual-arm tasks")
    # how many times as often tool calling runs out of calls, in words, over the benchmarks with 40 calls
    factors = [s["fail"]["rpent"]["cap"] / s["fail"]["cells"]["cap"] for key, _, s in rows
               if key not in BUDGET_100 and s["fail"]["cells"]["cap"]]
    if factors:
        lo, hi = round(min(factors)), round(max(factors))
        k["CAP_TIMES"] = (f"{NUMBER_WORDS.get(lo, str(lo))} times" if lo == hi
                          else f"{NUMBER_WORDS.get(lo, str(lo))} to {NUMBER_WORDS.get(hi, str(hi))} times")
    k["TOTAL_MAIN_EPISODES"] = str(2 * sum(s["n"] for _, _, s in rows))
    # the first setting of every group re-uses cells of the main comparison
    k["TOTAL_ABLATION_EPISODES"] = str(2 * sum(s["n"] for _, _, settings in groups for _, _, s in settings[1:]))
    return k


def fill(text: str, values: dict[str, str], where: str) -> str:
    def sub(match):
        name = match.group(1)
        if name not in values:
            raise KeyError(f"unknown token [[{name}]] in {where}")
        return values[name]

    return re.sub(r"\[\[([A-Z0-9_]+)\]\]", sub, text)


def render(rows, groups) -> str:
    return fill(TEMPLATE.read_text(), keys(rows, groups) | charts(rows, groups), TEMPLATE.name)


#: The project card's numbers, filled from the same keys as the article so the two cannot drift.
PROJECTS = ROOT / "content" / "projects.json"
PROJECT_CARD = {
    "metrics": [{"value": "3", "label": "benchmarks"}, {"value": "[[TOTAL_TASKS]]", "label": "tasks"},
                {"value": "2", "label": "action formats"}],
    "findings": [
        "PyRUA-Lean reaches a higher success rate than tool calling on every benchmark and solves [[POOLED_SR_REL]] more "
        "task instances overall ([[POOLED_SR_CODE]] against [[POOLED_SR_RPENT]]).",
        "On tasks both agents solve, tool calling consumes [[LIBERO_RATIO_PT]] the tokens of PyRUA-Lean on LIBERO-PRO, "
        "[[ROBOTWIN_RATIO_PT]] on RoboTwin 2.0, [[ROBOCASA_RATIO_PT]] on RoboCasa365 and [[COMPOSITE_RATIO_PT]] on its "
        "composite tasks; at GPT-6 Astra list prices, [[LIBERO_PRICE_PT]], [[ROBOTWIN_PRICE_PT]], [[ROBOCASA_PRICE_PT]] "
        "and [[COMPOSITE_PRICE_PT]].",
        "Tool calling stays the more expensive agent after removing the VLA policy, the shared guides or both "
        "from both agents. At list prices the saving all but vanishes where one VLA call does most of the work.",
    ],
    "limits": "Simulation only and zero-shot only: both agents run without memory. One tool-calling framework and one "
              "planner model, GPT-6 Astra.",
}


def update_project(values: dict[str, str]) -> bool:
    """Rewrite the pyrualean project card from PROJECT_CARD; True when the file changed."""
    projects = json.loads(PROJECTS.read_text())
    card = next(p for p in projects if p["slug"] == "pyrualean")
    filled = json.loads(fill(json.dumps(PROJECT_CARD, ensure_ascii=False), values, "PROJECT_CARD"))
    if all(card.get(k) == v for k, v in filled.items()):
        return False
    card.update(filled)
    PROJECTS.write_text(json.dumps(projects, indent=2, ensure_ascii=False) + "\n")
    return True


#: The post's title and subtitle in content/posts.json, filled from the same keys as the article.
POSTS = ROOT / "content" / "posts.json"
POST_CARD = {
    "title": "Fewer Tokens, Better Action: GPT-6 Astra Robot Agents with [[POOLED_SR_REL]] Higher Success but "
             "[[POOLED_TOKENS_FEWER]] Fewer Tokens",
    "subtitle": "Same model, same robot primitives, same budget. Acting in Python with PyRUA-Lean instead of through tool "
                "calls, GPT-6 Astra solves [[SR_REL_RANGE]] more tasks on every benchmark and uses "
                "[[TOKENS_SAVED_RANGE]] fewer tokens.",
}


def update_post(values: dict[str, str]) -> bool:
    """Rewrite the post's title and subtitle from POST_CARD; True when the file changed."""
    posts = json.loads(POSTS.read_text())
    post = next(p for p in posts if p["slug"] == "fewer-tokens-better-action")
    filled = json.loads(fill(json.dumps(POST_CARD, ensure_ascii=False), values, "POST_CARD"))
    if all(post.get(k) == v for k, v in filled.items()):
        return False
    post.update(filled)
    POSTS.write_text(json.dumps(posts, indent=2, ensure_ascii=False) + "\n")
    return True


# -- interactive charts -------------------------------------------------------------------------
# Figures 2-5 are drawn in the browser by assets/pyrualean/charts.js from the JSON each figure
# carries. The builders below emit that JSON, the legend and the metric switches. The site is light only, and so are the charts.

SHAPE = {"libero": "circle", "robotwin": "square", "robocasa": "triangle", "composite": "diamond"}
#: The switch ablations run on a subset of each benchmark (named by its tasks; seeds and cell counts stay
#: out of the post and are in the HTML comment under the setup section).
SUBSET = {"libero": "12 tasks", "robotwin": "12 tasks", "robocasa": "18 tasks"}
#: Where each benchmark's direct label sits in Figures 3 and 5.
EPISODE_LABEL_SIDE = {"libero": "above", "robotwin": "below", "robocasa": "right", "composite": "under"}
EPISODE_LABEL_SIDE_NARROW = {}
#: Figure 3 labels whose name needs two lines to stay clear of the arrows.
EPISODE_TITLE_LINES = {"composite": ["RoboCasa365", "composite"]}
DECOMP_LABEL_SIDE = {"libero": "above", "robotwin": "left", "robocasa": "right", "composite": "right"}
METRICS = [
    {"key": "prompt", "axis": "Token consumption, RPent ÷ PyRUA-Lean", "short": "Tokens, RPent ÷ code",
     "what": "token consumption, RPent ÷ PyRUA-Lean", "button": "Tokens"},
    {"key": "price", "axis": "List price (GPT-6 Astra), RPent ÷ PyRUA-Lean", "short": "List price, RPent ÷ code",
     "what": "list price, RPent ÷ PyRUA-Lean", "button": "List price"},
]
CHART_ASSETS = ('<link rel="stylesheet" href="/assets/pyrualean/charts.css">'
                '<script src="/assets/pyrualean/charts.js" defer></script>')


def key_shape(shape: str, filled: bool = True) -> str:
    fill, stroke = ("#242923", "none") if filled else ("#fbfaf6", "#8e9387")
    if shape == "square":
        body = f'<rect x="2" y="2" width="10" height="10" rx="1.5" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
    elif shape == "triangle":
        body = (f'<path d="M7,1.5 L12.5,11.5 L1.5,11.5 Z" fill="{fill}" stroke="{stroke}" stroke-width="1.5" '
                'stroke-linejoin="round"/>')
    elif shape == "diamond":
        body = (f'<path d="M7,1 L13,7 L7,13 L1,7 Z" fill="{fill}" stroke="{stroke}" stroke-width="1.5" '
                'stroke-linejoin="round"/>')
    else:
        body = f'<circle cx="7" cy="7" r="5" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
    return f'<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">{body}</svg>'


def key_line(color: str) -> str:
    return (f'<svg width="18" height="10" viewBox="0 0 18 10" aria-hidden="true"><line x1="1" y1="5" x2="17" y2="5" '
            f'stroke="{color}" stroke-width="2.5" stroke-linecap="round"/></svg>')


def point_legend() -> str:
    return "".join(f'<span class="pa-key">{key_shape(SHAPE[k])}{html.escape(n)}</span>' for k, n, _ in BENCHMARKS)


def chart(spec: dict, legend: str = "", modes: list[tuple[str, str]] | None = None) -> str:
    """The inside of a chart figure: legend, switches, plot and the JSON spec."""
    controls = ""
    if modes:
        buttons = "".join(
            f'<button type="button" data-mode="{k}" aria-pressed="{str(i == 0).lower()}">{html.escape(t)}</button>'
            for i, (k, t) in enumerate(modes))
        controls = f'<div class="pa-controls" role="group" aria-label="Shown as">{buttons}</div>'
    spec = dict(spec, mode=modes[0][0] if modes else None)
    data = json.dumps(spec, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (f'<div class="pa-card"><div class="pa-head"><div class="pa-legend">{legend}</div>{controls}</div>'
            '<div class="pa-plot"><p class="pa-noscript">This chart is drawn with JavaScript.</p></div>'
            f'</div><script type="application/json" class="pa-spec">{data}</script>')


def log_range(values, pad: float = 1.15) -> tuple[float, float]:
    return min(values) / pad, max(values) * pad


def ticks_in(lo: float, hi: float, candidates=(0.25, 0.5, 1, 2, 4, 8, 16)) -> list[float]:
    return [t for t in candidates if lo <= t <= hi]


def chart_episode(rows) -> str:
    """Figure 3: a solved episode on each benchmark, both arms: model requests against prompt
    tokens (or dollars at list price), means over the cells both arms solved."""
    panels = [{
        "key": key, "title": name, "shape": SHAPE[key], "labelSide": EPISODE_LABEL_SIDE.get(key, "right"),
        "labelSideNarrow": EPISODE_LABEL_SIDE_NARROW.get(key), "titleLines": EPISODE_TITLE_LINES.get(key),
        "req": {arm: round(s["req"][arm], 2) for arm in ARMS},
        "y": {"tokens": {arm: round(s["mean_input"][arm]) for arm in ARMS},
              "usd": {arm: round(s["usd"][arm], 3) for arm in ARMS}},
        "factor": {"tokens": round(s["ratio"], 3), "usd": round(s["price"], 3)},
        "reqFactor": round(s["req_ratio"], 3),
    } for key, name, s in rows if "ratio" in s]
    spec = {
        "type": "episode", "title": "LLM calls and token consumption of a solved episode, both agents, on each benchmark",
        "xLabel": "Number of LLM calls per solved episode", "xShort": "LLM calls per solved episode",
        "metrics": [
            {"key": "tokens", "axis": "Token consumption per solved episode (prompt tokens)", "short": "Token consumption",
             "fmt": "tok", "what": "fewer tokens", "whatShort": "fewer"},
            {"key": "usd", "axis": "Dollars per solved episode, GPT-6 Astra list price", "short": "Dollars, list price",
             "fmt": "usd", "what": "cheaper", "whatShort": "cheaper"},
        ],
        "panels": panels,
    }
    legend = (f'<span class="pa-key">{key_dot(TOOL_COLOR)}RPent · tool calling</span>'
              f'<span class="pa-key">{key_dot(CODE_COLOR)}PyRUA-Lean · code</span>'
              '<span class="pa-key pa-key-long"><svg width="26" height="10" viewBox="0 0 26 10" aria-hidden="true">'
              '<line x1="24" y1="5" x2="6" y2="5" stroke="#4d5249" stroke-width="1.6" stroke-dasharray="4 3"/>'
              '<path d="M1,5 L7,1.8 L7,8.2 Z" fill="#4d5249"/></svg>same task instances, tool calling → PyRUA-Lean</span>'
              '<span class="pa-legend-break" aria-hidden="true"></span>'
              + "".join(f'<span class="pa-key">{key_shape(p["shape"])}{html.escape(p["title"])}</span>' for p in panels))
    return chart(spec, legend, [("tokens", "Token consumption"), ("usd", "Dollars")])


def pchip(xs: list[float], ys: list[float], q: float) -> float:
    """Monotone cubic (Fritsch-Carlson) interpolation of increasing knots at q."""
    n = len(xs)
    if q <= xs[0]:
        return ys[0]
    if q >= xs[-1]:
        return ys[-1]
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [d[0]] + [0.0] * (n - 2) + [d[-1]]
    for i in range(1, n - 1):
        if d[i - 1] > 0 and d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    i = bisect.bisect_right(xs, q) - 1
    s = (q - xs[i]) / h[i]
    h00, h10, h01, h11 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s, -2 * s**3 + 3 * s**2, s**3 - s**2
    return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]


def smooth_curve(pairs: list[dict], arm: str, field: str, grid: list[float], spacing: float = 0.0,
                 keep: tuple = ()) -> list[float]:
    """Share of cells solved within each budget of the grid, as a smooth monotone curve through
    exact points (budget, cells solved within it) on a log budget axis, flat before the first success
    and after the last. With `spacing` (natural-log units) only points at least that far apart are
    kept, so a run of small steps becomes one slope; the first and last successes and the budgets in
    `keep` are always kept, so the curve is exact there."""
    budgets = solved_budgets(pairs, arm, field)
    if not budgets:
        return [0.0 for _ in grid]
    n = len(pairs)
    corners = []  # (log budget, share solved within it) at every distinct budget
    for j, b in enumerate(budgets):
        if j + 1 < len(budgets) and budgets[j + 1] == b:
            continue
        corners.append((math.log(b), (j + 1) / n))
    must = {math.log(b) for b in keep if b} | {corners[0][0], corners[-1][0]}
    knots = [(corners[0][0] - 0.12, 0.0)]
    for lx, share in corners:
        # a real jump (4 points or more since the last kept point) is kept, so it stays sharp
        if lx in must or lx - knots[-1][0] >= spacing or share - knots[-1][1] >= 0.04:
            knots.append((lx, share))
    xs, ys = [k[0] for k in knots], [k[1] for k in knots]
    return [round(100 * pchip(xs, ys, math.log(g)), 3) for g in grid]


def log_grid(lo: float, hi: float, n: int) -> list[int]:
    return sorted({round(lo * (hi / lo) ** (i / (n - 1))) for i in range(n)})


def token_grid(rows, n: int = 360) -> list[int]:
    top = max(v for _, _, s in rows for arm in ARMS for v in solved_budgets(s["pairs"], arm, "to_success"))
    return log_grid(15_000, top * 2.2, n)


def token_fit(s: dict, arm: str, grid: list[int]) -> list[float]:
    r = s["reach"]["to_success"]
    return smooth_curve(s["pairs"], arm, "to_success", grid, 0.15, r and [r[arm]])


def fit_gap(rows) -> float:
    """Largest distance, in points, between Figure 4's token-budget fit and the exact counts."""
    grid = token_grid(rows)
    return max(abs(f - 100 * c / s["n"]) for _, _, s in rows for arm in ARMS
               for f, c in zip(token_fit(s, arm, grid), budget_curve(s["pairs"], "to_success", grid)[arm]))


def chart_curves(rows) -> str:
    """Figure 4: cells solved within a budget, with the budget each arm needs to reach tool calling's final
    success. Tokens on a log axis long enough for both curves to level off; LLM calls on a log axis that ends at
    each benchmark's own call budget (40, or 100 on the composite tasks), past which no episode counts."""
    top_tok = max(v for _, _, s in rows for arm in ARMS for v in solved_budgets(s["pairs"], arm, "to_success"))
    tok_grid = log_grid(15_000, top_tok * 2.2, 320)
    req_max = max(100 if key in BUDGET_100 else 40 for key, _, _ in rows)
    req_grid = list(range(1, req_max + 1))  # a panel reads the prefix up to its budget
    tok_fine = token_grid(rows)
    panels = []
    for key, name, s in rows:
        budget = 100 if key in BUDGET_100 else 40
        fine = {"tokens": tok_fine, "requests": [round(math.exp(math.log(budget) * i / 359), 4) for i in range(360)]}
        reach_ = {}
        for mode, field in (("tokens", "to_success"), ("requests", "success_request")):
            r = s["reach"][field]
            if r:
                reach_[mode] = {"level": round(100 * r["level"] / s["n"], 2), "rpent": r["rpent"], "cells": r["cells"],
                                "ratio": round(r["ratio"], 3)}
        panels.append({
            "title": name, "n": s["n"], "reach": reach_, "budget": budget,
            "final": {arm: round(100 * s["succ"][arm] / s["n"], 2) for arm in ARMS},
            "y": {"tokens": budget_curve(s["pairs"], "to_success", tok_grid),
                  "requests": budget_curve(s["pairs"], "success_request", req_grid)},
            "fine": {"requests": fine["requests"]},
            "smooth": {mode: {arm: smooth_curve(s["pairs"], arm, field, fine[mode], spacing,
                                                (s["reach"][field] or {}).get(arm) and [s["reach"][field][arm]])
                              for arm in ARMS}
                       for mode, field, spacing in (("tokens", "to_success", 0.15), ("requests", "success_request", 0.0))},
        })
    spec = {
        "type": "curves", "title": "Success rate within a budget of tokens or LLM calls per episode",
        "series": [{"key": "cells", "label": "PyRUA-Lean · code", "color": CODE_COLOR},
                   {"key": "rpent", "label": "RPent · tool calls", "color": TOOL_COLOR}],
        "modes": [
            {"key": "tokens", "xLabel": "Token consumption up to the successful LLM call (prompt tokens, log scale)",
             "short": "Token consumption (log scale)", "fmt": "tok", "scale": "log", "x": tok_grid,
             "min": tok_grid[0], "max": tok_grid[-1], "fine": tok_fine,
             "ticks": [30_000, 100_000, 300_000, 1_000_000, 3_000_000, 10_000_000], "what": "fewer tokens"},
            # each panel's axis ends at its own budget (panel["budget"]) and draws its own fine grid (panel["fine"])
            {"key": "requests", "xLabel": "Number of LLM calls up to the successful one (log scale)",
             "short": "Number of LLM calls (log scale)", "fmt": "int", "scale": "log", "x": req_grid,
             "min": 1, "max": req_max, "ticks": [1, 2, 5, 10, 20, 40, 100], "budget": True,
             "what": "fewer LLM calls"},
        ],
        "panels": panels,
    }
    legend = "".join(f'<span class="pa-key">{key_line(color)}{html.escape(text)}</span>'
                     for color, text in ((CODE_COLOR, "PyRUA-Lean · code"), (TOOL_COLOR, "RPent · tool calls")))
    legend += ('<span class="pa-key"><svg width="26" height="10" viewBox="0 0 26 10" aria-hidden="true">'
               '<line x1="24" y1="5" x2="6" y2="5" stroke="#4d5249" stroke-width="1.6" stroke-dasharray="4 3"/>'
               '<path d="M1,5 L7,1.8 L7,8.2 Z" fill="#4d5249"/></svg>budget to reach tool calling\'s final SR</span>')
    return chart(spec, legend, [("tokens", "Token budget"), ("requests", "LLM-call budget")])


def chart_decomposition(rows) -> str:
    """Figure 5: equation (2) on each benchmark, the calls factor against the per-call factor (log-log;
    their product, the token factor, is constant along each diagonal)."""
    points = []
    for key, name, s in rows:
        if "ratio" not in s:
            continue
        per_call = {arm: s["mean_input"][arm] / s["req"][arm] for arm in ARMS}
        points.append({
            "id": key, "shape": SHAPE[key], "title": name, "label": name,
            "labelSide": DECOMP_LABEL_SIDE.get(key, "right"),
            "x": round(s["req_ratio"], 4), "y": round(s["tpr_ratio"], 4), "total": round(s["ratio"], 4),
            "rows": [["Fewer LLM calls", f"{s['req']['rpent']:.1f} → {s['req']['cells']:.1f} per episode"],
                     ["Smaller calls", f"{tokens(per_call['rpent'])} → {tokens(per_call['cells'])} tokens per call"]],
        })
    spec = {
        "type": "decomp", "title": "The token factor split into fewer LLM calls and smaller calls",
        "domain": [0.45, 4.5], "ticks": [0.5, 1, 2, 4], "totals": [0.5, 1, 2, 4, 8],
        "xLabel": "Fewer LLM calls: calls per episode, RPent ÷ PyRUA-Lean", "xShort": "Fewer LLM calls →",
        "yLabel": "Smaller calls: tokens per LLM call, RPent ÷ PyRUA-Lean", "yShort": "↑ Smaller calls",
        "points": points,
    }
    legend = point_legend() + (
        '<span class="pa-key"><svg width="16" height="14" viewBox="0 0 16 14" aria-hidden="true"><line x1="1.5" y1="12.5" '
        'x2="14.5" y2="1.5" stroke="#8e9387" stroke-width="1.3"/></svg>equal token factor (calls × per call)</span>')
    return chart(spec, legend)


def chart_ablation(groups) -> str:
    out, values = [], []
    for family, name, settings in groups:
        rows_ = []
        for i, (setting, _, s) in enumerate(settings):
            if "ratio" not in s:
                continue
            values += [s["ratio"], s["price"]]
            rows_.append({
                "setting": setting, "baseline": i == 0,
                "values": {"prompt": round(s["ratio"], 3), "price": round(s["price"], 3)},
                "rows": [["SR, RPent / code", f"{pct(s['succ']['rpent'] / s['n'])} / {pct(s['succ']['cells'] / s['n'])}"],
                         ["LLM calls per solved episode", f"RPent {s['req']['rpent']:.0f} · code {s['req']['cells']:.0f}"]],
            })
        out.append({"title": f"{name} · {SUBSET[family]}", "rows": rows_})
    lo, hi = log_range(values + [1])
    spec = {"type": "forest", "title": "Token-consumption ratio in every ablation setting",
            "domain": [round(lo, 3), round(hi, 3)], "ticks": ticks_in(lo, hi),
            "metrics": [{k: m[k] for k in ("key", "axis", "short", "what")} for m in METRICS], "groups": out}
    legend = (f'<span class="pa-key">{key_dot(CODE_COLOR)}the ratio, RPent ÷ PyRUA-Lean: right of 1×, '
              'PyRUA-Lean consumes fewer tokens</span>'
              '<span class="pa-key">Bold: the main comparison on the same task instances</span>')
    return chart(spec, legend, [(m["key"], m["button"]) for m in METRICS])


def key_dot(color: str) -> str:
    return (f'<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="5" '
            f'fill="{color}"/></svg>')


def chart_rates(rows) -> str:
    """RQ1: the success rate of both arms on each benchmark, and the difference in points."""
    items = []
    for key, name, s in rows:
        n = s["n"]
        items.append({
            "name": name, "sub": f"{s['tasks']} tasks", "n": n,
            "rpent": {"solved": s["succ"]["rpent"], "rate": round(100 * s["succ"]["rpent"] / n, 1)},
            "cells": {"solved": s["succ"]["cells"], "rate": round(100 * s["succ"]["cells"] / n, 1)},
        })
    spec = {"type": "success", "title": "Success rate (SR) of both agents on each benchmark", "rows": items}

    def key_pill(style: str) -> str:
        return (f'<svg width="24" height="12" viewBox="0 0 24 12" aria-hidden="true"><rect x="0.5" y="0.5" width="23" '
                f'height="11" rx="5.5" style="{style}"/></svg>')

    legend = "".join(f'<span class="pa-key">{key_dot(c)}{html.escape(t)}</span>'
                     for c, t in ((TOOL_COLOR, "RPent · tool calling"), (CODE_COLOR, "PyRUA-Lean · code")))
    legend += f'<span class="pa-key">{key_pill("fill: var(--pa-code-wash-strong)")}PyRUA-Lean − RPent, in points</span>'
    return chart(spec, legend)


DEMO = ROOT / "content" / "pyrualean-demo.json"
#: Appendix A: per benchmark, the task instances both agents solved whose token ratio (tool calling's prompt
#: tokens over PyRUA-Lean's, whole episodes) is closest to the benchmark's median, at most one per task (the page
#: names tasks, not seeds) and none of Figure 1's task. content/pyrualean-appendix.json lists them; each one's
#: replay data and frames are in assets/pyrualean/appendix/<slug>/, extracted from the two run directories. The
#: selection is redone here from the snapshot and must match the list, and every replay must agree with its pair.
APPENDIX = ROOT / "content" / "pyrualean-appendix.json"
APPENDIX_ASSETS = "/assets/pyrualean/appendix"
FIGURE_1_CELL = ["spatial_swap", 7, 2]  # the task instance content/pyrualean-demo.json replays


def replay_spec(demo: dict, assets: str, title: str) -> dict:
    spec = {"type": "replay", "title": title, "assets": assets, "task": demo["task"], "cell": demo["cell"],
            "rpent": demo["rpent"], "cells": demo["cells"]}
    if demo.get("cameras"):  # Figure 1's LIBERO episode uses the replay's defaults
        spec["cameras"] = demo["cameras"]
    return spec


def task_legend(demo: dict) -> str:
    return f'<span class="pa-key pa-task"><b>Task</b>&nbsp;“{html.escape(demo["task"])}”</span>'


def chart_replay() -> str:
    """Figure 1: one paired LIBERO-PRO episode, request by request (content/pyrualean-demo.json,
    extracted from the two run directories)."""
    demo = json.loads(DEMO.read_text())
    return chart(replay_spec(demo, "/assets/pyrualean/demo", "One real episode with both agents"), task_legend(demo))


def task_label(cell: list, instruction: str) -> str:
    """How the picker names a task: RoboTwin's and RoboCasa's own task names; LIBERO-PRO's numbered tasks by
    their instruction."""
    task = cell[1]
    return instruction.rstrip(".") if isinstance(task, int) else task


def token_ratio(p: dict) -> float:
    return p["rpent"]["input"] / p["cells"]["input"]


def selected(index: dict, per: int) -> list[tuple[list, list]]:
    """Per benchmark, the `per` task instances both agents solved closest to its median token ratio, at most one
    per task and none of Figure 1's task (ties by cell), as (block prefixes, cell)."""
    picks = []
    for _, _, prefix_lists in BENCHMARKS:
        both = [(prefixes, p) for prefixes in prefix_lists
                for p in (index.get(("main", tuple(prefixes))) or {}).get("pairs", [])
                if all(p[arm]["success"] and p[arm]["input"] for arm in ARMS)]
        mid = st.median(token_ratio(p) for _, p in both)
        tasks: set = {tuple(FIGURE_1_CELL[:2])}
        for prefixes, p in sorted(both, key=lambda q: (abs(token_ratio(q[1]) - mid), str(q[1]["cell"]))):
            if tuple(p["cell"][:2]) not in tasks and len(tasks) <= per:
                tasks.add(tuple(p["cell"][:2]))
                picks.append((prefixes, p["cell"]))
    return picks


def appendix() -> str:
    """Appendix A: selected episodes both agents solved in one figure, replayed one at a time (empty without the
    list)."""
    if not APPENDIX.exists():
        return ""
    manifest = json.loads(APPENDIX.read_text())
    index = load()
    per = manifest["per_benchmark"]
    if selected(index, per) != [(e["prefixes"], e["cell"]) for e in manifest["episodes"]]:
        raise SystemExit("Appendix A: content/pyrualean-appendix.json is not the selection the snapshot gives")
    episodes = []
    for e in manifest["episodes"]:
        block = index.get(("main", tuple(e["prefixes"])))
        pair = next((p for p in (block or {}).get("pairs", []) if p["cell"] == e["cell"]), None)
        demo_path = ROOT / APPENDIX_ASSETS.lstrip("/") / e["slug"] / "demo.json"
        if pair is None or not demo_path.exists():
            raise SystemExit(f"Appendix A: {e['slug']} has no pair in the snapshot or no replay data")
        demo = json.loads(demo_path.read_text())
        for arm in ARMS:  # the replay must be the very episode the snapshot counts
            reqs = demo[arm]["requests"]
            if (len(reqs), bool(demo[arm]["solved_at"]), reqs[-1]["cum"]) != \
                    (pair[arm]["decisions"], pair[arm]["success"], pair[arm]["input"]):
                raise SystemExit(f"Appendix A: the {arm} replay of {e['slug']} does not match the snapshot")
        episodes.append({"slug": e["slug"], "benchmark": e["benchmark"], "task": task_label(e["cell"], demo["task"])})
    if not episodes:
        return ""
    for b in {e["benchmark"] for e in episodes}:  # the picker tells a benchmark's tasks apart by name alone
        names = [e["task"] for e in episodes if e["benchmark"] == b]
        if len(set(names)) != len(names):
            raise SystemExit(f"Appendix A: two {b} tasks share a name")
    count = {3: "three", 4: "four", 5: "five", 6: "six"}
    spec = {"type": "gallery", "title": "More episodes both agents solved", "assets": APPENDIX_ASSETS,
            "episodes": episodes}
    intro = (f"<p>Figure 1 replays a single episode; Figure A1 replays more, {count.get(per, per)} tasks per "
             "benchmark that both agents solved. Pick a benchmark and a task to replay both agents LLM call by LLM "
             "call, as in Figure 1.</p>")
    caption = "<strong>Figure A1.</strong> More episodes that both agents solved, replayed as in Figure 1."
    return ('<h2 id="appendix">Appendix A. More episodes</h2>\n' + intro + "\n"
            f'<figure class="article-figure pa-chart" id="figure-a1">{chart(spec)}<figcaption>{caption}</figcaption></figure>')


#: The request of the Figure 1 episode whose cell the text shows in full (Section 6).
CODE_REQUEST = 5
PY_TOKEN = re.compile(
    r"(?P<comment>#.*$)|(?P<string>[rbfRBF]?'(?:[^'\\]|\\.)*'|[rbfRBF]?\"(?:[^\"\\]|\\.)*\")"
    r"|(?P<robo>\brobo\.[A-Za-z_]\w*)"
    r"|(?P<keyword>\b(?:and|as|assert|break|continue|def|elif|else|except|False|for|from|if|import|in|is|"
    r"lambda|None|not|or|pass|return|True|try|while|with)\b)"
    r"|(?P<number>\b\d+(?:\.\d+)?\b)")


def highlight(line: str) -> str:
    """One line of Python as escaped HTML, with robo.* calls, keywords, strings and numbers marked."""
    out, at = [], 0
    for m in PY_TOKEN.finditer(line):
        out.append(html.escape(line[at:m.start()]))
        out.append(f'<span class="pa-tk-{m.lastgroup}">{html.escape(m.group(0))}</span>')
        at = m.end()
    out.append(html.escape(line[at:]))
    return "".join(out)


def code_example() -> str:
    """The cell of one Figure 1 request exactly as the model wrote it, and what came back to it."""
    demo = json.loads(DEMO.read_text())
    reqs = demo["cells"]["requests"]
    r = next(q for q in reqs if q["k"] == CODE_REQUEST)
    # one block per line: long lines wrap with a hanging indent instead of running off the page
    lines = "".join(
        f'<span class="pa-ln" style="--i:{len(line) - len(line.lstrip(" "))}">{highlight(line) or " "}</span>'
        for line in r["code"].split("\n"))
    shown = r.get("shown") or ["agentview"]
    pictures = "".join(
        f'<img src="/assets/pyrualean/demo/{r["view"][cam]}" alt="the {cam.replace("agentview", "agent view")} '
        f'image the cell asked for" loading="lazy">' for cam in shown if r["view"].get(cam))
    n_img = len(shown)
    back = (f"What came back: the text it printed and the {'picture' if n_img == 1 else f'{n_img} pictures'} "
            "it asked for, nothing else")
    return (
        f'<figure class="article-figure pa-codefig" id="code-request-{CODE_REQUEST}"><div class="pa-codecard">'
        f'<div class="pa-codehead"><span class="pa-codedot"></span><b>PyRUA-Lean</b><span>LLM call {r["k"]} of '
        f'{len(reqs)} · one <code>python(code)</code> cell, {r["calls"]} primitive calls</span></div>'
        f'<pre class="pa-src"><code>{lines}</code></pre>'
        f'<div class="pa-codeback"><div class="pa-codeback-label">{back}</div>'
        f'<div class="pa-codeback-row"><pre class="pa-out">{html.escape(r["stdout"].rstrip())}</pre>'
        f'<div class="pa-codeback-pics">{pictures}</div></div></div></div></figure>')


COVER = ROOT / "assets" / "pyrualean" / "cover-tokens.svg"
#: Where each benchmark's label sits on the cover, from its tool-calling point: text anchor, dx, dy of the
#: first line ("edge" anchors the lines at the plot's right edge), and the name split into lines.
COVER_LABELS = {
    "libero": ("end", 18, -80, ["LIBERO-PRO"]),
    "robotwin": ("start", 26, 40, ["RoboTwin 2.0"]),
    "robocasa": ("start", 26, 40, ["RoboCasa365 atomic"]),
    "composite": ("edge", 0, 66, ["RoboCasa365", "composite"]),
}


def cover_svg(rows) -> str:
    """The post's card image: Figure 3 at a glance, drawn from the same numbers. LLM calls against
    token consumption of a solved episode on each benchmark, both on log scales, with an arrow from
    tool calling to PyRUA-Lean and the factor beside it."""
    w, h = 1200, 630
    m = {"l": 138, "r": 56, "t": 96, "b": 84}
    ps = [(key, name, s) for key, name, s in rows if "ratio" in s]
    reqs = [s["req"][a] for _, _, s in ps for a in ARMS]
    vals = [s["mean_input"][a] for _, _, s in ps for a in ARMS]
    xlo, xhi = min(reqs) / 1.3, max(reqs) * 1.22
    ylo, yhi = min(vals) / 1.45, max(vals) * 1.55

    def sx(v: float) -> float:
        return m["l"] + (math.log(v / xlo)) / math.log(xhi / xlo) * (w - m["l"] - m["r"])

    def sy(v: float) -> float:
        return h - m["b"] - (math.log(v / ylo)) / math.log(yhi / ylo) * (h - m["t"] - m["b"])

    def shape(kind: str, x: float, y: float, fill: str, r: float = 13) -> str:
        edge = f'fill="{fill}" stroke="#e7eae1" stroke-width="3" stroke-linejoin="round"'
        if kind == "square":
            return f'<rect x="{x - r * 0.9:.1f}" y="{y - r * 0.9:.1f}" width="{r * 1.8:.1f}" height="{r * 1.8:.1f}" rx="2" {edge}/>'
        if kind == "triangle":
            k = r * 1.15
            return f'<path d="M{x:.1f},{y - k:.1f} L{x + k:.1f},{y + k * 0.8:.1f} L{x - k:.1f},{y + k * 0.8:.1f} Z" {edge}/>'
        if kind == "diamond":
            k = r * 1.25
            return f'<path d="M{x:.1f},{y - k:.1f} L{x + k:.1f},{y:.1f} L{x:.1f},{y + k:.1f} L{x - k:.1f},{y:.1f} Z" {edge}/>'
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" {edge}/>'

    def arrow(x1: float, y1: float, x2: float, y2: float, gap: float = 20) -> str:
        dx, dy = x2 - x1, y2 - y1
        n = math.hypot(dx, dy) or 1
        ux, uy = dx / n, dy / n
        sx_, sy_, ex, ey = x1 + ux * gap, y1 + uy * gap, x2 - ux * gap, y2 - uy * gap
        bx, by = ex - ux * 16, ey - uy * 16
        px, py = -uy * 8, ux * 8
        return (f'<line x1="{sx_:.1f}" y1="{sy_:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="#4d5249" stroke-width="3" '
                f'stroke-dasharray="10 8"/><path d="M{ex:.1f},{ey:.1f} L{bx + px:.1f},{by + py:.1f} '
                f'L{bx - px:.1f},{by - py:.1f} Z" fill="#4d5249"/>')

    def text(x: float, y: float, s: str, size: int, fill: str, anchor: str = "start", weight: int = 400) -> str:
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
                f'text-anchor="{anchor}" stroke="#e7eae1" stroke-width="7" stroke-linejoin="round" '
                f'paint-order="stroke">{html.escape(s)}</text>')

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
           'aria-labelledby="cover-title cover-desc" font-family="Arial, Helvetica, sans-serif">',
           '<title id="cover-title">Fewer LLM calls and fewer tokens with code actions</title>',
           '<desc id="cover-desc">' + html.escape(
               "LLM calls against token consumption of a solved episode on four benchmarks. On each, an arrow runs "
               "from tool calling to PyRUA-Lean: " + "; ".join(
                   f"{name} {times(s['ratio'])} fewer tokens" for _, name, s in ps) + ".") + '</desc>',
           f'<rect width="{w}" height="{h}" fill="#e7eae1"/>']
    for t in (1e5, 2e5, 5e5, 1e6, 2e6):
        if ylo <= t <= yhi:
            out.append(f'<line x1="{m["l"]}" x2="{w - m["r"]}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" stroke="#d3d8ca" stroke-width="2"/>')
            out.append(text(m["l"] - 16, sy(t) + 7, tokens(t).replace(".00M", "M"), 20, "#656a61", "end"))
    base = h - m["b"]
    out.append(f'<line x1="{m["l"]}" x2="{w - m["r"]}" y1="{base}" y2="{base}" stroke="#a7ad9f" stroke-width="2"/>')
    for t in (5, 10, 20, 30):
        if xlo <= t <= xhi:
            out.append(text(sx(t), base + 30, str(t), 20, "#656a61", "middle"))
    out.append(text(w - m["r"], base + 62, "LLM calls per solved episode (log scale) →", 21, "#656a61", "end"))
    out.append(text(m["l"] - 16, m["t"] - 40, "↑ Token consumption per solved episode (log scale)", 21, "#656a61"))
    # the legend, bottom left, laid out left to right (Arial at 22 px is about 12 px a character)
    lx, ly = m["l"] + 10, base + 64
    for colour, name in ((TOOL_COLOR, "RPent · tool calling"), (CODE_COLOR, "PyRUA-Lean · code")):
        out.append(f'<circle cx="{lx:.1f}" cy="{ly - 7:.1f}" r="10" fill="{colour}"/>')
        out.append(text(lx + 20, ly, name, 22, "#242923", "start", 600))
        lx += 20 + 12.5 * len(name) + 36
    geo = [(key, name, s, sx(s["req"]["rpent"]), sy(s["mean_input"]["rpent"]), sx(s["req"]["cells"]),
            sy(s["mean_input"]["cells"])) for key, name, s in ps]
    out += [arrow(rx, ry, cx, cy) for _, _, _, rx, ry, cx, cy in geo]
    for key, _, _, rx, ry, cx, cy in geo:
        out += [shape(SHAPE[key], rx, ry, TOOL_COLOR), shape(SHAPE[key], cx, cy, CODE_COLOR)]
    for key, name, s, rx, ry, _, _ in geo:
        anchor, dx, dy, lines = COVER_LABELS.get(key, ("start", 26, 0, [name]))
        x = w - m["r"] if anchor == "edge" else rx + dx
        a = "end" if anchor in ("end", "edge") else "start"
        y = ry + dy
        for line in lines:
            out.append(text(x, y, line, 26, "#242923", a, 700))
            y += 32
        out.append(text(x, y + 4, f"{times(s['ratio'])} fewer tokens", 30, "#9a4b24", a, 700))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def charts(rows, groups) -> dict[str, str]:
    return {"CHART_ASSETS": CHART_ASSETS, "CODE_EXAMPLE": code_example(),
            "CHART_REPLAY": chart_replay(), "APPENDIX": appendix(), "CHART_RATES": chart_rates(rows),
            "CHART_EPISODE": chart_episode(rows), "CHART_CURVES": chart_curves(rows),
            "CHART_DECOMPOSITION": chart_decomposition(rows), "CHART_ABLATION": chart_ablation(groups)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trim-snapshot", action="store_true",
                    help="first drop the snapshot blocks the post does not use (run once after replacing it)")
    args = ap.parse_args()
    if args.trim_snapshot:
        print(f"trimmed {trim_snapshot()} unused blocks from {SNAPSHOT.relative_to(ROOT)}")
    index = load()
    rows, groups = main_rows(index), ablation_rows(index)
    ARTICLE.write_text(render(rows, groups))
    print(f"wrote {ARTICLE.relative_to(ROOT)}")
    COVER.write_text(cover_svg(rows))
    print(f"wrote {COVER.relative_to(ROOT)}")
    if update_post(keys(rows, groups)):
        print(f"wrote {POSTS.relative_to(ROOT)} (title and subtitle)")
    if update_project(keys(rows, groups)):
        print(f"wrote {PROJECTS.relative_to(ROOT)} (pyrualean card)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
