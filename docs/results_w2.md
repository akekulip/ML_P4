# W2 / RQ1 results

Split modes: **grouped** (each distinct data-plane vector in one pool; primary IID), **forward** (grouped + pools from first half of each local day, replay = second halves; primary replay), **random** (row-level; shown only to quantify duplicate leakage). Training source: stand-in pools with the Train_Test class mix (train_test_network.csv not yet available).

## grouped: IID test, val-selected configuration per family (5 seeds, mean ± sd)

| features | model | config (seed 0) | macro-F1 | novel-vector macro-F1 | MCC | attack recall | benign recall | PR-AUC | leaves |
|---|---|---|---|---|---|---|---|---|---|
| data-plane | DT | DT(depth=None,cw=None) | 0.9182 ± 0.0398 | 0.9176 ± 0.0402 | 0.8417 | 0.8622 | 0.9612 | 0.9056 | 1880 |
| data-plane | LR | LR(C=0.1,cw=None) | 0.7799 ± 0.1387 | 0.7806 ± 0.1401 | 0.5908 | 0.7925 | 0.7882 | 0.8685 | – |
| data-plane | RF | RF(depth=None,cw=None) | 0.9189 ± 0.0408 | 0.9183 ± 0.0412 | 0.8433 | 0.8611 | 0.9630 | 0.9468 | – |
| data-plane | HGB | HGB(leaves=127,cw=None) | 0.9090 ± 0.0166 | 0.9083 ± 0.0167 | 0.8250 | 0.8391 | 0.9625 | 0.9384 | – |
| full (Zeek) | DT | DT(depth=None,cw=balanced) | 0.9162 ± 0.0390 | 0.9157 ± 0.0394 | 0.8373 | 0.8643 | 0.9569 | 0.9000 | 1811 |
| full (Zeek) | LR | LR(C=1.0,cw=None) | 0.7954 ± 0.1388 | 0.7948 ± 0.1395 | 0.6259 | 0.8385 | 0.7830 | 0.8948 | – |
| full (Zeek) | RF | RF(depth=None,cw=None) | 0.9181 ± 0.0403 | 0.9176 ± 0.0406 | 0.8415 | 0.8615 | 0.9615 | 0.9449 | – |
| full (Zeek) | HGB | HGB(leaves=127,cw=None) | 0.9095 ± 0.0184 | 0.9090 ± 0.0186 | 0.8259 | 0.8411 | 0.9620 | 0.9394 | – |
| data-plane + ports | DT | DT(depth=None,cw=balanced) | 0.8858 ± 0.0841 | 0.8858 ± 0.0841 | 0.7952 | 0.9494 | 0.8551 | 0.7908 | 1204 |
| data-plane + ports | LR | LR(C=0.01,cw=None) | 0.8724 ± 0.0378 | 0.8724 ± 0.0378 | 0.7519 | 0.8416 | 0.9044 | 0.9159 | – |
| data-plane + ports | RF | RF(depth=16,cw=None) | 0.9180 ± 0.0608 | 0.9180 ± 0.0609 | 0.8489 | 0.9586 | 0.9000 | 0.9864 | – |
| data-plane + ports | HGB | HGB(leaves=127,cw=balanced) | 0.9207 ± 0.0795 | 0.9207 ± 0.0795 | 0.8547 | 0.9750 | 0.8938 | 0.9727 | – |
| full + ports + IPs | DT | DT(depth=8,cw=balanced) | 0.9999 ± 0.0001 | 0.9999 ± 0.0001 | 0.9998 | 0.9999 | 0.9999 | 0.9997 | 34 |
| full + ports + IPs | LR | LR(C=1.0,cw=None) | 0.9629 ± 0.0277 | 0.9629 ± 0.0278 | 0.9278 | 0.9670 | 0.9644 | 0.9654 | – |
| full + ports + IPs | RF | RF(depth=None,cw=None) | 0.9999 ± 0.0001 | 0.9999 ± 0.0001 | 0.9998 | 0.9998 | 1.0000 | 1.0000 | – |
| full + ports + IPs | HGB | HGB(leaves=31,cw=balanced) | 0.9999 ± 0.0001 | 0.9999 ± 0.0001 | 0.9998 | 0.9998 | 1.0000 | 1.0000 | – |

Test vectors also present in training, and Bayes accuracy ceiling (label conflicts on identical vectors):

| fs       |   test_seen_frac |   bayes_ceiling_test |
|:---------|-----------------:|---------------------:|
| dp       |           0.01   |               0.9699 |
| dp_ports |           0.0005 |               1      |
| full     |           0.0078 |               0.97   |
| full_ids |           0.0004 |               1      |

### grouped: DT depth sweep, data-plane features

