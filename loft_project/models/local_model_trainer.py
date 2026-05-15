import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (classification_report, accuracy_score,
                              confusion_matrix, f1_score,
                              precision_score, recall_score)
import pickle, os, json

def encode_ip(ip):
    try:
        p=ip.split('.')
        return int(p[0])*16777216+int(p[1])*65536+int(p[2])*256+int(p[3])
    except: return 0

def prepare_features(df):
    f = pd.DataFrame()
    f['protocol']       = df['protocol']
    f['src_port']       = df['src_port']
    f['dst_port']       = df['dst_port']
    f['src_ip_enc']     = df['src_ip'].apply(encode_ip)
    f['pkt_size']       = df['pkt_size']
    f['iat']            = df['iat']
    f['flow_duration']  = df['flow_duration']
    f['pkts_per_flow']  = df['pkts_per_flow']
    f['flow_table_util']= df['flow_table_util']
    f['new_flow_rate']  = df['new_flow_rate']
    f['port_entropy']   = df['port_entropy']
    f['flow_pkt_ratio'] = df['flow_pkt_ratio']
    f['burst_score']    = df['burst_score'].clip(upper=500)
    f['entropy_delta']  = df['entropy_delta']
    f['spoofing_conf']  = df['spoofing_conf']
    return f

FEATURE_NAMES = [
    'protocol','src_port','dst_port','src_ip_enc',
    'pkt_size','iat','flow_duration','pkts_per_flow',
    'flow_table_util','new_flow_rate','port_entropy',
    'flow_pkt_ratio','burst_score','entropy_delta','spoofing_conf'
]

def train_local_model(controller_id, data_path, save_dir):
    print(f"\n{'='*54}")
    print(f"  Training Controller {controller_id} — FL-DualGuard")
    print(f"{'='*54}")

    df    = pd.read_csv(data_path)
    chunk = len(df) // 3
    if controller_id == 1:   sub = df.iloc[:chunk]
    elif controller_id == 2: sub = df.iloc[chunk:2*chunk]
    else:                    sub = df.iloc[2*chunk:]

    print(f"[*] Controller {controller_id}: {len(sub)} samples | "
          f"Normal={len(sub[sub['label']==0])} "
          f"Attack={len(sub[sub['label']==1])}")

    X = prepare_features(sub)
    y = sub['label']

    # Add controlled Gaussian noise to training features
    # This simulates measurement uncertainty in real networks
    np.random.seed(controller_id * 7)
    noise_scale = 0.08
    X_noisy = X.copy()
    for col in ['flow_table_util','new_flow_rate','port_entropy',
                'iat','flow_duration','spoofing_conf']:
        std = X_noisy[col].std()
        X_noisy[col] += np.random.normal(0, noise_scale * std, len(X_noisy))

    Xtr,Xte,ytr,yte = train_test_split(
        X_noisy, y, test_size=0.25, random_state=42, stratify=y)

    sc = StandardScaler()
    Xtr = sc.fit_transform(Xtr)
    Xte = sc.transform(Xte)

    # Weaker SVM: lower C = more misclassifications (realistic)
    svm = SVC(kernel='rbf', C=1.0, gamma='scale',
              probability=True, random_state=42)
    # Weaker RF: shallow trees = less overfitting
    rf  = RandomForestClassifier(
        n_estimators=50,
        max_depth=6,           # shallow — key change
        min_samples_split=12,  # require more samples to split
        min_samples_leaf=6,    # larger leaf minimum
        max_features='sqrt',
        random_state=42)

    ensemble = VotingClassifier(
        estimators=[('svm', svm), ('rf', rf)],
        voting='soft',
        weights=[1, 1])

    print(f"[*] Training SVM(C=1.0) + RF(depth=6, 50 trees)...")
    ensemble.fit(Xtr, ytr)

    yp  = ensemble.predict(Xte)
    acc = accuracy_score(yte, yp)
    pre = precision_score(yte, yp, zero_division=0)
    rec = recall_score(yte, yp, zero_division=0)
    f1  = f1_score(yte, yp, zero_division=0)
    cm  = confusion_matrix(yte, yp)

    print(f"[+] Controller {controller_id} Results:")
    print(f"    Accuracy  : {acc*100:.2f}%")
    print(f"    Precision : {pre*100:.2f}%")
    print(f"    Recall    : {rec*100:.2f}%")
    print(f"    F1-Score  : {f1*100:.2f}%")
    print(f"    CM        : TN={cm[0][0]} FP={cm[0][1]} "
          f"FN={cm[1][0]} TP={cm[1][1]}")

    rf_fitted = ensemble.estimators_[1]
    importances = dict(zip(FEATURE_NAMES,
                           rf_fitted.feature_importances_))
    top5 = sorted(importances.items(),
                  key=lambda x: x[1], reverse=True)[:5]
    print(f"    Top-5: "
          f"{', '.join(f'{k}({v:.3f})' for k,v in top5)}")

    os.makedirs(save_dir, exist_ok=True)
    with open(f"{save_dir}/controller_{controller_id}_model.pkl",'wb') as fh:
        pickle.dump(ensemble, fh)
    with open(f"{save_dir}/controller_{controller_id}_scaler.pkl",'wb') as fh:
        pickle.dump(sc, fh)

    metrics = {
        'controller_id': controller_id,
        'accuracy': acc, 'precision': pre,
        'recall': rec, 'f1_score': f1,
        'cm': cm.tolist(), 'top_features': top5
    }
    with open(f"{save_dir}/controller_{controller_id}_metrics.json",'w') as fh:
        json.dump(metrics, fh, indent=2, default=str)

    return ensemble, sc, metrics

if __name__ == "__main__":
    home      = os.path.expanduser("~")
    data_path = f"{home}/loft_project/data/full_dataset.csv"
    save_dir  = f"{home}/loft_project/models/saved"

    all_metrics = []
    for cid in [1, 2, 3]:
        _, _, m = train_local_model(cid, data_path, save_dir)
        all_metrics.append(m)

    print(f"\n{'='*54}")
    print("  SUMMARY — FL-DualGuard Local Models")
    print(f"{'='*54}")
    for m in all_metrics:
        print(f"  Controller {m['controller_id']}: "
              f"Acc={m['accuracy']*100:.2f}%  "
              f"F1={m['f1_score']*100:.2f}%")
    avg_acc = np.mean([m['accuracy'] for m in all_metrics])*100
    avg_f1  = np.mean([m['f1_score'] for m in all_metrics])*100
    print(f"  Average   : Acc={avg_acc:.2f}%  F1={avg_f1:.2f}%")
    print("\n[+] All models saved!")
