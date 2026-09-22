# W2 / RQ1 results

Split modes: **grouped** (each distinct data-plane vector in one pool; primary IID), **forward** (grouped + pools from first half of each local day, replay = second halves; primary replay), **random** (row-level; shown only to quantify duplicate leakage). Training source: stand-in pools with the Train_Test class mix (train_test_network.csv not yet available).

## grouped: IID test, val-selected configuration per family (5 seeds, mean ± sd)

| features | model | config (seed 0) | macro-F1 | novel-vector macro-F1 | MCC | attack recall | benign recall | PR-AUC | leaves |
|---|---|---|---|---|---|---|---|---|---|
| data-plane | DT | DT(depth=6,cw=balanced) | 0.9100 ± 0.0118 | 0.9093 ± 0.0119 | 0.8204 | 0.8764 | 0.9404 | 0.9288 | 61 |
| data-plane | LR | LR(C=1.0,cw=None) | 0.8599 ± 0.0031 | 0.8619 ± 0.0031 | 0.7229 | 0.7710 | 0.9321 | 0.8739 | – |
| data-plane | RF | RF(depth=16,cw=balanced) | 0.8936 ± 0.0021 | 0.8926 ± 0.0021 | 0.7967 | 0.9555 | 0.8659 | 0.9633 | – |
| data-plane | HGB | HGB(leaves=127,cw=balanced) | 0.9253 ± 0.0131 | 0.9247 ± 0.0132 | 0.8523 | 0.8691 | 0.9678 | 0.9605 | – |
| full (Zeek) | DT | DT(depth=6,cw=balanced) | 0.9186 ± 0.0009 | 0.9181 ± 0.0009 | 0.8377 | 0.8775 | 0.9527 | 0.9388 | 63 |
| full (Zeek) | LR | LR(C=0.1,cw=None) | 0.8794 ± 0.0035 | 0.8793 ± 0.0035 | 0.7594 | 0.8240 | 0.9271 | 0.9068 | – |
| full (Zeek) | RF | RF(depth=16,cw=balanced) | 0.8937 ± 0.0022 | 0.8930 ± 0.0022 | 0.7971 | 0.9562 | 0.8657 | 0.9658 | – |
| full (Zeek) | HGB | HGB(leaves=127,cw=None) | 0.9347 ± 0.0014 | 0.9343 ± 0.0014 | 0.8729 | 0.8649 | 0.9844 | 0.9540 | – |
| data-plane + ports | DT | DT(depth=12,cw=None) | 0.9679 ± 0.0025 | 0.9679 ± 0.0025 | 0.9371 | 0.9929 | 0.9570 | 0.9078 | 485 |
| data-plane + ports | LR | LR(C=0.01,cw=None) | 0.8945 ± 0.0010 | 0.8944 ± 0.0010 | 0.7890 | 0.8564 | 0.9294 | 0.9147 | – |
| data-plane + ports | RF | RF(depth=None,cw=balanced) | 0.9913 ± 0.0011 | 0.9913 ± 0.0011 | 0.9827 | 0.9831 | 0.9971 | 0.9985 | – |
| data-plane + ports | HGB | HGB(leaves=127,cw=balanced) | 0.9789 ± 0.0086 | 0.9789 ± 0.0086 | 0.9584 | 0.9915 | 0.9741 | 0.9987 | – |
| full + ports + IPs | DT | DT(depth=12,cw=balanced) | 0.9999 ± 0.0000 | 0.9999 ± 0.0000 | 0.9998 | 0.9998 | 1.0000 | 0.9998 | 42 |
| full + ports + IPs | LR | LR(C=10.0,cw=balanced) | 0.9816 ± 0.0006 | 0.9816 ± 0.0006 | 0.9636 | 0.9955 | 0.9757 | 0.9547 | – |
| full + ports + IPs | RF | RF(depth=8,cw=balanced) | 0.9993 ± 0.0001 | 0.9993 ± 0.0001 | 0.9985 | 0.9995 | 0.9992 | 1.0000 | – |
| full + ports + IPs | HGB | HGB(leaves=127,cw=balanced) | 0.9999 ± 0.0000 | 0.9999 ± 0.0000 | 0.9999 | 0.9999 | 1.0000 | 1.0000 | – |

Test vectors also present in training, and Bayes accuracy ceiling (label conflicts on identical vectors):

