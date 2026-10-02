"""Train and evaluate the two Invigil models: device type and distance band.

Run from the repo root:
    python -m ml.train                      # all labeled sessions in data/raw
    python -m ml.train --data data/synthetic --name pipeline-check

How the accuracy is measured matters more than the model. Windows from the
same session are almost identical, so a random train/test split lets the model
see near-copies of the test rows and the score comes out far too high.
Instead, whole sessions are held out: the model is tested only on sessions it
never saw during training (grouped cross-validation).

Writes:
    docs/results/<date>-<name>/report.md      numbers for the portfolio
    docs/results/<date>-<name>/confusion_<target>.csv
    ml/models/<target>.joblib                  model trained on all sessions
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import GroupKFold

from ml.features import BANDS, BANNED, FEATURE_COLS, TYPES, dataset

TARGETS = {
    # target: (class order, design requirement it is checked against, pass mark)
    "type": (TYPES, "DR2 classification accuracy", 0.85),
    "band": (BANDS, "DR3 distance band accuracy", 0.80),
}
MAX_FOLDS = 5


def make_model() -> RandomForestClassifier:
    # A forest of shallow-ish trees. max_depth and min_samples_leaf stop each
    # tree from memorizing single windows (overfitting).
    return RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=0,
        n_jobs=-1,
    )


def folds(groups: pd.Series):
    """Grouped folds: every session lands in exactly one test fold."""
    n = min(MAX_FOLDS, groups.nunique())
    if n < 2:
        raise SystemExit("need at least 2 labeled sessions to test on unseen data")
    return list(GroupKFold(n_splits=n).split(np.zeros(len(groups)), groups=groups))


def evaluate(df: pd.DataFrame, target: str) -> dict:
    classes, _, _ = TARGETS[target]
    X = df[FEATURE_COLS].to_numpy(dtype=float)
    y = df[target].to_numpy()
    groups = df["session"]

    pred = np.empty(len(y), dtype=object)
    for train_idx, test_idx in folds(groups):
        assert not set(groups.iloc[train_idx]) & set(groups.iloc[test_idx])
        model = make_model().fit(X[train_idx], y[train_idx])
        pred[test_idx] = model.predict(X[test_idx])

    final = make_model().fit(X, y)
    labels = [c for c in classes if c in set(y) | set(pred)]
    result = {
        "target": target,
        "rows": len(y),
        "sessions": groups.nunique(),
        "train_acc": accuracy_score(y, final.predict(X)),
        "test_acc": accuracy_score(y, pred),
        "labels": labels,
        "confusion": confusion_matrix(y, pred, labels=labels),
        "report": classification_report(y, pred, labels=labels, zero_division=0),
        "importance": sorted(zip(FEATURE_COLS, final.feature_importances_), key=lambda p: -p[1]),
        "model": final,
    }
    if target == "type":
        # The mistake that matters most in a real hall: a banned device called allowed.
        banned = np.isin(y, BANNED)
        caught = np.isin(pred[banned], BANNED)
        result["banned_recall"] = float(caught.mean()) if banned.any() else float("nan")
    return result


def report_md(results: list[dict], data: Path) -> str:
    lines = [f"# Training run {date.today().isoformat()}", "", f"Data: `{data}`", ""]
    for r in results:
        _, req, mark = TARGETS[r["target"]]
        verdict = "PASS" if r["test_acc"] >= mark else "FAIL"
        lines += [
            f"## {r['target']}",
            "",
            f"- Rows: {r['rows']} windows from {r['sessions']} sessions",
            f"- Accuracy on unseen sessions: **{r['test_acc']:.1%}** ({req}, target {mark:.0%}: {verdict})",
            f"- Accuracy on training data: {r['train_acc']:.1%}",
            "  A big gap between these two means the model memorized the training sessions.",
        ]
        if "banned_recall" in r:
            lines.append(f"- Banned devices flagged as banned: {r['banned_recall']:.1%}")
        lines += ["", "Confusion matrix (rows: true, columns: predicted)", "", "```"]
        cm = pd.DataFrame(r["confusion"], index=r["labels"], columns=r["labels"])
        lines += [cm.to_string(), "```", "", "```", r["report"].rstrip(), "```", ""]
        lines += ["Top features", ""]
        lines += [f"- {name}: {imp:.3f}" for name, imp in r["importance"][:10]]
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train the Invigil models.")
    parser.add_argument("--data", type=Path, default=Path("data/raw"), help="folder of sessions")
    parser.add_argument("--target", choices=[*TARGETS, "both"], default="both")
    parser.add_argument("--name", default="train", help="name for the results folder")
    parser.add_argument("--results", type=Path, default=Path("docs/results"))
    parser.add_argument("--models", type=Path, default=Path("ml/models"))
    args = parser.parse_args(argv)

    df = dataset(args.data)
    if df.empty:
        raise SystemExit(f"no labeled windows found under {args.data}")
    targets = list(TARGETS) if args.target == "both" else [args.target]

    results = []
    for t in targets:
        r = evaluate(df, t)
        results.append(r)
        print(f"{t}: unseen sessions {r['test_acc']:.1%}, training data {r['train_acc']:.1%}")

    out = args.results / f"{date.today().isoformat()}-{args.name}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(report_md(results, args.data), encoding="utf-8")
    args.models.mkdir(parents=True, exist_ok=True)
    for r in results:
        cm = pd.DataFrame(r["confusion"], index=r["labels"], columns=r["labels"])
        cm.to_csv(out / f"confusion_{r['target']}.csv")
        joblib.dump(
            {"model": r["model"], "features": FEATURE_COLS, "classes": r["labels"]},
            args.models / f"{r['target']}.joblib",
        )
    print(f"report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
