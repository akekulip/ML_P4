# W4 / RQ4 results: leaf-cache policies

Data-plane DTs from W2 (stand-in training pools), replayed in file order. K = resident leaf entries. Mean over 5 seeds. Churn counts inserts + evictions per flow (a replacement = one P4Runtime DELETE + one INSERT). Demand policies start cold. Belady is the offline optimum for any policy that changes at most one entry per miss; the hourly oracle preloads each hour's top-K (not deployable). 'Best static in hindsight' is C(K) from W3: the K most frequent leaves of the whole stream.

## grouped / full stream / depth 6: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.739 | 0.905 | 0.980 | 0.997 | 1.000 | 1.000 | 1.000 | 0.0041 |
| decayed LFU, γ=0.99 | 0.603 | 0.847 | 0.966 | 0.994 | 0.999 | 1.000 | 1.000 | 0.0115 |
| decayed LFU, γ=0.999 | 0.603 | 0.839 | 0.961 | 0.994 | 0.999 | 1.000 | 1.000 | 0.0119 |
| LRU | 0.603 | 0.831 | 0.961 | 0.994 | 0.999 | 1.000 | 1.000 | 0.0128 |
| hourly oracle (top-K per hour) | 0.579 | 0.807 | 0.945 | 0.990 | 0.999 | 1.000 | 1.000 | 0.0000 |
| LFU | 0.603 | 0.738 | 0.852 | 0.963 | 0.992 | 1.000 | 1.000 | 0.0735 |
| static top-K from first hour | 0.057 | 0.093 | 0.098 | 0.103 | 0.103 | 0.103 | 0.103 | 0.0000 |
| best static table in hindsight, C(K) | 0.317 | 0.509 | 0.751 | 0.925 | 0.984 | 0.999 | 1.000 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.136, K=2: 0.058, K=4: 0.014, K=8: 0.002, K=16: 0.000, K=32: 0.000, K=64: 0.000

## grouped / full stream / depth 10: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.701 | 0.868 | 0.956 | 0.986 | 0.996 | 0.999 | 1.000 | 0.0143 |
| decayed LFU, γ=0.99 | 0.553 | 0.793 | 0.930 | 0.978 | 0.992 | 0.997 | 0.999 | 0.0433 |
| decayed LFU, γ=0.999 | 0.553 | 0.786 | 0.924 | 0.977 | 0.993 | 0.998 | 0.999 | 0.0461 |
| LRU | 0.553 | 0.773 | 0.918 | 0.975 | 0.992 | 0.997 | 0.999 | 0.0500 |
| hourly oracle (top-K per hour) | 0.525 | 0.754 | 0.904 | 0.969 | 0.989 | 0.997 | 0.999 | 0.0000 |
| LFU | 0.553 | 0.624 | 0.742 | 0.877 | 0.954 | 0.984 | 0.994 | 0.2455 |
| static top-K from first hour | 0.009 | 0.011 | 0.013 | 0.014 | 0.017 | 0.017 | 0.017 | 0.0000 |
| best static table in hindsight, C(K) | 0.202 | 0.356 | 0.580 | 0.816 | 0.925 | 0.975 | 0.992 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.148, K=2: 0.075, K=4: 0.026, K=8: 0.008, K=16: 0.003, K=32: 0.001, K=64: 0.000

## grouped / full stream / depth None: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.665 | 0.830 | 0.924 | 0.964 | 0.982 | 0.991 | 0.995 | 0.0321 |
| decayed LFU, γ=0.99 | 0.508 | 0.744 | 0.886 | 0.947 | 0.971 | 0.984 | 0.991 | 0.1059 |
| decayed LFU, γ=0.999 | 0.508 | 0.732 | 0.874 | 0.943 | 0.972 | 0.985 | 0.992 | 0.1137 |
| LRU | 0.508 | 0.718 | 0.868 | 0.936 | 0.968 | 0.983 | 0.991 | 0.1282 |
| hourly oracle (top-K per hour) | 0.480 | 0.696 | 0.841 | 0.929 | 0.962 | 0.980 | 0.990 | 0.0000 |
| LFU | 0.508 | 0.574 | 0.674 | 0.778 | 0.878 | 0.940 | 0.966 | 0.4449 |
| static top-K from first hour | 0.009 | 0.010 | 0.012 | 0.013 | 0.013 | 0.013 | 0.013 | 0.0000 |
| best static table in hindsight, C(K) | 0.204 | 0.325 | 0.516 | 0.709 | 0.837 | 0.922 | 0.958 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.157, K=2: 0.086, K=4: 0.038, K=8: 0.016, K=16: 0.011, K=32: 0.007, K=64: 0.004