| fs       |   test_seen_frac |   bayes_ceiling_test |
|:---------|-----------------:|---------------------:|
| dp       |           0.0104 |               0.9584 |
| dp_ports |           0.0005 |               1      |
| full     |           0.0082 |               0.9585 |
| full_ids |           0.0004 |               1      |

### grouped: DT depth sweep, data-plane features

| depth | leaves | macro-F1 | MCC | attack recall | benign recall |
|---|---|---|---|---|---|
| 4 | 16 | 0.7515 ± 0.0130 | 0.5338 | 0.8546 | 0.7009 |
| 6 | 61 | 0.9100 ± 0.0118 | 0.8204 | 0.8764 | 0.9404 |
| 8 | 200 | 0.9219 ± 0.0122 | 0.8448 | 0.8777 | 0.9574 |
| 10 | 439 | 0.9289 ± 0.0117 | 0.8593 | 0.8764 | 0.9686 |
| 12 | 689 | 0.9246 ± 0.0214 | 0.8532 | 0.8937 | 0.9512 |
| 16 | 1153 | 0.8897 ± 0.0079 | 0.7910 | 0.9605 | 0.8566 |
| None | 1944 | 0.8985 ± 0.0234 | 0.8060 | 0.9382 | 0.8838 |

### grouped: 10-class DT (IID test, mean over seeds)

- **data-plane** (depth=12,cw=None): macro-F1 0.7835 ± 0.0113, balanced acc 0.7868; recall: normal 0.984, backdoor 0.994, ddos 0.907, dos 0.997, injection 0.951, mitm 0.427, password 0.987, ransomware 0.008, scanning 0.639, xss 0.975
- **full (Zeek)** (depth=12,cw=None): macro-F1 0.7873 ± 0.0110, balanced acc 0.7901; recall: normal 0.984, backdoor 0.994, ddos 0.911, dos 0.998, injection 0.952, mitm 0.453, password 0.987, ransomware 0.008, scanning 0.639, xss 0.975

### grouped: chronological replay (seed-0 models; 95% block bootstrap over local hours)

| features | model | config | flows | macro-F1 [95% CI] | MCC | attack recall | benign recall |
|---|---|---|---|---|---|---|---|
| – | always-attack | – | 21,718,055 | 0.4954 | 0.0000 | 1.0000 | 0.0000 |
| data-plane | DT | 12 | 21,718,055 | 0.7768 [0.7016, 0.8752] | 0.6082 | 0.9744 | 0.9385 |
| data-plane | DT | 8 | 21,718,055 | 0.7240 [0.6398, 0.8611] | 0.5342 | 0.9600 | 0.9634 |
| data-plane | DT | None | 21,718,055 | 0.7838 [0.7046, 0.8913] | 0.6160 | 0.9765 | 0.9238 |
| data-plane | HGB | best | 21,718,055 | 0.7315 [0.6432, 0.8798] | 0.5461 | 0.9619 | 0.9673 |
| data-plane | LR | best | 21,718,055 | 0.5631 [0.5314, 0.6065] | 0.2400 | 0.8944 | 0.6792 |
| data-plane | RF | best | 21,718,055 | 0.8031 [0.7181, 0.9197] | 0.6508 | 0.9790 | 0.9489 |
| data-plane + ports | DT | 12 | 21,718,055 | 0.8727 [0.7992, 0.9456] | 0.7649 | 0.9889 | 0.9602 |
| data-plane + ports | DT | 8 | 21,718,055 | 0.8117 [0.7468, 0.8810] | 0.6512 | 0.9833 | 0.8775 |
| data-plane + ports | DT | None | 21,718,055 | 0.8873 [0.8422, 0.9258] | 0.7791 | 0.9932 | 0.8701 |
| data-plane + ports | HGB | best | 21,718,055 | 0.8743 [0.8199, 0.9236] | 0.7558 | 0.9918 | 0.8704 |
| data-plane + ports | LR | best | 21,718,055 | 0.6319 [0.5895, 0.6874] | 0.3890 | 0.9237 | 0.9132 |
| data-plane + ports | RF | best | 21,718,055 | 0.8084 [0.7320, 0.8968] | 0.6434 | 0.9834 | 0.8630 |
| full (Zeek) | DT | 12 | 21,718,055 | 0.7773 [0.7018, 0.8760] | 0.6077 | 0.9748 | 0.9322 |
| full (Zeek) | DT | 8 | 21,718,055 | 0.7918 [0.7114, 0.8975] | 0.6357 | 0.9764 | 0.9606 |
| full (Zeek) | DT | None | 21,718,055 | 0.7851 [0.7057, 0.8943] | 0.6168 | 0.9770 | 0.9179 |
| full (Zeek) | HGB | best | 21,718,055 | 0.7345 [0.6451, 0.8836] | 0.5545 | 0.9618 | 0.9853 |
| full (Zeek) | LR | best | 21,718,055 | 0.7019 [0.6507, 0.7616] | 0.4928 | 0.9553 | 0.9228 |
| full (Zeek) | RF | best | 21,718,055 | 0.8056 [0.7200, 0.9239] | 0.6542 | 0.9796 | 0.9460 |
| full + ports + IPs | DT | 12 | 21,718,055 | 0.9656 [0.9189, 0.9989] | 0.9333 | 0.9973 | 1.0000 |
| full + ports + IPs | DT | 8 | 21,718,055 | 0.9579 [0.9030, 0.9990] | 0.9191 | 0.9966 | 1.0000 |
| full + ports + IPs | DT | None | 21,718,055 | 0.9656 [0.9189, 0.9989] | 0.9333 | 0.9973 | 1.0000 |
| full + ports + IPs | HGB | best | 21,718,055 | 0.9743 [0.9388, 0.9992] | 0.9498 | 0.9980 | 1.0000 |
| full + ports + IPs | LR | best | 21,718,055 | 0.8495 [0.7697, 0.9396] | 0.7309 | 0.9850 | 0.9846 |
| full + ports + IPs | RF | best | 21,718,055 | 0.9949 [0.9885, 0.9991] | 0.9899 | 0.9996 | 0.9991 |

