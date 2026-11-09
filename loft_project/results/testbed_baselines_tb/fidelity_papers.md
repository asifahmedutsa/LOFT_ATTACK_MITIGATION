# Retrained baselines against their papers' headline results

loftbench/tbfl_paper_fidelity.py. Ours, detection: the deployed per-entry model at the threshold
its defense applies, on the T1B testbed test recordings (seeds 4176-4178; G1-G3, Spoof, Pulse and
benign-only recordings as recorded: 960177 rows, 655470 attack). The papers score
their own traces and attacks, so the numbers are beside each other, not a replication.

| Baseline | Paper's setting | Published detection | Ours (training) | Acc. | Prec. | Rec. | F1 | FPR | Pooled arm: Acc. / FPR |
|---|---|---|---|---|---|---|---|---|---|
| FTMaster | Mininet; LFTO; classifiers' accuracy; attack rules in the table with FTMaster | accuracy 98 % or higher (most classifiers) | simulator T1A | 97.64 | 99.95 | 96.59 | 98.24 | 0.11 | 98.86 / 3.35 |
| FTOP | simulation; LFTO; Table IV | accuracy up to 98 % | simulator T1A | 97.86 | 99.95 | 96.92 | 98.41 | 0.11 | 98.73 / 3.73 |
| FloRa | Mininet, tables of 1,500-3,000 entries; LOFT | accuracy 99.49 %, FPR 0.01 % | C3 | 99.84 | 99.88 | 99.89 | 99.88 | 0.26 | 99.15 / 2.42 |
| DMS-BTT | table of 3,500, 600 s runs; LFTO; Table 6 | accuracy > 92 %, recall > 80 %, precision > 90 %, F1 > 85 % | C3 | 99.85 | 99.89 | 99.88 | 99.89 | 0.23 | 99.29 / 2.00 |
| FTODefender | simulation; LFTO; Table 3, against REFUSE | accuracy 97 % | C3 | 99.82 | 99.86 | 99.88 | 99.87 | 0.30 | 98.81 / 3.51 |

Mitigation: the published result, and our earlier testbed runs (A2, attack share of s11 after
onset, results/tbfl/compare_baselines_dev.md: simulator-trained models and controller-only source
blocks, both changed since). The campaign's runs, with the deployed models and switch drop rules,
give the numbers reported in the paper.

| Baseline | Published mitigation | Earlier testbed, A2, s11 |
|---|---|---|
| FTMaster | attack rules below 25 % of the table early, then blocked | 10.0 % (5 runs) |
| FTOP | average Pm 20.66 %, table usage 50.56 % | 33.9 % (1 run) |
| FloRa | attack rules below 35 % of the table early, then detected | 39.1 % (1 run) |
| DMS-BTT | average attack flow share 5.25 %, peak 52.32 %, table utilisation 48.69 % | 18.7 % (5 runs) |
| FTODefender | Pm 38.74 % (REFUSE) reduced to 22.23 % | no run |

rDefender has no learned model; its paper's headline is Packet-In loss (none under its HA flood, where
SAIA, TableGuard and LtRFT lose Packet-Ins) and malicious rules limited on attacked ports; the campaign
reports its lost first packets and attack share.