| depth | leaves | macro-F1 | MCC | attack recall | benign recall |
|---|---|---|---|---|---|
| 4 | 16 | 0.8361 ± 0.0400 | 0.6964 | 0.8331 | 0.8539 |
| 6 | 58 | 0.8816 ± 0.0648 | 0.7718 | 0.8173 | 0.9342 |
| 8 | 176 | 0.8758 ± 0.0797 | 0.7612 | 0.8687 | 0.8910 |
| 10 | 395 | 0.9039 ± 0.0560 | 0.8141 | 0.8367 | 0.9561 |
| 12 | 650 | 0.9213 ± 0.0266 | 0.8501 | 0.8377 | 0.9824 |
| 16 | 1160 | 0.9127 ± 0.0392 | 0.8317 | 0.8530 | 0.9590 |
| None | 1880 | 0.9182 ± 0.0398 | 0.8417 | 0.8622 | 0.9612 |

### grouped: 10-class DT (IID test, mean over seeds)

- **data-plane** (depth=None,cw=balanced): macro-F1 0.7944 ± 0.0544, balanced acc 0.7990; recall: normal 0.934, backdoor 0.973, ddos 0.893, dos 0.997, injection 0.958, mitm 0.592, password 0.947, ransomware 0.277, scanning 0.447, xss 0.973
- **full (Zeek)** (depth=12,cw=None): macro-F1 0.7933 ± 0.0509, balanced acc 0.7906; recall: normal 0.904, backdoor 0.970, ddos 0.893, dos 0.997, injection 0.953, mitm 0.589, password 0.949, ransomware 0.233, scanning 0.446, xss 0.972

### grouped: chronological replay (seed-0 models; 95% block bootstrap over local hours)

| features | model | config | flows | macro-F1 [95% CI] | MCC | attack recall | benign recall |
|---|---|---|---|---|---|---|---|
| – | always-attack | – | 21,715,873 | 0.4954 | 0.0000 | 1.0000 | 0.0000 |
| data-plane | DT | 12 | 21,715,873 | 0.5668 [0.4918, 0.7974] | 0.3067 | 0.8642 | 0.9543 |
| data-plane | DT | 8 | 21,715,873 | 0.5511 [0.4759, 0.7850] | 0.2798 | 0.8487 | 0.9266 |
| data-plane | DT | None | 21,715,873 | 0.5553 [0.4780, 0.7980] | 0.2948 | 0.8490 | 0.9688 |
| data-plane | HGB | best | 21,715,873 | 0.5572 [0.4787, 0.8033] | 0.3024 | 0.8486 | 0.9921 |
| data-plane | LR | best | 21,715,873 | 0.6001 [0.5651, 0.6497] | 0.3332 | 0.9060 | 0.8658 |
| data-plane | RF | best | 21,715,873 | 0.5560 [0.4781, 0.8052] | 0.2958 | 0.8497 | 0.9699 |
| data-plane + ports | DT | 12 | 21,715,873 | 0.7080 [0.6155, 0.9016] | 0.5176 | 0.9529 | 0.9954 |
| data-plane + ports | DT | 8 | 21,715,873 | 0.6407 [0.5637, 0.8155] | 0.4150 | 0.9237 | 0.9739 |
| data-plane + ports | DT | None | 21,715,873 | 0.7049 [0.6126, 0.9036] | 0.5094 | 0.9528 | 0.9789 |
| data-plane + ports | HGB | best | 21,715,873 | 0.8626 [0.7934, 0.9328] | 0.7541 | 0.9864 | 0.9973 |
| data-plane + ports | LR | best | 21,715,873 | 0.5479 [0.4987, 0.6265] | 0.2697 | 0.8479 | 0.9000 |
| data-plane + ports | RF | best | 21,715,873 | 0.6686 [0.5794, 0.8935] | 0.4575 | 0.9377 | 0.9837 |
| full (Zeek) | DT | 12 | 21,715,873 | 0.5671 [0.4920, 0.8011] | 0.3068 | 0.8648 | 0.9525 |
| full (Zeek) | DT | 8 | 21,715,873 | 0.5430 [0.4719, 0.7304] | 0.2758 | 0.8347 | 0.9551 |
| full (Zeek) | DT | None | 21,715,873 | 0.5653 [0.4915, 0.7994] | 0.3006 | 0.8648 | 0.9354 |
| full (Zeek) | HGB | best | 21,715,873 | 0.5574 [0.4788, 0.8052] | 0.3027 | 0.8489 | 0.9921 |
| full (Zeek) | LR | best | 21,715,873 | 0.7310 [0.6692, 0.8087] | 0.5222 | 0.9679 | 0.8578 |
| full (Zeek) | RF | best | 21,715,873 | 0.5562 [0.4783, 0.8066] | 0.2961 | 0.8500 | 0.9698 |
| full + ports + IPs | DT | 12 | 21,715,873 | 0.9979 [0.9950, 0.9996] | 0.9958 | 0.9998 | 0.9999 |
| full + ports + IPs | DT | 8 | 21,715,873 | 0.9983 [0.9950, 0.9998] | 0.9965 | 0.9999 | 0.9999 |
| full + ports + IPs | DT | None | 21,715,873 | 0.9980 [0.9944, 0.9997] | 0.9961 | 0.9999 | 1.0000 |
| full + ports + IPs | HGB | best | 21,715,873 | 0.9906 [0.9752, 0.9996] | 0.9813 | 0.9993 | 1.0000 |
| full + ports + IPs | LR | best | 21,715,873 | 0.9498 [0.9325, 0.9656] | 0.9021 | 0.9966 | 0.9718 |
| full + ports + IPs | RF | best | 21,715,873 | 0.9989 [0.9975, 0.9998] | 0.9979 | 0.9999 | 1.0000 |