## grouped / benign stream / depth 6: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.663 | 0.843 | 0.949 | 0.989 | 0.998 | 1.000 | 1.000 | 0.0137 |
| decayed LFU, γ=0.99 | 0.515 | 0.757 | 0.917 | 0.981 | 0.996 | 0.999 | 1.000 | 0.0383 |
| decayed LFU, γ=0.999 | 0.515 | 0.749 | 0.909 | 0.978 | 0.996 | 0.999 | 1.000 | 0.0442 |
| LRU | 0.515 | 0.737 | 0.906 | 0.978 | 0.996 | 0.999 | 1.000 | 0.0434 |
| hourly oracle (top-K per hour) | 0.543 | 0.744 | 0.900 | 0.974 | 0.997 | 1.000 | 1.000 | 0.0011 |
| LFU | 0.515 | 0.631 | 0.759 | 0.900 | 0.983 | 0.999 | 1.000 | 0.1990 |
| static top-K from first hour | 0.199 | 0.375 | 0.533 | 0.545 | 0.554 | 0.554 | 0.554 | 0.0000 |
| best static table in hindsight, C(K) | 0.270 | 0.401 | 0.616 | 0.841 | 0.968 | 0.998 | 1.000 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.149, K=2: 0.086, K=4: 0.032, K=8: 0.008, K=16: 0.002, K=32: 0.000, K=64: 0.000

## grouped / benign stream / depth 10: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.585 | 0.752 | 0.872 | 0.946 | 0.981 | 0.994 | 0.998 | 0.0618 |
| decayed LFU, γ=0.99 | 0.421 | 0.643 | 0.807 | 0.911 | 0.966 | 0.989 | 0.996 | 0.1774 |
| decayed LFU, γ=0.999 | 0.421 | 0.631 | 0.790 | 0.900 | 0.963 | 0.989 | 0.996 | 0.2004 |
| LRU | 0.421 | 0.611 | 0.781 | 0.900 | 0.963 | 0.988 | 0.996 | 0.2009 |
| hourly oracle (top-K per hour) | 0.464 | 0.625 | 0.779 | 0.887 | 0.958 | 0.991 | 0.999 | 0.0011 |
| LFU | 0.421 | 0.513 | 0.609 | 0.737 | 0.876 | 0.953 | 0.988 | 0.5250 |
| static top-K from first hour | 0.168 | 0.254 | 0.371 | 0.404 | 0.410 | 0.410 | 0.410 | 0.0000 |
| best static table in hindsight, C(K) | 0.187 | 0.293 | 0.442 | 0.637 | 0.837 | 0.937 | 0.984 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.164, K=2: 0.109, K=4: 0.065, K=8: 0.035, K=16: 0.015, K=32: 0.005, K=64: 0.002

## grouped / benign stream / depth None: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.554 | 0.706 | 0.819 | 0.898 | 0.948 | 0.974 | 0.988 | 0.1020 |
| decayed LFU, γ=0.99 | 0.388 | 0.597 | 0.746 | 0.848 | 0.915 | 0.955 | 0.978 | 0.3041 |
| decayed LFU, γ=0.999 | 0.388 | 0.585 | 0.728 | 0.834 | 0.912 | 0.956 | 0.980 | 0.3330 |
| LRU | 0.388 | 0.556 | 0.708 | 0.821 | 0.906 | 0.953 | 0.977 | 0.3579 |
| hourly oracle (top-K per hour) | 0.446 | 0.590 | 0.721 | 0.822 | 0.903 | 0.954 | 0.983 | 0.0015 |
| LFU | 0.388 | 0.465 | 0.547 | 0.666 | 0.796 | 0.882 | 0.943 | 0.6676 |
| static top-K from first hour | 0.167 | 0.244 | 0.322 | 0.356 | 0.366 | 0.366 | 0.366 | 0.0000 |
| best static table in hindsight, C(K) | 0.168 | 0.265 | 0.402 | 0.577 | 0.752 | 0.860 | 0.935 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.166, K=2: 0.108, K=4: 0.072, K=8: 0.050, K=16: 0.032, K=32: 0.019, K=64: 0.010

