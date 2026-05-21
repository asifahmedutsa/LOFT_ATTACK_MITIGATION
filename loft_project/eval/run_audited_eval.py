import argparse
import json
import os
import subprocess
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


DEFAULT_FEATURES = [
    "protocol",
    "src_port",
    "dst_port",
    "src_ip_enc",
    "pkt_size",
    "iat",
    "flow_duration",
    "pkts_per_flow",
    "flow_table_util",
    "new_flow_rate",
    "port_entropy",
    "flow_pkt_ratio",
    "burst_score",
    "entropy_delta",
    "spoofing_conf",
]

LEAKAGE_PRONE_FEATURES = {"spoofing_conf"}


def encode_ip(ip_val):
    try:
        parts = str(ip_val).split(".")
        return (
            int(parts[0]) * 16777216
            + int(parts[1]) * 65536
            + int(parts[2]) * 256
            + int(parts[3])
        )
    except Exception:
        return 0


def get_repo_root(script_path):
    # eval/run_audited_eval.py -> loft_project
    return os.path.dirname(os.path.dirname(os.path.abspath(script_path)))


def get_git_commit(repo_root):
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(repo_root),
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def prepare_features(df, selected_features):
    feat = pd.DataFrame(index=df.index)
    feat["protocol"] = df["protocol"]
    feat["src_port"] = df["src_port"]
    feat["dst_port"] = df["dst_port"]
    feat["src_ip_enc"] = df["src_ip"].apply(encode_ip)
    feat["pkt_size"] = df["pkt_size"]
    feat["iat"] = df["iat"]
    feat["flow_duration"] = df["flow_duration"]
    feat["pkts_per_flow"] = df["pkts_per_flow"]
    feat["flow_table_util"] = df["flow_table_util"]
    feat["new_flow_rate"] = df["new_flow_rate"]
    feat["port_entropy"] = df["port_entropy"]
    feat["flow_pkt_ratio"] = df["flow_pkt_ratio"]
    feat["burst_score"] = df["burst_score"].clip(upper=500)
    feat["entropy_delta"] = df["entropy_delta"]
    feat["spoofing_conf"] = df["spoofing_conf"]
    return feat[selected_features]


def make_groups(df):
    if {"src_ip", "dst_ip", "src_port", "dst_port"}.issubset(df.columns):
        return (
            df["src_ip"].astype(str)
            + "|"
            + df["dst_ip"].astype(str)
            + "|"
            + df["src_port"].astype(str)
            + "|"
            + df["dst_port"].astype(str)
        )
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Run single audited LOFT evaluation with reproducible artifacts."
    )
    parser.add_argument(
        "--data-path",
        default=None,
        help="CSV dataset path (default: loft_project/data/full_dataset.csv).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: loft_project/results/audited).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--test-size", type=float, default=0.2, help="Holdout test fraction."
    )
    parser.add_argument(
        "--allow-leakage-prone-feature",
        action="store_true",
        help="Keep leakage-prone features (default drops spoofing_conf).",
    )
    args = parser.parse_args()

    repo_root = get_repo_root(__file__)
    data_path = args.data_path or os.path.join(repo_root, "data", "full_dataset.csv")
    output_dir = args.output_dir or os.path.join(repo_root, "results", "audited")
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_csv(data_path)
    if "label" not in df.columns:
        raise ValueError("Dataset must contain a 'label' column.")

    selected_features = list(DEFAULT_FEATURES)
    dropped_features = []
    if not args.allow_leakage_prone_feature:
        selected_features = [
            f for f in selected_features if f not in LEAKAGE_PRONE_FEATURES
        ]
        dropped_features = sorted(list(LEAKAGE_PRONE_FEATURES))

    X = prepare_features(df, selected_features)
    y = df["label"].astype(int)
    groups = make_groups(df)

    if groups is not None:
        splitter = GroupShuffleSplit(
            n_splits=1, test_size=args.test_size, random_state=args.seed
        )
        train_idx, test_idx = next(splitter.split(X, y, groups=groups))
    else:
        train_idx, test_idx = train_test_split(
            np.arange(len(df)),
            test_size=args.test_size,
            random_state=args.seed,
            stratify=y,
        )

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "clf",
                VotingClassifier(
                    estimators=[
                        (
                            "svm",
                            SVC(
                                kernel="rbf",
                                C=1.0,
                                gamma="scale",
                                probability=True,
                                random_state=args.seed,
                            ),
                        ),
                        (
                            "rf",
                            RandomForestClassifier(
                                n_estimators=100,
                                max_depth=8,
                                min_samples_split=10,
                                min_samples_leaf=5,
                                random_state=args.seed,
                            ),
                        ),
                    ],
                    voting="soft",
                    weights=[1, 1],
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    cm = confusion_matrix(y_test, y_pred)

    acc = float(accuracy_score(y_test, y_pred))
    pre = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    auc = float(roc_auc_score(y_test, y_prob))
    fpr, tpr, thresholds = roc_curve(y_test, y_prob)

    metrics = {
        "accuracy": acc,
        "precision": pre,
        "recall": rec,
        "f1_score": f1,
        "roc_auc": auc,
        "confusion_matrix": cm.tolist(),
        "false_positive_rate": float(cm[0][1] / max(cm[0][0] + cm[0][1], 1)),
        "train_samples": int(len(train_idx)),
        "test_samples": int(len(test_idx)),
    }

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(repo_root),
        "dataset_path": os.path.abspath(data_path),
        "dataset_rows": int(len(df)),
        "seed": int(args.seed),
        "test_size": float(args.test_size),
        "features_used": selected_features,
        "features_dropped": dropped_features,
        "split_strategy": "GroupShuffleSplit(4-tuple)" if groups is not None else "StratifiedRandomSplit",
        "train_indices_path": os.path.join(output_dir, "train_indices.csv"),
        "test_indices_path": os.path.join(output_dir, "test_indices.csv"),
    }

    pd.DataFrame({"index": train_idx}).to_csv(
        os.path.join(output_dir, "train_indices.csv"), index=False
    )
    pd.DataFrame({"index": test_idx}).to_csv(
        os.path.join(output_dir, "test_indices.csv"), index=False
    )
    pd.DataFrame(
        {
            "index": X_test.index,
            "y_true": y_test.values,
            "y_pred": y_pred,
            "y_prob_attack": y_prob,
        }
    ).to_csv(os.path.join(output_dir, "predictions.csv"), index=False)
    pd.DataFrame({"fpr": fpr, "tpr": tpr, "threshold": thresholds}).to_csv(
        os.path.join(output_dir, "roc_points.csv"), index=False
    )
    pd.DataFrame(
        [{"tn": cm[0][0], "fp": cm[0][1], "fn": cm[1][0], "tp": cm[1][1]}]
    ).to_csv(os.path.join(output_dir, "confusion_matrix.csv"), index=False)

    with open(os.path.join(output_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("=" * 64)
    print("AUDITED EVALUATION COMPLETE")
    print("=" * 64)
    print(f"Accuracy : {acc * 100:.2f}%")
    print(f"Precision: {pre * 100:.2f}%")
    print(f"Recall   : {rec * 100:.2f}%")
    print(f"F1       : {f1 * 100:.2f}%")
    print(f"ROC AUC  : {auc:.4f}")
    print(f"FPR      : {metrics['false_positive_rate'] * 100:.2f}%")
    print(f"Artifacts: {output_dir}")


if __name__ == "__main__":
    main()

