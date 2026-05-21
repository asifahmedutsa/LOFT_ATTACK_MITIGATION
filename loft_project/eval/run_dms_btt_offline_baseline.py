import argparse
import json
import os

import pandas as pd
from sklearn.model_selection import train_test_split

from features.attack_detection import derive_state_label
from metrics.offline_metrics import binary_classification_metrics, three_class_state_metrics


def _load_catboost():
    try:
        from catboost import CatBoostClassifier  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "CatBoost is required for DMS-BTT offline baseline. "
            "Install with: python -m pip install catboost"
        ) from exc
    return CatBoostClassifier


def build_state_dataset(df: pd.DataFrame, flow_table_size: int) -> pd.DataFrame:
    required = {"FN", "APIT"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"State dataset missing columns: {sorted(missing)}")

    out = df[["FN", "APIT"]].copy()
    if "state_label" in df.columns:
        out["label"] = df["state_label"].astype(int)
    else:
        out["label"] = df["FN"].apply(lambda x: derive_state_label(int(x), flow_table_size))
    return out


def build_flow_dataset(df: pd.DataFrame) -> pd.DataFrame:
    required = {"Numb", "PIT", "Sizep", "label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Flow dataset missing columns: {sorted(missing)}")
    return df[["Numb", "PIT", "Sizep", "label"]].copy()


def train_eval_catboost(X_train, X_test, y_train, y_test, loss_function):
    CatBoostClassifier = _load_catboost()
    model = CatBoostClassifier(
        loss_function=loss_function,
        random_seed=42,
        verbose=False,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test).astype(int).ravel()
    return y_pred


def main():
    parser = argparse.ArgumentParser(description="Run DMS-BTT-style offline CatBoost baseline.")
    parser.add_argument("--state-csv", required=True, help="CSV with FN, APIT, and optional state_label.")
    parser.add_argument("--flow-csv", required=True, help="CSV with Numb, PIT, Sizep, label.")
    parser.add_argument(
        "--flow-table-size",
        type=int,
        default=3500,
        help="Flow table size used for deriving state labels when absent.",
    )
    parser.add_argument(
        "--output-dir",
        default="loft_project/results/dms_btt/offline",
        help="Output folder for metrics.",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    state_df = build_state_dataset(pd.read_csv(args.state_csv), args.flow_table_size)
    flow_df = build_flow_dataset(pd.read_csv(args.flow_csv))

    # 5:1 train/test split to mirror paper setup.
    test_size = 1 / 6

    Xs = state_df[["FN", "APIT"]]
    ys = state_df["label"]
    Xs_tr, Xs_te, ys_tr, ys_te = train_test_split(
        Xs, ys, test_size=test_size, random_state=42, stratify=ys
    )
    ys_pred = train_eval_catboost(Xs_tr, Xs_te, ys_tr, ys_te, loss_function="MultiClass")
    state_metrics = three_class_state_metrics(ys_te.tolist(), ys_pred.tolist())

    Xf = flow_df[["Numb", "PIT", "Sizep"]]
    yf = flow_df["label"]
    Xf_tr, Xf_te, yf_tr, yf_te = train_test_split(
        Xf, yf, test_size=test_size, random_state=42, stratify=yf
    )
    yf_pred = train_eval_catboost(Xf_tr, Xf_te, yf_tr, yf_te, loss_function="Logloss")
    flow_metrics = binary_classification_metrics(yf_te.tolist(), yf_pred.tolist())

    metrics = {
        "split": "5:1",
        "state_detection_metrics": state_metrics,
        "malicious_flow_metrics": flow_metrics,
    }
    out_path = os.path.join(args.output_dir, "dms_btt_offline_metrics.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    print("DMS-BTT offline baseline complete")
    print(json.dumps(metrics, indent=2))
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