## forward / full stream / depth 6: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.747 | 0.911 | 0.981 | 0.996 | 0.999 | 1.000 | 1.000 | 0.0050 |
| decayed LFU, γ=0.99 | 0.615 | 0.857 | 0.969 | 0.993 | 0.999 | 1.000 | 1.000 | 0.0135 |
| decayed LFU, γ=0.999 | 0.615 | 0.846 | 0.965 | 0.993 | 0.999 | 1.000 | 1.000 | 0.0147 |
| LRU | 0.615 | 0.840 | 0.965 | 0.993 | 0.999 | 1.000 | 1.000 | 0.0146 |
| hourly oracle (top-K per hour) | 0.573 | 0.812 | 0.950 | 0.987 | 0.998 | 1.000 | 1.000 | 0.0000 |
| LFU | 0.615 | 0.750 | 0.862 | 0.961 | 0.989 | 0.999 | 1.000 | 0.0776 |
| static top-K from first hour | 0.011 | 0.021 | 0.025 | 0.251 | 0.426 | 0.426 | 0.426 | 0.0000 |
| best static table in hindsight, C(K) | 0.334 | 0.534 | 0.779 | 0.919 | 0.980 | 0.998 | 1.000 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.131, K=2: 0.054, K=4: 0.012, K=8: 0.003, K=16: 0.001, K=32: 0.000, K=64: 0.000

## forward / full stream / depth 10: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.721 | 0.883 | 0.964 | 0.988 | 0.996 | 0.999 | 1.000 | 0.0132 |
| decayed LFU, γ=0.99 | 0.583 | 0.817 | 0.944 | 0.981 | 0.993 | 0.998 | 0.999 | 0.0376 |
| decayed LFU, γ=0.999 | 0.583 | 0.801 | 0.934 | 0.979 | 0.993 | 0.998 | 0.999 | 0.0422 |
| LRU | 0.583 | 0.796 | 0.935 | 0.979 | 0.993 | 0.998 | 0.999 | 0.0420 |
| hourly oracle (top-K per hour) | 0.523 | 0.741 | 0.906 | 0.968 | 0.988 | 0.997 | 0.999 | 0.0000 |
| LFU | 0.583 | 0.659 | 0.744 | 0.883 | 0.959 | 0.983 | 0.995 | 0.2345 |
| static top-K from first hour | 0.007 | 0.013 | 0.016 | 0.081 | 0.116 | 0.140 | 0.140 | 0.0000 |
| best static table in hindsight, C(K) | 0.261 | 0.407 | 0.598 | 0.816 | 0.933 | 0.974 | 0.992 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.139, K=2: 0.066, K=4: 0.020, K=8: 0.007, K=16: 0.003, K=32: 0.001, K=64: 0.000

## forward / full stream / depth None: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.700 | 0.855 | 0.939 | 0.973 | 0.987 | 0.994 | 0.997 | 0.0270 |
| decayed LFU, γ=0.99 | 0.558 | 0.783 | 0.908 | 0.959 | 0.980 | 0.989 | 0.995 | 0.0813 |
| decayed LFU, γ=0.999 | 0.558 | 0.764 | 0.887 | 0.950 | 0.976 | 0.989 | 0.995 | 0.1007 |
| LRU | 0.558 | 0.756 | 0.893 | 0.953 | 0.978 | 0.989 | 0.995 | 0.0935 |
| hourly oracle (top-K per hour) | 0.515 | 0.703 | 0.840 | 0.919 | 0.962 | 0.982 | 0.993 | 0.0000 |
| LFU | 0.558 | 0.634 | 0.709 | 0.803 | 0.884 | 0.943 | 0.973 | 0.3931 |
| static top-K from first hour | 0.005 | 0.008 | 0.011 | 0.014 | 0.036 | 0.045 | 0.073 | 0.0000 |
| best static table in hindsight, C(K) | 0.261 | 0.398 | 0.577 | 0.723 | 0.836 | 0.921 | 0.964 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.142, K=2: 0.072, K=4: 0.031, K=8: 0.014, K=16: 0.008, K=32: 0.004, K=64: 0.003