Data-plane DT replay macro-F1 across seeds: depth 10: 0.6832 ± 0.1039, depth 12: 0.6626 ± 0.1110, depth 16: 0.6611 ± 0.1131, depth 4: 0.6318 ± 0.1772, depth 6: 0.6015 ± 0.1242, depth 8: 0.6688 ± 0.1087, depth None: 0.6603 ± 0.1128

### grouped: replay per-type recall, data-plane features (DT = depth None; seed 0)

| type       |     DT |    HGB |     LR |     RF |   train_rows |      replay_rows |
|:-----------|-------:|-------:|-------:|-------:|-------------:|-----------------:|
| backdoor   | 0.9992 | 0.9992 | 0.9996 | 0.9993 |        20000 | 480116           |
| ddos       | 0.9782 | 0.9811 | 0.8769 | 0.9804 |        20000 |      6.13701e+06 |
| dos        | 0.999  | 0.9991 | 0.9553 | 0.9992 |        20000 |      3.34733e+06 |
| injection  | 0.9936 | 0.9959 | 0.7663 | 0.9962 |        20000 | 424659           |
| mitm       | 0.7362 | 0.6945 | 0.1139 | 0.6964 |          375 |    527           |
| normal     | 0.9688 | 0.9921 | 0.8658 | 0.9699 |       284110 | 397757           |
| password   | 0.9404 | 0.9473 | 0.9919 | 0.9427 |        20000 |      1.69057e+06 |
| ransomware | 0.7842 | 0.0939 | 0.6645 | 0.7365 |        20000 |  44805           |
| scanning   | 0.5859 | 0.5844 | 0.9519 | 0.5848 |        20000 |      7.11216e+06 |
| xss        | 0.9892 | 0.9906 | 0.6977 | 0.9912 |        20000 |      2.08094e+06 |

### grouped: IID per-type recall reweighted to the replay's class mix (seed 0)

| features | model | reweighted macro-F1 | IID macro-F1 |
|---|---|---|---|
| data-plane | DT | 0.4656 | 0.8562 |
| data-plane | LR | 0.6036 | 0.7999 |
| data-plane | RF | 0.4652 | 0.8545 |
| data-plane | HGB | 0.4719 | 0.8957 |
| full (Zeek) | DT | 0.4657 | 0.8559 |
| full (Zeek) | LR | 0.7921 | 0.8148 |
| full (Zeek) | RF | 0.4651 | 0.8539 |
| full (Zeek) | HGB | 0.4721 | 0.8947 |

## forward: IID test, val-selected configuration per family (5 seeds, mean ± sd)

