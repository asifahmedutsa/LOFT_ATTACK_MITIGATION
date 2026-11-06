# v5 volume block (docs/v5_plan.md, section 3)

X = 1.5 x the busiest benign host per switch in the T1A benign recordings (seeds 4150-4152); open-loop replay of the recordings (defense none).

```
switch  busiest_benign_host  vol_x
   s11                  533  799.5
   s12                  523  784.5
   s13                  531  796.5

                        run  benign_blocked  attackers_blocked
v5vol_T1A_benign_none_s4150               0                  0
v5vol_T1A_benign_none_s4151               0                  0
v5vol_T1A_benign_none_s4152               0                  0
    v5vol_T1A_A2_none_s4153               0                  2
    v5vol_T1A_A4_none_s4153               0                  2
   v5vol_T1A_E9P_none_s4153               0                  2
```

- calibration recordings: no benign host blocked: **True**
- check recordings: both attackers blocked in at least 2 of 3: **True**
- **adopt: yes**
