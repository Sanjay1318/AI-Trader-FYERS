"""
ML model training pipeline — Milestone 3.
Trains baseline classifiers for UP/DOWN/NEUTRAL prediction (10-min horizon).
All preprocessing fitted on TRAIN only. Validation/test untouched until selection.
"""

import numpy as np
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import warnings
warnings.filterwarnings('ignore')

from datasets.dataset_builder import (
    build_dataset, compute_train_thresholds, chronological_split
)
from training.evaluate import (
    compute_naive_baselines, evaluate_model, print_evaluation
)

CLASS_ORDER = ['DOWN', 'NEUTRAL', 'UP']
RANDOM_STATE = 42
LABEL_HORIZON = 10
MODEL_DIR = Path(__file__).resolve().parent.parent / 'models' / 'saved'
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def verify_dataset(X_train, X_val, X_test, y_train, y_val, y_test, features, thresholds):
    print(f"\n{'='*60}")
    print("  STEP 1 — DATASET VERIFICATION")
    print(f"{'='*60}")
    print(f"  X_train shape:        {X_train.shape}")
    print(f"  X_val shape:          {X_val.shape}")
    print(f"  X_test shape:         {X_test.shape}")
    print(f"  Features:             {X_train.shape[1]}")
    for name, y in [('y_train', y_train), ('y_val', y_val), ('y_test', y_test)]:
        print(f"  {name}: {y.value_counts().to_dict()}")
    ok = True
    for label, X in [('X_train', X_train), ('X_val', X_val), ('X_test', X_test)]:
        if X.isna().any().any():
            cols = X.columns[X.isna().any()].tolist()
            print(f"  FAIL: {label} has NaN: {cols}")
            ok = False
        if np.isinf(X.values).any():
            print(f"  FAIL: {label} has inf")
            ok = False
    found = [c for c in X_train.columns if c in {'timestamp','forward_return_pct','label','date_ist'}]
    if found:
        print(f"  FAIL: forbidden cols: {found}")
        ok = False
    if ok:
        print("  VERIFICATION: PASS")
    else:
        print("  VERIFICATION: FAIL")
        return False
    print(f"  Thresholds: UP>{thresholds['up']:.4f}% DOWN<{thresholds['down']:.4f}%")
    print(f"  Train: {thresholds['train_start_date']} -> {thresholds['train_end_date']}")
    return True


def prepare_data():
    from database.db import read_sql
    df = read_sql("SELECT * FROM market_features ORDER BY timestamp")
    thresholds = compute_train_thresholds(df, label_horizon=LABEL_HORIZON)
    dataset = build_dataset(df, label_horizon=LABEL_HORIZON, thresholds=thresholds)
    split = chronological_split(dataset)
    splits = split['splits']
    meta = {'timestamp', 'label', 'forward_return_pct'}
    features = [c for c in splits['train'].columns if c not in meta]
    X_train = splits['train'][features].copy()
    y_train = splits['train']['label'].copy()
    X_val = splits['validation'][features].copy()
    y_val = splits['validation']['label'].copy()
    X_test = splits['test'][features].copy()
    y_test = splits['test']['label'].copy()
    split_info = {
        'train_range': split['train']['date_range'],
        'val_range': split['validation']['date_range'],
        'test_range': split['test']['date_range'],
        'train_rows': len(splits['train']),
        'val_rows': len(splits['validation']),
        'test_rows': len(splits['test']),
    }
    return X_train, X_val, X_test, y_train, y_val, y_test, features, thresholds, split_info


def train_lr(X_train, y_train):
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X_train)
    model = LogisticRegression(solver='lbfgs', max_iter=2000,
                                random_state=RANDOM_STATE, class_weight='balanced', n_jobs=-1)
    model.fit(Xs, y_train)
    return model, scaler


