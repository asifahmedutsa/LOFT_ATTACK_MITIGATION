# EnsGuard v4, phase 2: offline check against the rules fixed in docs/v4_plan.md

| Candidate | R1 A4 recall sim / tb (>= 30) | R2 benign FPR sim / tb (<= 0.5) | R3 A2 recall sim (>= v3 - 2) | R4 E11 unseen recall (>= 46.5) | E9P recall sim / tb | Pass |
|---|---|---|---|---|---|---|
| ens3 | 0.0 / 0.0 | 0.13 / 0.00 | 99.4 | 48.5 | 0.0 / 0.0 | no |
| ens4 | 0.0 / 0.0 | 0.13 / 0.00 | 100.0 | 14.9 | 0.0 / 0.0 | no |
| cb4 | 0.0 / 0.0 | 0.14 / 0.00 | 100.0 | 21.0 | 0.0 / 0.0 | no |

Per-entry rates (%) at the T1 tau; attack_median is the median attack score.

```
source variant cand   tau      n  recall   fpr  attack_median
   sim      A2 ens3 0.639 132258  99.432 0.274          0.831
   sim      A2 ens4 0.479 132258 100.000 0.279          0.873
   sim      A2  cb4 0.467 132258 100.000 0.238          0.903
   sim      A4 ens3 0.639 132101   0.005 0.205          0.336
   sim      A4 ens4 0.479 132101   0.005 0.207          0.252
   sim      A4  cb4 0.467 132101   0.008 0.205          0.250
   sim     E9P ens3 0.639 138285   0.001 0.106          0.006
   sim     E9P ens4 0.479 138285   0.001 0.110          0.005
   sim     E9P  cb4 0.467 138285   0.001 0.117          0.003
   sim  benign ens3 0.639  72052     NaN 0.133            NaN
   sim  benign ens4 0.479  72052     NaN 0.133            NaN
   sim  benign  cb4 0.467  72052     NaN 0.144            NaN
    tb      A2 ens3 0.639 174391  95.100 0.190          0.865
    tb      A2 ens4 0.479 174391  99.657 0.196          0.889
    tb      A2  cb4 0.467 174391  99.633 0.188          0.980
    tb      A4 ens3 0.639 179217   0.003 0.169          0.264
    tb      A4 ens4 0.479 179217   0.003 0.173          0.199
    tb      A4  cb4 0.467 179217   0.004 0.171          0.247
    tb     E9P ens3 0.639 162815   0.001 0.159          0.047
    tb     E9P ens4 0.479 162815   0.001 0.161          0.036
    tb     E9P  cb4 0.467 162815   0.001 0.164          0.026
    tb  benign ens3 0.639  82137   0.000 0.000          0.001
    tb  benign ens4 0.479  82137   0.000 0.000          0.001
    tb  benign  cb4 0.467  82137   0.000 0.002          0.000
```