Data-plane DT replay macro-F1 across seeds: depth 10: 0.7629 ± 0.0318, depth 12: 0.7505 ± 0.0286, depth 16: 0.7525 ± 0.0307, depth 4: 0.6638 ± 0.0332, depth 6: 0.7677 ± 0.0044, depth 8: 0.7380 ± 0.0277, depth None: 0.7485 ± 0.0302

### grouped: replay per-type recall, data-plane features (DT = depth 6; seed 0)

| type       |     DT |    HGB |     LR |     RF |   train_rows |      replay_rows |
|:-----------|-------:|-------:|-------:|-------:|-------------:|-----------------:|
| backdoor   | 0.9996 | 0.9992 | 0.9996 | 0.9992 |        20000 | 480116           |
| ddos       | 0.9793 | 0.9864 | 0.8477 | 0.9872 |        20000 |      6.13701e+06 |
| dos        | 0.9984 | 0.9988 | 0.9533 | 0.9993 |        20000 |      3.34733e+06 |
| injection  | 0.9809 | 0.9969 | 0.743  | 0.9974 |        20000 | 424659           |
| mitm       | 0.5655 | 0.6717 | 0.0854 | 0.6945 |          375 |    527           |
| normal     | 0.9607 | 0.9673 | 0.6792 | 0.9489 |       284110 | 397757           |
| password   | 0.9912 | 0.9991 | 0.9832 | 0.9987 |        20000 |      1.69057e+06 |
| ransomware | 0.2857 | 0.1583 | 0.0832 | 0.7953 |        20000 |  46987           |
| scanning   | 0.9501 | 0.9064 | 0.9513 | 0.9524 |        20000 |      7.11216e+06 |
| xss        | 0.9861 | 0.9924 | 0.6953 | 0.9931 |        20000 |      2.08094e+06 |

### grouped: IID per-type recall reweighted to the replay's class mix (seed 0)

| features | model | reweighted macro-F1 | IID macro-F1 |
|---|---|---|---|
| data-plane | DT | 0.7336 | 0.9237 |
| data-plane | LR | 0.5951 | 0.8615 |
| data-plane | RF | 0.7444 | 0.8952 |
| data-plane | HGB | 0.7485 | 0.9116 |
| full (Zeek) | DT | 0.7418 | 0.9201 |
| full (Zeek) | LR | 0.7060 | 0.8815 |
| full (Zeek) | RF | 0.7510 | 0.8952 |
| full (Zeek) | HGB | 0.7588 | 0.9359 |

