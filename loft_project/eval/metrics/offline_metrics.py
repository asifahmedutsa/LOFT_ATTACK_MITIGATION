from typing import Dict

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


def attack_detection_rate(y_true, y_pred) -> float:
    """
    Attack detection rate from DMS-BTT definition:
    correctly predicted as attack stages (1 or 2) among true attack stages (1 or 2).
    """
    true_attack = [i for i, y in enumerate(y_true) if y in (1, 2)]
    if not true_attack:
        return 0.0
    correct = sum(1 for i in true_attack if y_pred[i] in (1, 2))
    return correct / len(true_attack)


def binary_classification_metrics(y_true, y_pred) -> Dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def three_class_state_metrics(y_true, y_pred) -> Dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "attack_detection_rate": float(attack_detection_rate(y_true, y_pred)),
    }