| features | model | config (seed 0) | macro-F1 | novel-vector macro-F1 | MCC | attack recall | benign recall | PR-AUC | leaves |
|---|---|---|---|---|---|---|---|---|---|
| data-plane | DT | DT(depth=None,cw=None) | 0.8801 ± 0.0837 | 0.8795 ± 0.0843 | 0.7698 | 0.8720 | 0.8895 | 0.8929 | 1080 |
| data-plane | LR | LR(C=0.1,cw=None) | 0.7695 ± 0.1256 | 0.7685 ± 0.1262 | 0.5745 | 0.8263 | 0.7288 | 0.9127 | – |
| data-plane | RF | RF(depth=None,cw=None) | 0.8889 ± 0.0909 | 0.8884 ± 0.0916 | 0.7867 | 0.8669 | 0.9114 | 0.9512 | – |
| data-plane | HGB | HGB(leaves=127,cw=balanced) | 0.9078 ± 0.0361 | 0.9075 ± 0.0362 | 0.8246 | 0.8674 | 0.9475 | 0.9702 | – |
| full (Zeek) | DT | DT(depth=16,cw=None) | 0.8745 ± 0.0920 | 0.8741 ± 0.0924 | 0.7550 | 0.8641 | 0.8854 | 0.8917 | 704 |
| full (Zeek) | LR | LR(C=10.0,cw=None) | 0.7989 ± 0.1255 | 0.7984 ± 0.1259 | 0.6371 | 0.8712 | 0.7438 | 0.9395 | – |
| full (Zeek) | RF | RF(depth=None,cw=balanced) | 0.8872 ± 0.0920 | 0.8869 ± 0.0925 | 0.7836 | 0.8673 | 0.9078 | 0.9502 | – |
| full (Zeek) | HGB | HGB(leaves=127,cw=balanced) | 0.9079 ± 0.0362 | 0.9077 ± 0.0363 | 0.8247 | 0.8678 | 0.9473 | 0.9704 | – |
| data-plane + ports | DT | DT(depth=None,cw=None) | 0.8617 ± 0.0645 | 0.8616 ± 0.0645 | 0.7437 | 0.9311 | 0.7996 | 0.8013 | 810 |
| data-plane + ports | LR | LR(C=0.01,cw=None) | 0.8573 ± 0.0517 | 0.8573 ± 0.0518 | 0.7263 | 0.8629 | 0.8545 | 0.9446 | – |
| data-plane + ports | RF | RF(depth=None,cw=None) | 0.9102 ± 0.0395 | 0.9102 ± 0.0395 | 0.8320 | 0.9405 | 0.8829 | 0.9938 | – |
| data-plane + ports | HGB | HGB(leaves=31,cw=balanced) | 0.8970 ± 0.0959 | 0.8970 ± 0.0959 | 0.8188 | 0.9729 | 0.8298 | 0.9892 | – |
| full + ports + IPs | DT | DT(depth=8,cw=None) | 0.9999 ± 0.0001 | 0.9999 ± 0.0001 | 0.9998 | 0.9999 | 1.0000 | 0.9999 | 22 |
| full + ports + IPs | LR | LR(C=10.0,cw=balanced) | 0.9605 ± 0.0268 | 0.9605 ± 0.0268 | 0.9235 | 0.9666 | 0.9550 | 0.9780 | – |
| full + ports + IPs | RF | RF(depth=16,cw=None) | 0.9999 ± 0.0001 | 0.9999 ± 0.0001 | 0.9998 | 0.9998 | 1.0000 | 1.0000 | – |
| full + ports + IPs | HGB | HGB(leaves=31,cw=balanced) | 0.9999 ± 0.0001 | 0.9999 ± 0.0001 | 0.9998 | 0.9999 | 1.0000 | 1.0000 | – |

Test vectors also present in training, and Bayes accuracy ceiling (label conflicts on identical vectors):

| fs       |   test_seen_frac |   bayes_ceiling_test |
|:---------|-----------------:|---------------------:|
| dp       |           0.0048 |               0.9595 |
| dp_ports |           0.0002 |               1      |
| full     |           0.0031 |               0.9596 |
| full_ids |           0.0001 |               1      |

### forward: DT depth sweep, data-plane features

| depth | leaves | macro-F1 | MCC | attack recall | benign recall |
|---|---|---|---|---|---|
| 4 | 16 | 0.7838 ± 0.0962 | 0.6138 | 0.8474 | 0.7388 |
| 6 | 58 | 0.8684 ± 0.0751 | 0.7461 | 0.8761 | 0.8627 |
| 8 | 165 | 0.8746 ± 0.0726 | 0.7586 | 0.8774 | 0.8736 |
| 10 | 313 | 0.8839 ± 0.0589 | 0.7729 | 0.8472 | 0.9197 |
| 12 | 479 | 0.8970 ± 0.0612 | 0.8006 | 0.8421 | 0.9503 |
| 16 | 803 | 0.8766 ± 0.0817 | 0.7623 | 0.8635 | 0.8907 |
| None | 1080 | 0.8801 ± 0.0837 | 0.7698 | 0.8720 | 0.8895 |

### forward: 10-class DT (IID test, mean over seeds)

- **data-plane** (depth=None,cw=balanced): macro-F1 0.7116 ± 0.0638, balanced acc 0.8125; recall: normal 0.785, backdoor 0.991, ddos 0.923, dos 0.998, injection 0.000, mitm 0.582, password 0.950, ransomware 0.370, scanning 0.742, xss 0.971
- **full (Zeek)** (depth=None,cw=balanced): macro-F1 0.7239 ± 0.0601, balanced acc 0.8154; recall: normal 0.789, backdoor 0.991, ddos 0.924, dos 0.998, injection 0.000, mitm 0.600, password 0.950, ransomware 0.374, scanning 0.741, xss 0.972

### forward: chronological replay (seed-0 models; 95% block bootstrap over local hours)

