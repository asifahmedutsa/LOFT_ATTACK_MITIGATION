import flwr as fl
import pandas as pd
import numpy as np
import pickle, os, sys, json
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (accuracy_score, precision_score,
                              recall_score, f1_score)

def encode_ip(ip):
    try:
        p=ip.split('.')
        return int(p[0])*16777216+int(p[1])*65536+int(p[2])*256+int(p[3])
    except: return 0

def prepare_features(df):
    f = pd.DataFrame()
    f['eth_type']       = df['eth_type']
    f['protocol']       = df['protocol']
    f['src_port']       = df['src_port']
    f['dst_port']       = df['dst_port']
    f['src_ip_enc']     = df['src_ip'].apply(encode_ip)
    f['dst_ip_enc']     = df['dst_ip'].apply(encode_ip)
    f['pkt_size']       = df['pkt_size']
    f['ttl']            = df['ttl']
    f['iat']            = df['iat']
    f['flow_duration']  = df['flow_duration']
    f['pkts_per_flow']  = df['pkts_per_flow']
    f['bytes_per_flow'] = df['bytes_per_flow']
    f['flow_table_util']= df['flow_table_util']
    f['new_flow_rate']  = df['new_flow_rate']
    f['port_entropy']   = df['port_entropy']
    f['flow_pkt_ratio'] = df['flow_pkt_ratio']
    f['burst_score']    = df['burst_score']
    f['entropy_delta']  = df['entropy_delta']
    f['spoofing_conf']  = df['spoofing_conf']
    return f

class DualGuardClient(fl.client.NumPyClient):
    def __init__(self, controller_id, data_path):
        self.cid  = controller_id
        self.home = os.path.expanduser("~")

        df    = pd.read_csv(data_path)
        chunk = len(df) // 3
        if controller_id==1:   sub=df.iloc[:chunk]
        elif controller_id==2: sub=df.iloc[chunk:2*chunk]
        else:                  sub=df.iloc[2*chunk:]

        X = prepare_features(sub); y = sub['label']
        self.Xtr,self.Xte,self.ytr,self.yte = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)

        self.sc  = StandardScaler()
        self.Xtr = self.sc.fit_transform(self.Xtr)
        self.Xte = self.sc.transform(self.Xte)

        mpath = f"{self.home}/loft_project/models/saved/controller_{controller_id}_model.pkl"
        with open(mpath,'rb') as fh:
            self.model = pickle.load(fh)

        print(f"[+] Controller {controller_id} FL client ready | "
              f"train={len(self.Xtr)} test={len(self.Xte)}")

    def get_parameters(self, config):
        rf = self.model.estimators_[1]
        return [rf.feature_importances_]

    def fit(self, parameters, config):
        print(f"[*] Controller {self.cid}: federated training round...")
        self.model.fit(self.Xtr, self.ytr)
        yp  = self.model.predict(self.Xtr)
        acc = accuracy_score(self.ytr, yp)
        f1  = f1_score(self.ytr, yp, zero_division=0)
        print(f"[+] Controller {self.cid}: train acc={acc*100:.2f}% f1={f1*100:.2f}%")
        return self.get_parameters({}), len(self.Xtr), {
            'accuracy' :float(acc), 'precision':float(acc),
            'recall'   :float(acc), 'f1_score' :float(f1)}

    def evaluate(self, parameters, config):
        yp  = self.model.predict(self.Xte)
        acc = accuracy_score(self.yte, yp)
        pre = precision_score(self.yte, yp, zero_division=0)
        rec = recall_score(self.yte, yp, zero_division=0)
        f1  = f1_score(self.yte, yp, zero_division=0)
        print(f"[+] Controller {self.cid}: "
              f"acc={acc*100:.2f}% pre={pre*100:.2f}% "
              f"rec={rec*100:.2f}% f1={f1*100:.2f}%")
        out = f"{self.home}/loft_project/federated/controller_{self.cid}_fl_results.json"
        with open(out,'w') as fh:
            json.dump({'controller_id':self.cid,'accuracy':acc,
                       'precision':pre,'recall':rec,'f1_score':f1}, fh, indent=2)
        return float(1-acc), len(self.Xte), {
            'accuracy' :float(acc),'precision':float(pre),
            'recall'   :float(rec),'f1_score' :float(f1)}

if __name__ == "__main__":
    cid       = int(sys.argv[1])
    home      = os.path.expanduser("~")
    data_path = f"{home}/loft_project/data/full_dataset.csv"
    print(f"\n{'='*50}\n  FL-DualGuard Client — Controller {cid}\n{'='*50}")
    client = DualGuardClient(cid, data_path)
    fl.client.start_client(
        server_address="127.0.0.1:8080",
        client=client.to_client())
