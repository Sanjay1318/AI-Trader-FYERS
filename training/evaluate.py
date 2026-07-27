"""
Model evaluation and validation.
Metrics, baselines, classification reports for Milestone 3.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score,
    precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)


def compute_naive_baselines(y_true):
    """
    Report majority-class and random 3-class baselines.

    Parameters
    ----------
    y_true : array-like
        True labels (DOWN, NEUTRAL, UP)

    Returns
    -------
    dict
        {'majority_class': {accuracy, macro_f1},
         'random_3class':  {accuracy, macro_f1}}
    """
    from collections import Counter
    classes = ['DOWN', 'NEUTRAL', 'UP']

    # Majority-class baseline: always predict the most frequent class
    counts = Counter(y_true)
    majority_class = counts.most_common(1)[0][0]
    majority_preds = np.full(len(y_true), majority_class)
    maj_acc = accuracy_score(y_true, majority_preds)
    # For majority macro F1: only one class predicted, F1=0 for all others
    maj_f1 = f1_score(y_true, majority_preds, labels=classes, average='macro', zero_division=0)

    # Random 3-class baseline: uniform random predictions
    rng = np.random.default_rng(42)
    random_preds = rng.choice(classes, size=len(y_true))
    rand_acc = accuracy_score(y_true, random_preds)
    rand_f1 = f1_score(y_true, random_preds, labels=classes, average='macro', zero_division=0)

    results = {
        'majority_class': {
            'accuracy': maj_acc,
            'macro_f1': maj_f1,
            'majority_class': majority_class,
        },
        'random_3class': {
            'accuracy': rand_acc,
            'macro_f1': rand_f1,
        },
    }
    return results


def evaluate_model(y_true, y_pred, class_order=None):
    """
    Evaluate a classifier and return comprehensive metrics.

    Parameters
    ----------
    y_true : array-like
        True labels (strings: DOWN, NEUTRAL, UP)
    y_pred : array-like
        Predicted labels
    class_order : list or None
        Explicit class order for metrics / confusion matrix

    Returns
    -------
    dict
        All computed metrics
    """
    if class_order is None:
        class_order = ['DOWN', 'NEUTRAL', 'UP']

    acc = accuracy_score(y_true, y_pred)
    bal_acc = balanced_accuracy_score(y_true, y_pred)
    macro_prec = precision_score(y_true, y_pred, labels=class_order, average='macro', zero_division=0)
    macro_rec = recall_score(y_true, y_pred, labels=class_order, average='macro', zero_division=0)
    macro_f1 = f1_score(y_true, y_pred, labels=class_order, average='macro', zero_division=0)
    weighted_f1 = f1_score(y_true, y_pred, labels=class_order, average='weighted', zero_division=0)

    # Per-class metrics
    per_class_prec = precision_score(y_true, y_pred, labels=class_order, average=None, zero_division=0)
    per_class_rec = recall_score(y_true, y_pred, labels=class_order, average=None, zero_division=0)
    per_class_f1 = f1_score(y_true, y_pred, labels=class_order, average=None, zero_division=0)

    per_class = {}
    for i, cls in enumerate(class_order):
        per_class[cls] = {
            'precision': per_class_prec[i],
            'recall': per_class_rec[i],
            'f1': per_class_f1[i],
        }

    cm = confusion_matrix(y_true, y_pred, labels=class_order)

    # Predicted class distribution
    unique, counts = np.unique(y_pred, return_counts=True)
    pred_dist = dict(zip(unique, counts))

    report = {
        'accuracy': acc,
        'balanced_accuracy': bal_acc,
        'macro_precision': macro_prec,
        'macro_recall': macro_rec,
        'macro_f1': macro_f1,
        'weighted_f1': weighted_f1,
        'per_class': per_class,
        'confusion_matrix': cm.tolist(),
        'class_order': class_order,
        'predicted_distribution': pred_dist,
    }
    return report


def print_evaluation(name, report, dataset_label=''):
    """Pretty-print evaluation results."""
    header = f"  {name} — {dataset_label}" if dataset_label else f"  {name}"
    print(f"\n{'='*60}")
    print(header)
    print(f"{'='*60}")
    print(f"  Accuracy:          {report['accuracy']:.4f}")
    print(f"  Balanced Accuracy: {report['balanced_accuracy']:.4f}")
    print(f"  Macro Precision:   {report['macro_precision']:.4f}")
    print(f"  Macro Recall:      {report['macro_recall']:.4f}")
    print(f"  Macro F1:          {report['macro_f1']:.4f}")
    print(f"  Weighted F1:       {report['weighted_f1']:.4f}")
    print(f"\n  Per-Class Metrics:")
    for cls, metrics in report['per_class'].items():
        print(f"    {cls:8s}  Prec={metrics['precision']:.4f}  Rec={metrics['recall']:.4f}  F1={metrics['f1']:.4f}")

    print(f"\n  Confusion Matrix (rows=true, cols=pred):")
    cm = report['confusion_matrix']
    classes = report['class_order']
    print(f"    {'':8s}  {' '.join(f'{c:>8s}' for c in classes)}")
    for i, cls in enumerate(classes):
        row_str = ' '.join(f'{val:8d}' for val in cm[i])
        print(f"    {cls:8s}  {row_str}")

    print(f"\n  Predicted Distribution: {report['predicted_distribution']}")