| features | model | config | flows | macro-F1 [95% CI] | MCC | attack recall | benign recall |
|---|---|---|---|---|---|---|---|
| – | always-attack | – | 11,169,131 | 0.4911 | 0.0000 | 1.0000 | 0.0000 |
| data-plane | DT | 12 | 11,169,131 | 0.6357 [0.5133, 0.8711] | 0.4157 | 0.8667 | 0.9666 |
| data-plane | DT | 8 | 11,169,131 | 0.6281 [0.5093, 0.8505] | 0.3979 | 0.8641 | 0.9363 |
| data-plane | DT | None | 11,169,131 | 0.6244 [0.5072, 0.8398] | 0.3990 | 0.8573 | 0.9598 |
| data-plane | HGB | best | 11,169,131 | 0.8273 [0.7406, 0.9181] | 0.6976 | 0.9651 | 0.9924 |
| data-plane | LR | best | 11,169,131 | 0.6720 [0.6102, 0.7495] | 0.4242 | 0.9167 | 0.8002 |
| data-plane | RF | best | 11,169,131 | 0.6369 [0.5136, 0.8795] | 0.4165 | 0.8682 | 0.9634 |
| data-plane + ports | DT | 12 | 11,169,131 | 0.6685 [0.5455, 0.9195] | 0.4610 | 0.8926 | 0.9707 |
| data-plane + ports | DT | 8 | 11,169,131 | 0.6661 [0.5488, 0.8866] | 0.4602 | 0.8896 | 0.9806 |
| data-plane + ports | DT | None | 11,169,131 | 0.6665 [0.5445, 0.9109] | 0.4586 | 0.8909 | 0.9723 |
| data-plane + ports | HGB | best | 11,169,131 | 0.8649 [0.7603, 0.9560] | 0.7561 | 0.9756 | 0.9854 |
| data-plane + ports | LR | best | 11,169,131 | 0.6974 [0.6319, 0.7786] | 0.4750 | 0.9241 | 0.8622 |
| data-plane + ports | RF | best | 11,169,131 | 0.7999 [0.6698, 0.9591] | 0.6529 | 0.9574 | 0.9796 |
| full (Zeek) | DT | 12 | 11,169,131 | 0.6369 [0.5136, 0.8791] | 0.4153 | 0.8689 | 0.9585 |
| full (Zeek) | DT | 8 | 11,169,131 | 0.6249 [0.5076, 0.8489] | 0.3868 | 0.8651 | 0.9094 |
| full (Zeek) | DT | None | 11,169,131 | 0.6273 [0.5086, 0.8493] | 0.4024 | 0.8603 | 0.9582 |
| full (Zeek) | HGB | best | 11,169,131 | 0.8367 [0.7492, 0.9250] | 0.7124 | 0.9678 | 0.9926 |
| full (Zeek) | LR | best | 11,169,131 | 0.7983 [0.7224, 0.8722] | 0.6223 | 0.9679 | 0.8374 |
| full (Zeek) | RF | best | 11,169,131 | 0.6374 [0.5138, 0.8816] | 0.4169 | 0.8688 | 0.9625 |
| full + ports + IPs | DT | 12 | 11,169,131 | 0.9954 [0.9848, 1.0000] | 0.9909 | 0.9994 | 0.9998 |
| full + ports + IPs | DT | 8 | 11,169,131 | 0.9954 [0.9848, 1.0000] | 0.9909 | 0.9994 | 0.9998 |
| full + ports + IPs | DT | None | 11,169,131 | 0.9954 [0.9848, 1.0000] | 0.9909 | 0.9994 | 0.9998 |
| full + ports + IPs | HGB | best | 11,169,131 | 0.9952 [0.9847, 0.9999] | 0.9905 | 0.9993 | 0.9998 |
| full + ports + IPs | LR | best | 11,169,131 | 0.9471 [0.9205, 0.9707] | 0.8977 | 0.9926 | 0.9815 |
| full + ports + IPs | RF | best | 11,169,131 | 0.9995 [0.9990, 0.9999] | 0.9990 | 0.9999 | 0.9998 |

Data-plane DT replay macro-F1 across seeds: depth 10: 0.7687 ± 0.1107, depth 12: 0.7698 ± 0.1104, depth 16: 0.7589 ± 0.1052, depth 4: 0.7101 ± 0.1292, depth 6: 0.7956 ± 0.0973, depth 8: 0.8053 ± 0.0994, depth None: 0.7570 ± 0.1057

### forward: replay per-type recall, data-plane features (DT = depth None; seed 0)