## forward: IID test, val-selected configuration per family (5 seeds, mean ± sd)

| features | model | config (seed 0) | macro-F1 | novel-vector macro-F1 | MCC | attack recall | benign recall | PR-AUC | leaves |
|---|---|---|---|---|---|---|---|---|---|
| data-plane | DT | DT(depth=12,cw=None) | 0.8797 ± 0.0384 | 0.8792 ± 0.0385 | 0.7681 | 0.9060 | 0.8557 | 0.8281 | 525 |
| data-plane | LR | LR(C=0.1,cw=None) | 0.8849 ± 0.0012 | 0.8845 ± 0.0013 | 0.7764 | 0.8196 | 0.9481 | 0.9253 | – |
| data-plane | RF | RF(depth=None,cw=balanced) | 0.8726 ± 0.0089 | 0.8721 ± 0.0090 | 0.7536 | 0.9398 | 0.8096 | 0.8187 | – |
| data-plane | HGB | HGB(leaves=127,cw=None) | 0.9240 ± 0.0040 | 0.9237 ± 0.0040 | 0.8535 | 0.8673 | 0.9784 | 0.9601 | – |
| full (Zeek) | DT | DT(depth=6,cw=balanced) | 0.7988 ± 0.0012 | 0.7982 ± 0.0012 | 0.6137 | 0.8962 | 0.7089 | 0.6736 | 57 |
| full (Zeek) | LR | LR(C=1.0,cw=None) | 0.9082 ± 0.0006 | 0.9081 ± 0.0007 | 0.8194 | 0.8651 | 0.9498 | 0.9553 | – |
| full (Zeek) | RF | RF(depth=16,cw=None) | 0.8730 ± 0.0089 | 0.8728 ± 0.0090 | 0.7546 | 0.9410 | 0.8094 | 0.9658 | – |
| full (Zeek) | HGB | HGB(leaves=127,cw=None) | 0.9225 ± 0.0033 | 0.9223 ± 0.0033 | 0.8500 | 0.8680 | 0.9748 | 0.9608 | – |
| data-plane + ports | DT | DT(depth=16,cw=balanced) | 0.8900 ± 0.0180 | 0.8900 ± 0.0180 | 0.7956 | 0.9817 | 0.8046 | 0.7808 | 612 |
| data-plane + ports | LR | LR(C=1.0,cw=balanced) | 0.8882 ± 0.0009 | 0.8882 ± 0.0009 | 0.7766 | 0.8729 | 0.9029 | 0.9514 | – |
| data-plane + ports | RF | RF(depth=None,cw=balanced) | 0.9868 ± 0.0046 | 0.9868 ± 0.0046 | 0.9738 | 0.9781 | 0.9951 | 0.9982 | – |
| data-plane + ports | HGB | HGB(leaves=31,cw=balanced) | 0.9749 ± 0.0232 | 0.9748 ± 0.0232 | 0.9510 | 0.9897 | 0.9609 | 0.9983 | – |
| full + ports + IPs | DT | DT(depth=8,cw=None) | 0.9999 ± 0.0001 | 0.9999 ± 0.0001 | 0.9998 | 0.9998 | 1.0000 | 0.9999 | 18 |
| full + ports + IPs | LR | LR(C=1.0,cw=balanced) | 0.9856 ± 0.0006 | 0.9856 ± 0.0006 | 0.9712 | 0.9913 | 0.9802 | 0.9875 | – |
| full + ports + IPs | RF | RF(depth=None,cw=None) | 0.9997 ± 0.0000 | 0.9997 ± 0.0000 | 0.9995 | 0.9995 | 1.0000 | 1.0000 | – |
| full + ports + IPs | HGB | HGB(leaves=31,cw=None) | 0.9999 ± 0.0001 | 0.9999 ± 0.0001 | 0.9998 | 0.9998 | 1.0000 | 1.0000 | – |

Test vectors also present in training, and Bayes accuracy ceiling (label conflicts on identical vectors):

| fs       |   test_seen_frac |   bayes_ceiling_test |
|:---------|-----------------:|---------------------:|
| dp       |           0.0049 |               0.9438 |
| dp_ports |           0.0003 |               1      |
| full     |           0.0033 |               0.944  |
| full_ids |           0.0002 |               1      |