## forward / benign stream / depth 6: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.641 | 0.838 | 0.950 | 0.991 | 0.998 | 1.000 | 1.000 | 0.0110 |
| decayed LFU, γ=0.99 | 0.493 | 0.742 | 0.916 | 0.985 | 0.997 | 1.000 | 1.000 | 0.0302 |
| decayed LFU, γ=0.999 | 0.493 | 0.733 | 0.909 | 0.983 | 0.997 | 1.000 | 1.000 | 0.0334 |
| LRU | 0.493 | 0.729 | 0.909 | 0.982 | 0.997 | 1.000 | 1.000 | 0.0351 |
| hourly oracle (top-K per hour) | 0.493 | 0.710 | 0.886 | 0.976 | 0.997 | 1.000 | 1.000 | 0.0005 |
| LFU | 0.493 | 0.628 | 0.773 | 0.913 | 0.988 | 0.999 | 1.000 | 0.1740 |
| static top-K from first hour | 0.165 | 0.393 | 0.507 | 0.563 | 0.622 | 0.622 | 0.622 | 0.0000 |
| best static table in hindsight, C(K) | 0.249 | 0.413 | 0.645 | 0.862 | 0.972 | 0.998 | 1.000 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.149, K=2: 0.096, K=4: 0.034, K=8: 0.006, K=16: 0.002, K=32: 0.000, K=64: 0.000

## forward / benign stream / depth 10: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.568 | 0.754 | 0.877 | 0.950 | 0.984 | 0.995 | 0.998 | 0.0568 |
| decayed LFU, γ=0.99 | 0.403 | 0.639 | 0.814 | 0.921 | 0.972 | 0.991 | 0.997 | 0.1581 |
| decayed LFU, γ=0.999 | 0.403 | 0.624 | 0.796 | 0.911 | 0.971 | 0.991 | 0.997 | 0.1786 |
| LRU | 0.403 | 0.611 | 0.794 | 0.907 | 0.970 | 0.990 | 0.997 | 0.1860 |
| hourly oracle (top-K per hour) | 0.424 | 0.610 | 0.772 | 0.892 | 0.962 | 0.991 | 0.999 | 0.0007 |
| LFU | 0.403 | 0.502 | 0.623 | 0.759 | 0.881 | 0.961 | 0.991 | 0.4823 |
| static top-K from first hour | 0.133 | 0.292 | 0.385 | 0.414 | 0.473 | 0.518 | 0.518 | 0.0000 |
| best static table in hindsight, C(K) | 0.174 | 0.297 | 0.491 | 0.691 | 0.843 | 0.944 | 0.987 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.165, K=2: 0.115, K=4: 0.064, K=8: 0.029, K=16: 0.012, K=32: 0.004, K=64: 0.001

## forward / benign stream / depth None: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.532 | 0.701 | 0.825 | 0.906 | 0.958 | 0.981 | 0.991 | 0.0986 |
| decayed LFU, γ=0.99 | 0.365 | 0.584 | 0.749 | 0.861 | 0.932 | 0.967 | 0.984 | 0.2775 |
| decayed LFU, γ=0.999 | 0.365 | 0.571 | 0.730 | 0.849 | 0.929 | 0.967 | 0.985 | 0.3021 |
| LRU | 0.365 | 0.550 | 0.721 | 0.837 | 0.920 | 0.966 | 0.984 | 0.3260 |
| hourly oracle (top-K per hour) | 0.405 | 0.562 | 0.713 | 0.830 | 0.917 | 0.962 | 0.987 | 0.0007 |
| LFU | 0.365 | 0.436 | 0.545 | 0.679 | 0.810 | 0.902 | 0.957 | 0.6417 |
| static top-K from first hour | 0.131 | 0.232 | 0.311 | 0.364 | 0.402 | 0.449 | 0.466 | 0.0000 |
| best static table in hindsight, C(K) | 0.133 | 0.241 | 0.428 | 0.611 | 0.767 | 0.879 | 0.949 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.166, K=2: 0.117, K=4: 0.076, K=8: 0.045, K=16: 0.026, K=32: 0.014, K=64: 0.008

Recovery after attack-phase changes is in docs/results_w4_recovery.md (experiments/w4_recovery.py).