| type       |     DT |    HGB |     LR |     RF |   train_rows |      replay_rows |
|:-----------|-------:|-------:|-------:|-------:|-------------:|-----------------:|
| backdoor   | 0.9984 | 0.9984 | 0.9998 | 0.9988 |        20000 | 298913           |
| ddos       | 0.9904 | 0.9913 | 0.9876 | 0.991  |        20000 |      3.04734e+06 |
| dos        | 0.9999 | 0.9999 | 0.9782 | 0.9999 |        20000 |      1.45306e+06 |
| injection  | 0.511  | 0.5759 | 0.7287 | 0.749  |            0 | 452659           |
| mitm       | 0.4691 | 0.4815 | 0.1993 | 0.4409 |          172 |    567           |
| normal     | 0.9598 | 0.9924 | 0.8002 | 0.9634 |       144104 | 392018           |
| password   | 0.9814 | 0.9835 | 0.9658 | 0.9831 |        20000 |  13259           |
| ransomware | 0.5799 | 0.1674 | 0.5438 | 0.5894 |        14100 |  29361           |
| scanning   | 0.6456 | 0.964  | 0.9647 | 0.6461 |        20000 |      3.56927e+06 |
| xss        | 0.9954 | 0.9983 | 0.7042 | 0.9987 |        20000 |      1.91269e+06 |

### forward: IID per-type recall reweighted to the replay's class mix (seed 0)

| features | model | reweighted macro-F1 | IID macro-F1 |
|---|---|---|---|
| data-plane | DT | 0.4687 | 0.7396 |
| data-plane | LR | 0.6430 | 0.7177 |
| data-plane | RF | 0.4694 | 0.7405 |
| data-plane | HGB | 0.9276 | 0.9344 |
| full (Zeek) | DT | 0.4684 | 0.7346 |
| full (Zeek) | LR | 0.7833 | 0.7495 |
| full (Zeek) | RF | 0.4689 | 0.7357 |
| full (Zeek) | HGB | 0.9324 | 0.9349 |

## random: IID test, val-selected configuration per family (3 seeds, mean ± sd)

| features | model | config (seed 0) | macro-F1 | novel-vector macro-F1 | MCC | attack recall | benign recall | PR-AUC | leaves |
|---|---|---|---|---|---|---|---|---|---|
| data-plane | DT | DT(depth=None,cw=balanced) | 0.9665 ± 0.0004 | 0.9926 ± 0.0005 | 0.9332 | 0.9680 | 0.9695 | 0.9860 | 2088 |
| data-plane | LR | LR(C=0.01,cw=None) | 0.8662 ± 0.0008 | 0.8400 ± 0.0003 | 0.7326 | 0.8380 | 0.8976 | 0.8960 | – |
| data-plane | RF | RF(depth=None,cw=None) | 0.9674 ± 0.0005 | 0.9948 ± 0.0006 | 0.9350 | 0.9689 | 0.9703 | 0.9923 | – |
| data-plane | HGB | HGB(leaves=127,cw=None) | 0.9623 ± 0.0005 | 0.9945 ± 0.0005 | 0.9248 | 0.9604 | 0.9678 | 0.9919 | – |
| full (Zeek) | DT | DT(depth=None,cw=balanced) | 0.9668 ± 0.0004 | 0.9931 ± 0.0006 | 0.9337 | 0.9685 | 0.9696 | 0.9864 | 1956 |
| full (Zeek) | LR | LR(C=0.01,cw=None) | 0.8822 ± 0.0009 | 0.8638 ± 0.0013 | 0.7668 | 0.8944 | 0.8863 | 0.9147 | – |
| full (Zeek) | RF | RF(depth=None,cw=None) | 0.9676 ± 0.0005 | 0.9951 ± 0.0006 | 0.9354 | 0.9692 | 0.9704 | 0.9924 | – |
| full (Zeek) | HGB | HGB(leaves=127,cw=None) | 0.9625 ± 0.0005 | 0.9948 ± 0.0005 | 0.9252 | 0.9609 | 0.9678 | 0.9920 | – |
| data-plane + ports | DT | DT(depth=None,cw=balanced) | 0.9977 ± 0.0002 | 0.9972 ± 0.0002 | 0.9953 | 0.9969 | 0.9984 | 0.9954 | 1250 |
| data-plane + ports | LR | LR(C=10.0,cw=balanced) | 0.8854 ± 0.0020 | 0.8960 ± 0.0006 | 0.7709 | 0.8648 | 0.9100 | 0.9260 | – |
| data-plane + ports | RF | RF(depth=None,cw=None) | 0.9984 ± 0.0001 | 0.9981 ± 0.0001 | 0.9968 | 0.9977 | 0.9990 | 0.9998 | – |
| data-plane + ports | HGB | HGB(leaves=127,cw=balanced) | 0.9980 ± 0.0001 | 0.9977 ± 0.0001 | 0.9959 | 0.9977 | 0.9984 | 0.9999 | – |
| full + ports + IPs | DT | DT(depth=8,cw=balanced) | 0.9999 ± 0.0000 | 0.9999 ± 0.0000 | 0.9999 | 1.0000 | 0.9999 | 0.9998 | 35 |
| full + ports + IPs | LR | LR(C=1.0,cw=balanced) | 0.9822 ± 0.0002 | 0.9873 ± 0.0001 | 0.9644 | 0.9788 | 0.9862 | 0.9695 | – |
| full + ports + IPs | RF | RF(depth=16,cw=None) | 0.9999 ± 0.0000 | 0.9999 ± 0.0000 | 0.9999 | 0.9999 | 1.0000 | 1.0000 | – |
| full + ports + IPs | HGB | HGB(leaves=31,cw=None) | 1.0000 ± 0.0000 | 0.9999 ± 0.0000 | 0.9999 | 1.0000 | 0.9999 | 1.0000 | – |

