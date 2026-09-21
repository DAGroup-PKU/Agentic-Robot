"""Regenerate the blog radar from saved results; requires matplotlib only for editing."""
import json
import math
import os
from pathlib import Path
from statistics import mean

os.environ.setdefault("MPLCONFIGDIR", "/tmp/agent-robot-radar-mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
comparison = json.loads((ROOT / "content/robodojo-results.json").read_text())
reference = json.loads((ROOT / "content/pi05-reference.json").read_text())
categories = comparison["categories"]
pi = {task["task"]: task["success_rate"] for task in reference["tasks"]}
members = [task for category in categories for task in category["members"]]
assert len(members) == len(set(members)) == 18
assert set(members) == set(pi)
angles = [i * math.tau / len(categories) for i in range(len(categories))]
closed_angles = angles + angles[:1]
plt.rcParams.update({"svg.fonttype": "none", "svg.hashsalt": "agent-robot-radar"})
fig = plt.figure(figsize=(10, 8.5), facecolor="none")
ax = fig.add_axes([.23, .20, .54, .64], projection="polar", facecolor="none")
ax.set_theta_offset(math.pi / 2)
ax.set_theta_direction(-1)
ax.set_ylim(0, 100)
ax.set_xticks(angles)
ax.set_xticklabels([])
ax.set_yticks([20, 40, 60, 80, 100])
ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], fontsize=9, color="#667060")
ax.set_rlabel_position(10)
ax.grid(color="#d3d8cd")
ax.spines["polar"].set_color("#d3d8cd")
labels = ["Block\nmanipulation", "Symbolic\ntasks", "Object\nhandling",
          "Cloth\nfolding", "Tools &\ninsertion", "Shape\nmanipulation"]
for angle, label in zip(angles, labels):
    alignment = "center" if abs(math.sin(angle)) < .01 else "left" if math.sin(angle) > 0 else "right"
    ax.text(angle, 111, label, ha=alignment, va="center", fontsize=12, color="#242923", clip_on=False)
series = [
    ("Astra", "#237569", "-", "o", [c["gpt"]["success_rate"] * 100 for c in categories]),
    ("Fable 5.1", "#c26a40", "--", "s", [c["fable"]["success_rate"] * 100 for c in categories]),
    ("π0.5 · official reference", "#6374a4", "-.", "^", [mean(pi[t] for t in c["members"]) * 100 for c in categories]),
]
for name, color, style, marker, values in series:
    ax.plot(closed_angles, values + values[:1], label=name, color=color,
            linestyle=style, linewidth=2.5, marker=marker, markersize=5)
    ax.fill(closed_angles, values + values[:1], color=color, alpha=.045)
fig.suptitle("Success rate across six task categories", y=.97, fontsize=18, color="#242923")
fig.legend(*ax.get_legend_handles_labels(), loc="lower center", bbox_to_anchor=(.5, .065),
           ncol=3, frameon=False, fontsize=11, columnspacing=1.6)
fig.text(.5, .045, "Same 18 task names · category means · separate evaluation protocols",
         ha="center", fontsize=10, color="#667060")
fig.text(.5, .020, "π0.5 source: RoboDojo leaderboard · data " + reference["leaderboard_data_version"],
         ha="center", fontsize=9, color="#667060", url=reference["source_url"])
output = ROOT / "assets/robodojo-category-radar.svg"
fig.savefig(output, transparent=True, metadata={"Date": None})
output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
plt.close(fig)
print("Updated radar:", output)
for category, value in zip(categories, series[-1][-1]):
    print(f"  π0.5 {category['label']}: {value:.3f}%")
