# FEVER with ingress blocking: development check

T1B at 600 pps, tree, seeds 4181-4182 (docs/ingress_plan.md). fever-fl-ll-noing: the old block
(2 s drop rule renewed by the blocking switch); fever-fl-ll: permanent drop at the host's access
port. Means of the runs; two seeds, so the columns after the attack occupancy are descriptive.

| Traffic | Method | Runs | Harm % | Attack occupancy % | Probe success % | Never installed % | Packet-Ins | Drop rules | Ingress rules | First block s | Benign hosts blocked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 | fever-fl-ll-noing | 2 | 0.015 | 22.22 | 50.9 | 5.17 | 109276 | 384 | 0 | 72.5 | 0.0 |
| A2 | fever-fl-ll | 2 | 0.005 | 4.17 | 96.1 | 0.07 | 80832 | 6 | 2 | 72.4 | 0.0 |
| A4 | fever-fl-ll-noing | 2 | 0.000 | 23.70 | 61.0 | 2.56 | 115370 | 355 | 0 | 76.3 | 0.0 |
| A4 | fever-fl-ll | 2 | 0.000 | 4.30 | 99.6 | 0.01 | 77900 | 6 | 2 | 77.7 | 0.0 |
| E9P | fever-fl-ll-noing | 2 | 0.000 | 23.19 | 13.6 | 15.59 | 148484 | 566 | 0 | 76.4 | 0.0 |
| E9P | fever-fl-ll | 2 | 0.000 | 11.84 | 51.9 | 10.57 | 114495 | 38 | 2 | 81.1 | 0.0 |
| benign | fever-fl-ll-noing | 2 | 0.000 | 0.00 | 100.0 | 0.13 | 68238 | 0 | 0 | nan | 0.0 |
| benign | fever-fl-ll | 2 | 0.000 | 0.00 | 100.0 | 0.18 | 68715 | 0 | 0 | nan | 0.0 |

## Adoption rule

| Condition | Holds |
|---|---|
| A2: harm ingress <= old + 0.1 | yes |
| A2: attack occupancy ingress <= old + 2 | yes |
| A4: harm ingress <= old + 0.1 | yes |
| A4: attack occupancy ingress <= old + 2 | yes |
| E9P: harm ingress <= old + 0.1 | yes |
| E9P: attack occupancy ingress <= old + 2 | yes |
| No benign host blocked by ingress | yes |
| Benign only: harm ingress <= 0.1 % | yes |

**Adopted: FEVER blocks at the ingress.**

## FTMaster's source blocks in the switch (E9P)

| Runs | Sources blocked (attack) | Sources blocked (benign) | Drop rules | Packet-Ins | Probe success % | Harm % |
|---|---|---|---|---|---|---|
| 2 | 0.0 | 0.0 | 0 | 84038 | 13.5 | 9.325 |