Test vectors also present in training, and Bayes accuracy ceiling (label conflicts on identical vectors):

| fs       |   test_seen_frac |   bayes_ceiling_test |
|:---------|-----------------:|---------------------:|
| dp       |           0.5929 |               0.9722 |
| dp_ports |           0.2684 |               0.9999 |
| full     |           0.5912 |               0.9722 |
| full_ids |           0.2491 |               1      |

### random: DT depth sweep, data-plane features

| depth | leaves | macro-F1 | MCC | attack recall | benign recall |
|---|---|---|---|---|---|
| 4 | 16 | 0.8634 ± 0.0007 | 0.7421 | 0.9427 | 0.8262 |
| 6 | 61 | 0.9369 ± 0.0006 | 0.8743 | 0.9378 | 0.9434 |
| 8 | 195 | 0.9516 ± 0.0006 | 0.9040 | 0.9633 | 0.9501 |
| 10 | 435 | 0.9566 ± 0.0003 | 0.9137 | 0.9644 | 0.9570 |
| 12 | 631 | 0.9605 ± 0.0004 | 0.9211 | 0.9622 | 0.9640 |
| 16 | 1165 | 0.9647 ± 0.0007 | 0.9297 | 0.9668 | 0.9676 |
| None | 2088 | 0.9665 ± 0.0004 | 0.9332 | 0.9680 | 0.9695 |

### random: 10-class DT (IID test, mean over seeds)

- **data-plane** (depth=16,cw=None): macro-F1 0.9026 ± 0.0047, balanced acc 0.9106; recall: normal 0.969, backdoor 0.979, ddos 0.951, dos 0.994, injection 0.963, mitm 0.640, password 0.983, ransomware 0.777, scanning 0.883, xss 0.968
- **full (Zeek)** (depth=16,cw=None): macro-F1 0.9022 ± 0.0013, balanced acc 0.9091; recall: normal 0.970, backdoor 0.979, ddos 0.951, dos 0.995, injection 0.964, mitm 0.627, password 0.983, ransomware 0.772, scanning 0.883, xss 0.967

### random: chronological replay (seed-0 models; 95% block bootstrap over local hours)

| features | model | config | flows | macro-F1 [95% CI] | MCC | attack recall | benign recall |
|---|---|---|---|---|---|---|---|
| – | always-attack | – | 21,715,873 | 0.4954 | 0.0000 | 1.0000 | 0.0000 |
| data-plane | DT | 12 | 21,715,873 | 0.8074 [0.7208, 0.9201] | 0.6602 | 0.9792 | 0.9627 |
| data-plane | DT | 8 | 21,715,873 | 0.7956 [0.7131, 0.9032] | 0.6396 | 0.9776 | 0.9507 |
| data-plane | DT | None | 21,715,873 | 0.8011 [0.7171, 0.9109] | 0.6519 | 0.9778 | 0.9702 |
| data-plane | HGB | best | 21,715,873 | 0.8059 [0.7198, 0.9185] | 0.6591 | 0.9787 | 0.9687 |
| data-plane | LR | best | 21,715,873 | 0.6027 [0.5661, 0.6550] | 0.3441 | 0.9047 | 0.8983 |
| data-plane | RF | best | 21,715,873 | 0.8064 [0.7210, 0.9180] | 0.6603 | 0.9787 | 0.9710 |
| data-plane + ports | DT | 12 | 21,715,873 | 0.9265 [0.8939, 0.9545] | 0.8620 | 0.9938 | 0.9969 |
| data-plane + ports | DT | 8 | 21,715,873 | 0.7703 [0.6978, 0.8612] | 0.6085 | 0.9707 | 0.9878 |
| data-plane + ports | DT | None | 21,715,873 | 0.9536 [0.9309, 0.9720] | 0.9110 | 0.9963 | 0.9984 |
| data-plane + ports | HGB | best | 21,715,873 | 0.9632 [0.9422, 0.9793] | 0.9287 | 0.9971 | 0.9985 |
| data-plane + ports | LR | best | 21,715,873 | 0.5887 [0.5489, 0.6481] | 0.3269 | 0.8916 | 0.9092 |
| data-plane + ports | RF | best | 21,715,873 | 0.9677 [0.9508, 0.9812] | 0.9374 | 0.9975 | 0.9991 |
| full (Zeek) | DT | 12 | 21,715,873 | 0.8078 [0.7207, 0.9209] | 0.6607 | 0.9793 | 0.9628 |
| full (Zeek) | DT | 8 | 21,715,873 | 0.7956 [0.7126, 0.9032] | 0.6394 | 0.9776 | 0.9507 |
| full (Zeek) | DT | None | 21,715,873 | 0.8035 [0.7183, 0.9144] | 0.6556 | 0.9782 | 0.9704 |
| full (Zeek) | HGB | best | 21,715,873 | 0.8084 [0.7210, 0.9227] | 0.6630 | 0.9791 | 0.9689 |
| full (Zeek) | LR | best | 21,715,873 | 0.7359 [0.6738, 0.8092] | 0.5355 | 0.9676 | 0.8865 |
| full (Zeek) | RF | best | 21,715,873 | 0.8085 [0.7222, 0.9210] | 0.6635 | 0.9791 | 0.9711 |
| full + ports + IPs | DT | 12 | 21,715,873 | 0.9983 [0.9969, 0.9993] | 0.9966 | 0.9999 | 1.0000 |
| full + ports + IPs | DT | 8 | 21,715,873 | 0.9995 [0.9989, 0.9999] | 0.9990 | 1.0000 | 0.9999 |
| full + ports + IPs | DT | None | 21,715,873 | 0.9983 [0.9969, 0.9993] | 0.9966 | 0.9999 | 1.0000 |
| full + ports + IPs | HGB | best | 21,715,873 | 0.9995 [0.9986, 0.9999] | 0.9990 | 1.0000 | 1.0000 |
| full + ports + IPs | LR | best | 21,715,873 | 0.9550 [0.9374, 0.9703] | 0.9127 | 0.9967 | 0.9867 |
| full + ports + IPs | RF | best | 21,715,873 | 0.9991 [0.9978, 0.9999] | 0.9981 | 0.9999 | 1.0000 |