def train_rf(X_train, y_train):
    model = RandomForestClassifier(n_estimators=200, max_depth=15, min_samples_leaf=10,
                                    min_samples_split=20, random_state=RANDOM_STATE,
                                    class_weight='balanced', n_jobs=-1)
    model.fit(X_train, y_train)
    return model


def train_xgb(X_train, y_train):
    import xgboost as xgb
    lm = {'DOWN': 0, 'NEUTRAL': 1, 'UP': 2}
    yi = y_train.map(lm)
    model = xgb.XGBClassifier(objective='multi:softprob', num_class=3, n_estimators=200,
                               max_depth=6, learning_rate=0.1, subsample=0.8,
                               colsample_bytree=0.8, random_state=RANDOM_STATE, eval_metric='mlogloss')
    model.fit(X_train, yi)
    return model, lm


def confidence_analysis(y_true, probs, class_order=None):
    if class_order is None:
        class_order = CLASS_ORDER
    mp = probs.max(axis=1)
    pi = probs.argmax(axis=1)
    pc = np.array([class_order[i] for i in pi])
    stats = {'mean': float(np.mean(mp)), 'median': float(np.median(mp)),
             'p25': float(np.percentile(mp,25)), 'p75': float(np.percentile(mp,75)),
             'p90': float(np.percentile(mp,90))}
    ya = np.array(y_true) if isinstance(y_true, pd.Series) else y_true
    from sklearn.metrics import accuracy_score, f1_score
    res = []
    for t in [0.40, 0.50, 0.60, 0.70]:
        m = mp >= t
        n = int(m.sum())
        p = n/len(ya)*100 if len(ya)>0 else 0
        if n>0:
            res.append({'thresh':t, 'n':n, 'pct':p,
                        'acc': accuracy_score(ya[m], pc[m]),
                        'mf1': f1_score(ya[m], pc[m], labels=class_order, average='macro', zero_division=0)})
        else:
            res.append({'thresh':t, 'n':0, 'pct':p, 'acc':0, 'mf1':0})
    return stats, res


def feat_importance(model, names, mtype):
    if mtype in ('rf', 'xgb'):
        imp = model.feature_importances_
        idx = np.argsort(imp)[::-1][:15]
        return [{'feature': names[i], 'importance': float(imp[i])} for i in idx]
    elif mtype == 'lr':
        coef = model.coef_
        res = {}
        for i, cls in enumerate(model.classes_):
            ac = np.abs(coef[i])
            top = np.argsort(ac)[::-1][:15]
            res[cls] = [{'feature': names[j], 'coef': float(coef[i][j])} for j in top]
        return res
    return None


def save_model(model, scaler, label_map, meta, mtype):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f"baseline_{mtype}_{ts}"
    p = MODEL_DIR / f"{name}.joblib"
    joblib.dump(model, p)
    sp = None
    if scaler is not None:
        sp = MODEL_DIR / f"{name}_scaler.joblib"
        joblib.dump(scaler, sp)
    lp = None
    if label_map is not None:
        lp = MODEL_DIR / f"{name}_label_map.joblib"
        joblib.dump(label_map, lp)
    meta['model_path'] = str(p)
    meta['scaler_path'] = str(sp) if sp else None
    meta['label_map_path'] = str(lp) if lp else None
    meta['created'] = ts
    mp = MODEL_DIR / f"{name}_metadata.json"
    with open(mp, 'w') as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"\n  Saved: {p}")
    return p