### forward: DT depth sweep, data-plane features

| depth | leaves | macro-F1 | MCC | attack recall | benign recall |
|---|---|---|---|---|---|
| 4 | 16 | 0.7964 ± 0.0014 | 0.6110 | 0.9006 | 0.7005 |
| 6 | 60 | 0.8053 ± 0.0013 | 0.6291 | 0.9095 | 0.7094 |
| 8 | 173 | 0.8108 ± 0.0128 | 0.6363 | 0.9030 | 0.7255 |
| 10 | 339 | 0.9031 ± 0.0571 | 0.8118 | 0.8789 | 0.9268 |
| 12 | 525 | 0.8797 ± 0.0384 | 0.7681 | 0.9060 | 0.8557 |
| 16 | 883 | 0.8487 ± 0.0462 | 0.7205 | 0.9572 | 0.7495 |
| None | 1105 | 0.8657 ± 0.0093 | 0.7452 | 0.9519 | 0.7855 |

### forward: 10-class DT (IID test, mean over seeds)

- **data-plane** (depth=16,cw=balanced): macro-F1 0.6853 ± 0.0126, balanced acc 0.8317; recall: normal 0.595, backdoor 0.998, ddos 0.910, dos 0.992, injection 0.000, mitm 0.635, password 0.990, ransomware 0.703, scanning 0.707, xss 0.955
- **full (Zeek)** (depth=12,cw=None): macro-F1 0.6942 ± 0.0032, balanced acc 0.8311; recall: normal 0.598, backdoor 0.996, ddos 0.929, dos 0.995, injection 0.000, mitm 0.588, password 0.979, ransomware 0.700, scanning 0.745, xss 0.949

### forward: chronological replay (seed-0 models; 95% block bootstrap over local hours)

| features | model | config | flows | macro-F1 [95% CI] | MCC | attack recall | benign recall |
|---|---|---|---|---|---|---|---|
| – | always-attack | – | 11,169,131 | 0.4911 | 0.0000 | 1.0000 | 0.0000 |
| data-plane | DT | 12 | 11,169,131 | 0.8510 [0.7608, 0.9354] | 0.7278 | 0.9743 | 0.9515 |
| data-plane | DT | 8 | 11,169,131 | 0.8331 [0.7482, 0.9161] | 0.6907 | 0.9727 | 0.9056 |
| data-plane | DT | None | 11,169,131 | 0.8445 [0.7559, 0.9323] | 0.7175 | 0.9725 | 0.9538 |
| data-plane | HGB | best | 11,169,131 | 0.8334 [0.7471, 0.9212] | 0.7015 | 0.9689 | 0.9629 |
| data-plane | LR | best | 11,169,131 | 0.6496 [0.5898, 0.7205] | 0.3778 | 0.9100 | 0.7395 |
| data-plane | RF | best | 11,169,131 | 0.8528 [0.7627, 0.9360] | 0.7310 | 0.9747 | 0.9531 |
| data-plane + ports | DT | 12 | 11,169,131 | 0.8806 [0.8362, 0.9221] | 0.7665 | 0.9860 | 0.8674 |
| data-plane + ports | DT | 8 | 11,169,131 | 0.8566 [0.8103, 0.9025] | 0.7203 | 0.9829 | 0.8357 |
| data-plane + ports | DT | None | 11,169,131 | 0.8892 [0.8485, 0.9272] | 0.7835 | 0.9869 | 0.8825 |
| data-plane + ports | HGB | best | 11,169,131 | 0.9288 [0.9016, 0.9505] | 0.8593 | 0.9924 | 0.9181 |
| data-plane + ports | LR | best | 11,169,131 | 0.7115 [0.6401, 0.7943] | 0.5025 | 0.9283 | 0.8926 |
| data-plane + ports | RF | best | 11,169,131 | 0.9151 [0.8821, 0.9432] | 0.8333 | 0.9902 | 0.9130 |
| full (Zeek) | DT | 12 | 11,169,131 | 0.8343 [0.7466, 0.9233] | 0.7006 | 0.9700 | 0.9502 |
| full (Zeek) | DT | 8 | 11,169,131 | 0.8250 [0.7413, 0.9067] | 0.6733 | 0.9722 | 0.8817 |
| full (Zeek) | DT | None | 11,169,131 | 0.8320 [0.7451, 0.9242] | 0.6929 | 0.9709 | 0.9280 |
| full (Zeek) | HGB | best | 11,169,131 | 0.8410 [0.7535, 0.9273] | 0.7137 | 0.9710 | 0.9631 |
| full (Zeek) | LR | best | 11,169,131 | 0.7626 [0.6916, 0.8312] | 0.5485 | 0.9644 | 0.7466 |
| full (Zeek) | RF | best | 11,169,131 | 0.8561 [0.7651, 0.9399] | 0.7361 | 0.9755 | 0.9519 |
| full + ports + IPs | DT | 12 | 11,169,131 | 0.9269 [0.8562, 0.9910] | 0.8632 | 0.9882 | 0.9998 |
| full + ports + IPs | DT | 8 | 11,169,131 | 0.9269 [0.8562, 0.9910] | 0.8632 | 0.9882 | 0.9998 |
| full + ports + IPs | DT | None | 11,169,131 | 0.9269 [0.8562, 0.9910] | 0.8632 | 0.9882 | 0.9998 |
| full + ports + IPs | HGB | best | 11,169,131 | 0.9952 [0.9847, 0.9999] | 0.9905 | 0.9993 | 0.9999 |
| full + ports + IPs | LR | best | 11,169,131 | 0.9250 [0.8862, 0.9599] | 0.8586 | 0.9883 | 0.9891 |
| full + ports + IPs | RF | best | 11,169,131 | 0.9880 [0.9730, 0.9987] | 0.9763 | 0.9983 | 0.9998 |