Data-plane DT replay macro-F1 across seeds: depth 10: 0.8038 ± 0.0015, depth 12: 0.8026 ± 0.0042, depth 16: 0.8062 ± 0.0011, depth 4: 0.7036 ± 0.0001, depth 6: 0.7758 ± 0.0062, depth 8: 0.7966 ± 0.0011, depth None: 0.8013 ± 0.0011

### random: replay per-type recall, data-plane features (DT = depth None; seed 0)

| type       |     DT |    HGB |     LR |     RF |   train_rows |      replay_rows |
|:-----------|-------:|-------:|-------:|-------:|-------------:|-----------------:|
| backdoor   | 0.9992 | 0.9991 | 0.9996 | 0.9992 |        20000 | 480116           |
| ddos       | 0.9853 | 0.9859 | 0.8745 | 0.9862 |        20000 |      6.13701e+06 |
| dos        | 0.9991 | 0.9988 | 0.9534 | 0.9992 |        20000 |      3.34733e+06 |
| injection  | 0.9942 | 0.9969 | 0.796  | 0.9965 |        20000 | 424659           |
| mitm       | 0.7154 | 0.6565 | 0.1044 | 0.6641 |          375 |    527           |
| normal     | 0.9702 | 0.9687 | 0.8983 | 0.971  |       284110 | 397757           |
| password   | 0.9919 | 0.9988 | 0.9887 | 0.992  |        20000 |      1.69057e+06 |
| ransomware | 0.8363 | 0.7617 | 0.4491 | 0.8356 |        20000 |  44805           |
| scanning   | 0.9529 | 0.9532 | 0.9517 | 0.9538 |        20000 |      7.11216e+06 |
| xss        | 0.9899 | 0.9922 | 0.6966 | 0.9927 |        20000 |      2.08094e+06 |

### random: IID per-type recall reweighted to the replay's class mix (seed 0)

| features | model | reweighted macro-F1 | IID macro-F1 |
|---|---|---|---|
| data-plane | DT | 0.8046 | 0.9663 |
| data-plane | LR | 0.6010 | 0.8656 |
| data-plane | RF | 0.8109 | 0.9670 |
| data-plane | HGB | 0.8077 | 0.9618 |
| full (Zeek) | DT | 0.8066 | 0.9664 |
| full (Zeek) | LR | 0.7308 | 0.8811 |
| full (Zeek) | RF | 0.8113 | 0.9671 |
| full (Zeek) | HGB | 0.8091 | 0.9620 |

## Duplicate leakage: random vs grouped split (IID test macro-F1, data-plane features)

| model | random | grouped | inflation |
|---|---|---|---|
| DT | 0.9665 | 0.9182 | +0.0483 |
| LR | 0.8662 | 0.7799 | +0.0864 |
| RF | 0.9674 | 0.9189 | +0.0485 |
| HGB | 0.9623 | 0.9090 | +0.0534 |