def run():
    print(f"\n{'='*60}")
    print("  MILESTONE 3 — BASELINE TRAINING")
    print(f"  Horizon: {LABEL_HORIZON}min  Target: UP/DOWN/NEUTRAL")
    print(f"{'='*60}")
    X_train, X_val, X_test, y_train, y_val, y_test, features, thresh, split_info = prepare_data()
    if not verify_dataset(X_train, X_val, X_test, y_train, y_val, y_test, features, thresh):
        return
    mv = {}
    ma = {}

    # Step 2
    print(f"\n{'='*60}")
    print("  STEP 2 — NAIVE BASELINES")
    print(f"{'='*60}")
    naive = compute_naive_baselines(y_train)
    mc = naive['majority_class']
    rc = naive['random_3class']
    print(f"  Majority-class ({mc['majority_class']}): Acc={mc['accuracy']:.4f} MF1={mc['macro_f1']:.4f}")
    print(f"  Random 3-class: Acc={rc['accuracy']:.4f} MF1={rc['macro_f1']:.4f}")

    # Step 3
    print(f"\n{'='*60}\n  STEP 3 — TRAINING\n{'='*60}")
    print("  Logistic Regression...")
    lr_m, lr_s = train_lr(X_train, y_train)
    print("  Random Forest...")
    rf_m = train_rf(X_train, y_train)
    print("  XGBoost...")
    xgb_m, xgb_lm = train_xgb(X_train, y_train)
    print("  Done.")

    # Step 4
    print(f"\n{'='*60}\n  STEP 4 — VALIDATION\n{'='*60}")
    Xvl = lr_s.transform(X_val)
    ypl = lr_m.predict(Xvl)
    lr_v = evaluate_model(y_val, ypl, CLASS_ORDER)
    print_evaluation('LOGISTIC REGRESSION', lr_v, 'VALIDATION')
    mv['LR'] = lr_v
    ma['LR'] = (lr_m, lr_s, None, 'lr')

    ypr = rf_m.predict(X_val)
    rf_v = evaluate_model(y_val, ypr, CLASS_ORDER)
    print_evaluation('RANDOM FOREST', rf_v, 'VALIDATION')
    mv['RF'] = rf_v
    ma['RF'] = (rf_m, None, None, 'rf')

    ypx = xgb_m.predict(X_val)
    il = {v:k for k,v in xgb_lm.items()}
    ypxs = np.array([il[i] for i in ypx])
    xgb_v = evaluate_model(y_val, ypxs, CLASS_ORDER)
    print_evaluation('XGBOOST', xgb_v, 'VALIDATION')
    mv['XGB'] = xgb_v
    ma['XGB'] = (xgb_m, None, xgb_lm, 'xgb')

    # Step 5
    print(f"\n{'='*60}\n  STEP 5 — SELECTION\n{'='*60}")
    print(f"  {'Model':12s}  MacroF1")
    for k, v in mv.items():
        print(f"  {k:12s}  {v['macro_f1']:.4f}")
    best = max(mv, key=lambda k: mv[k]['macro_f1'])
    print(f"\n  SELECTED: {best} (MF1={mv[best]['macro_f1']:.4f})")

    # Step 6
    print(f"\n{'='*60}\n  STEP 6 — TEST\n{'='*60}")
    m, s, lm, mt = ma[best]
    if mt == 'lr':
        Xte = s.transform(X_test)
        ypt = m.predict(Xte)
    elif mt == 'xgb':
        ypti = m.predict(X_test)
        ypt = np.array([il[i] for i in ypti])
    else:
        ypt = m.predict(X_test)
    tr = evaluate_model(y_test, pd.Series(ypt, index=y_test.index), CLASS_ORDER)
    print_evaluation(f'{best} (SELECTED)', tr, 'TEST')

    # Step 7
    print(f"\n{'='*60}\n  STEP 7 — CONFIDENCE\n{'='*60}")
    if hasattr(m, 'predict_proba'):
        if mt == 'lr':
            probs = m.predict_proba(Xte)
        else:
            probs = m.predict_proba(X_test)
        cproba = list(m.classes_)
        pa = np.zeros((probs.shape[0], 3))
        for i, cls in enumerate(CLASS_ORDER):
            if cls in cproba:
                j = cproba.index(cls)
                pa[:, i] = probs[:, j]
        ps, pt = confidence_analysis(y_test, pa, CLASS_ORDER)
        print(f"  Mean:{ps['mean']:.4f} Med:{ps['median']:.4f} P25:{ps['p25']:.4f} P75:{ps['p75']:.4f} P90:{ps['p90']:.4f}")
        print(f"  {'Thresh':>6s}  {'N':>6s}  {'%':>7s}  {'Acc':>6s}  {'MF1':>6s}")
        for r in pt:
            print(f"  {r['thresh']:>6.2f}  {r['n']:>6d}  {r['pct']:>6.2f}%  {r['acc']:>6.4f}  {r['mf1']:>6.4f}")

    # Step 8
    print(f"\n{'='*60}\n  STEP 8 — FEATURE IMPORTANCE\n{'='*60}")
    fi = feat_importance(m, features, mt)
    if isinstance(fi, list):
        print(f"\n  Top 15 ({mt}):")
        for i, item in enumerate(fi, 1):
            print(f"    {i:2d}. {item['feature']:25s}  {item['importance']:.6f}")
    elif isinstance(fi, dict):
        for cls, items in fi.items():
            print(f"\n  {cls}:")
            for i, item in enumerate(items[:10], 1):
                print(f"    {i:2d}. {item['feature']:25s}  coeff={item['coef']:+.6f}")

    # Step 9
    print(f"\n{'='*60}\n  STEP 9 — SAVING\n{'='*60}")
    meta = {
        'milestone': '3', 'model_type': mt, 'n_features': len(features),
        'class_order': CLASS_ORDER, 'horizon': LABEL_HORIZON,
        'up_threshold': thresh['up'], 'down_threshold': thresh['down'],
        'threshold_method': thresh['method'], 'threshold_fitted_on': thresh['fitted_on'],
        'train_date_range': split_info['train_range'],
        'val_date_range': split_info['val_range'],
        'test_date_range': split_info['test_range'],
        'validation_macro_f1': mv[best]['macro_f1'],
        'test_accuracy': tr['accuracy'],
        'test_macro_f1': tr['macro_f1'],
        'test_balanced_accuracy': tr['balanced_accuracy'],
    }
    sp = save_model(m, s if mt=='lr' else None, lm if mt=='xgb' else None, meta, mt)

    # Step 10
    print(f"\n{'='*60}")
    print("  STEP 10 — REPORT")
    print(f"{'='*60}")
    print(f"\n  NAIVE BASELINES")
    print(f"    Majority-class: Acc={mc['accuracy']:.4f} MF1={mc['macro_f1']:.4f}")
    print(f"    Random 3-class: Acc={rc['accuracy']:.4f} MF1={rc['macro_f1']:.4f}")
    print(f"\n  VALIDATION RESULTS")
    for k, v in mv.items():
        print(f"    {k:12s}  Acc={v['accuracy']:.4f}  BAcc={v['balanced_accuracy']:.4f}  MF1={v['macro_f1']:.4f}")
    print(f"\n  SELECTED MODEL: {best}")
    print(f"\n  TEST RESULTS")
    print(f"    Accuracy:          {tr['accuracy']:.4f}")
    print(f"    Balanced Accuracy: {tr['balanced_accuracy']:.4f}")
    print(f"    Macro F1:          {tr['macro_f1']:.4f}")
    print(f"    Weighted F1:       {tr['weighted_f1']:.4f}")
    print(f"  CONFIDENCE ANALYSIS")
    if pt:
        print(f"    Mean confidence: {ps['mean']:.4f}")
    print(f"  TOP FEATURES")
    if isinstance(fi, list):
        for item in fi[:5]:
            print(f"    {item['feature']:25s}  {item['importance']:.6f}")
    print(f"\n  SAVED MODEL PATH")
    print(f"    {sp}")
    print(f"\n{'='*60}")
    print("  MILESTONE 3 BASELINE: PASS")
    print(f"{'='*60}")


if __name__ == '__main__':
    run()