Data-plane DT replay macro-F1 across seeds: depth 10: 0.8308 ± 0.0260, depth 12: 0.8347 ± 0.0268, depth 16: 0.8339 ± 0.0266, depth 4: 0.7602 ± 0.0295, depth 6: 0.8207 ± 0.0263, depth 8: 0.8199 ± 0.0249, depth None: 0.8223 ± 0.0288

### forward: replay per-type recall, data-plane features (DT = depth 12; seed 0)

| type       |     DT |    HGB |     LR |     RF |   train_rows |      replay_rows |
|:-----------|-------:|-------:|-------:|-------:|-------------:|-----------------:|
| backdoor   | 0.9988 | 0.9986 | 0.9998 | 0.9988 |        20000 | 298913           |
| ddos       | 0.9944 | 0.9947 | 0.9882 | 0.9954 |        20000 |      3.04734e+06 |
| dos        | 0.9998 | 0.9997 | 0.9673 | 0.9998 |        20000 |      1.45306e+06 |
| injection  | 0.7253 | 0.6409 | 0.6635 | 0.7414 |            0 | 452659           |
| mitm       | 0.5079 | 0.3986 | 0.1182 | 0.418  |          172 |    567           |
| normal     | 0.9515 | 0.9629 | 0.7395 | 0.9531 |       144104 | 392018           |
| password   | 0.9912 | 0.9937 | 0.9643 | 0.9906 |        20000 |  13259           |
| ransomware | 0.8178 | 0.3078 | 0.1351 | 0.6921 |        15515 |  29361           |
| scanning   | 0.9652 | 0.963  | 0.964  | 0.9636 |        20000 |      3.56927e+06 |
| xss        | 0.9975 | 0.9986 | 0.6972 | 0.999  |        20000 |      1.91269e+06 |

### forward: IID per-type recall reweighted to the replay's class mix (seed 0)

| features | model | reweighted macro-F1 | IID macro-F1 |
|---|---|---|---|
| data-plane | DT | 0.7611 | 0.8586 |
| data-plane | LR | 0.6703 | 0.8843 |
| data-plane | RF | 0.7430 | 0.8765 |
| data-plane | HGB | 0.7830 | 0.9279 |
| full (Zeek) | DT | 0.7823 | 0.7977 |
| full (Zeek) | LR | 0.7817 | 0.9082 |
| full (Zeek) | RF | 0.7487 | 0.8766 |
| full (Zeek) | HGB | 0.7834 | 0.9209 |

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
| DT | 0.9665 | 0.9100 | +0.0565 |
| LR | 0.8662 | 0.8599 | +0.0064 |
| RF | 0.9674 | 0.8936 | +0.0739 |
| HGB | 0.9623 | 0.9253 | +0.0370 |
