# W4 / RQ4 results: leaf-cache policies

Data-plane DTs from W2 (stand-in training pools), replayed in file order. K = resident leaf entries. Mean over 5 seeds. Demand policies start cold. Belady is the offline optimum for any policy that changes at most one entry per miss; the hourly oracle preloads each hour's top-K (not deployable). 'Best static in hindsight' is C(K) from W3: the K most frequent leaves of the whole stream.

## grouped / full stream / depth 10: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.719 | 0.875 | 0.961 | 0.987 | 0.995 | 0.998 | 1.000 | 0.0130 |
| decayed LFU, γ=0.99 | 0.580 | 0.802 | 0.937 | 0.980 | 0.992 | 0.997 | 0.999 | 0.0392 |
| decayed LFU, γ=0.999 | 0.580 | 0.793 | 0.932 | 0.979 | 0.992 | 0.997 | 0.999 | 0.0414 |
| LRU | 0.580 | 0.785 | 0.928 | 0.978 | 0.992 | 0.997 | 0.999 | 0.0447 |
| hourly oracle (top-K per hour) | 0.537 | 0.756 | 0.912 | 0.971 | 0.988 | 0.996 | 0.999 | 0.0000 |
| LFU | 0.580 | 0.645 | 0.742 | 0.887 | 0.959 | 0.982 | 0.993 | 0.2263 |
| static top-K from first hour | 0.004 | 0.005 | 0.006 | 0.007 | 0.007 | 0.007 | 0.007 | 0.0000 |
| best static table in hindsight, C(K) | 0.256 | 0.401 | 0.638 | 0.826 | 0.935 | 0.974 | 0.990 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.139, K=2: 0.073, K=4: 0.024, K=8: 0.007, K=16: 0.003, K=32: 0.001, K=64: 0.000

## grouped / full stream / depth None: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.695 | 0.843 | 0.927 | 0.963 | 0.980 | 0.990 | 0.995 | 0.0330 |
| decayed LFU, γ=0.99 | 0.553 | 0.765 | 0.892 | 0.946 | 0.969 | 0.982 | 0.990 | 0.1077 |
| decayed LFU, γ=0.999 | 0.553 | 0.753 | 0.879 | 0.941 | 0.969 | 0.984 | 0.991 | 0.1176 |
| LRU | 0.553 | 0.741 | 0.875 | 0.935 | 0.966 | 0.982 | 0.990 | 0.1292 |
| hourly oracle (top-K per hour) | 0.514 | 0.715 | 0.849 | 0.926 | 0.959 | 0.978 | 0.989 | 0.0000 |
| LFU | 0.553 | 0.609 | 0.695 | 0.784 | 0.880 | 0.937 | 0.963 | 0.4318 |
| static top-K from first hour | 0.004 | 0.005 | 0.006 | 0.007 | 0.007 | 0.007 | 0.007 | 0.0000 |
| best static table in hindsight, C(K) | 0.236 | 0.359 | 0.556 | 0.716 | 0.842 | 0.920 | 0.955 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.142, K=2: 0.079, K=4: 0.035, K=8: 0.016, K=16: 0.011, K=32: 0.008, K=64: 0.005

## grouped / benign stream / depth 10: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.583 | 0.734 | 0.850 | 0.929 | 0.973 | 0.991 | 0.997 | 0.0797 |
| decayed LFU, γ=0.99 | 0.422 | 0.628 | 0.778 | 0.888 | 0.953 | 0.984 | 0.995 | 0.2242 |
| decayed LFU, γ=0.999 | 0.422 | 0.614 | 0.759 | 0.875 | 0.949 | 0.984 | 0.995 | 0.2501 |
| LRU | 0.422 | 0.593 | 0.750 | 0.870 | 0.949 | 0.983 | 0.995 | 0.2609 |
| hourly oracle (top-K per hour) | 0.470 | 0.605 | 0.749 | 0.862 | 0.942 | 0.985 | 0.998 | 0.0013 |
| LFU | 0.422 | 0.485 | 0.563 | 0.681 | 0.834 | 0.930 | 0.981 | 0.6384 |
| static top-K from first hour | 0.214 | 0.256 | 0.318 | 0.371 | 0.376 | 0.376 | 0.376 | 0.0000 |
| best static table in hindsight, C(K) | 0.214 | 0.302 | 0.415 | 0.584 | 0.786 | 0.909 | 0.975 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.161, K=2: 0.106, K=4: 0.072, K=8: 0.042, K=16: 0.021, K=32: 0.008, K=64: 0.002

## grouped / benign stream / depth None: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.567 | 0.707 | 0.817 | 0.895 | 0.946 | 0.974 | 0.988 | 0.1040 |
| decayed LFU, γ=0.99 | 0.405 | 0.602 | 0.743 | 0.846 | 0.913 | 0.954 | 0.978 | 0.3085 |
| decayed LFU, γ=0.999 | 0.405 | 0.589 | 0.724 | 0.831 | 0.909 | 0.956 | 0.980 | 0.3371 |
| LRU | 0.405 | 0.562 | 0.708 | 0.817 | 0.902 | 0.952 | 0.978 | 0.3651 |
| hourly oracle (top-K per hour) | 0.463 | 0.588 | 0.717 | 0.822 | 0.900 | 0.953 | 0.984 | 0.0015 |
| LFU | 0.405 | 0.469 | 0.546 | 0.658 | 0.783 | 0.877 | 0.938 | 0.6838 |
| static top-K from first hour | 0.214 | 0.256 | 0.318 | 0.366 | 0.371 | 0.371 | 0.371 | 0.0000 |
| best static table in hindsight, C(K) | 0.214 | 0.302 | 0.413 | 0.570 | 0.735 | 0.856 | 0.929 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.162, K=2: 0.106, K=4: 0.074, K=8: 0.049, K=16: 0.033, K=32: 0.020, K=64: 0.010

## forward / full stream / depth 10: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.735 | 0.896 | 0.963 | 0.987 | 0.995 | 0.998 | 1.000 | 0.0150 |
| decayed LFU, γ=0.99 | 0.599 | 0.836 | 0.943 | 0.978 | 0.992 | 0.997 | 0.999 | 0.0431 |
| decayed LFU, γ=0.999 | 0.599 | 0.825 | 0.935 | 0.976 | 0.991 | 0.997 | 0.999 | 0.0481 |
| LRU | 0.599 | 0.818 | 0.935 | 0.976 | 0.991 | 0.997 | 0.999 | 0.0482 |
| hourly oracle (top-K per hour) | 0.554 | 0.782 | 0.913 | 0.965 | 0.985 | 0.996 | 0.999 | 0.0000 |
| LFU | 0.599 | 0.670 | 0.754 | 0.892 | 0.951 | 0.976 | 0.992 | 0.2160 |
| static top-K from first hour | 0.005 | 0.008 | 0.012 | 0.014 | 0.061 | 0.106 | 0.106 | 0.0000 |
| best static table in hindsight, C(K) | 0.265 | 0.388 | 0.597 | 0.831 | 0.926 | 0.966 | 0.989 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.136, K=2: 0.060, K=4: 0.020, K=8: 0.008, K=16: 0.004, K=32: 0.001, K=64: 0.000

## forward / full stream / depth None: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.704 | 0.860 | 0.942 | 0.974 | 0.988 | 0.994 | 0.998 | 0.0269 |
| decayed LFU, γ=0.99 | 0.563 | 0.789 | 0.912 | 0.960 | 0.980 | 0.990 | 0.995 | 0.0797 |
| decayed LFU, γ=0.999 | 0.563 | 0.770 | 0.895 | 0.953 | 0.977 | 0.990 | 0.995 | 0.0935 |
| LRU | 0.563 | 0.765 | 0.898 | 0.954 | 0.978 | 0.990 | 0.995 | 0.0913 |
| hourly oracle (top-K per hour) | 0.496 | 0.714 | 0.860 | 0.936 | 0.965 | 0.984 | 0.994 | 0.0000 |
| LFU | 0.563 | 0.634 | 0.705 | 0.814 | 0.904 | 0.948 | 0.973 | 0.3711 |
| static top-K from first hour | 0.005 | 0.008 | 0.012 | 0.014 | 0.058 | 0.062 | 0.077 | 0.0000 |
| best static table in hindsight, C(K) | 0.265 | 0.372 | 0.553 | 0.742 | 0.865 | 0.931 | 0.966 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.141, K=2: 0.072, K=4: 0.030, K=8: 0.014, K=16: 0.008, K=32: 0.004, K=64: 0.002

## forward / benign stream / depth 10: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.545 | 0.727 | 0.861 | 0.943 | 0.981 | 0.994 | 0.998 | 0.0664 |
| decayed LFU, γ=0.99 | 0.379 | 0.604 | 0.787 | 0.909 | 0.966 | 0.989 | 0.997 | 0.1822 |
| decayed LFU, γ=0.999 | 0.379 | 0.589 | 0.767 | 0.895 | 0.964 | 0.990 | 0.997 | 0.2090 |
| LRU | 0.379 | 0.578 | 0.767 | 0.894 | 0.963 | 0.989 | 0.997 | 0.2126 |
| hourly oracle (top-K per hour) | 0.402 | 0.570 | 0.740 | 0.872 | 0.952 | 0.988 | 0.999 | 0.0007 |
| LFU | 0.379 | 0.449 | 0.559 | 0.712 | 0.853 | 0.950 | 0.988 | 0.5763 |
| static top-K from first hour | 0.131 | 0.236 | 0.335 | 0.379 | 0.456 | 0.512 | 0.512 | 0.0000 |
| best static table in hindsight, C(K) | 0.131 | 0.239 | 0.420 | 0.630 | 0.806 | 0.928 | 0.983 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.166, K=2: 0.123, K=4: 0.074, K=8: 0.034, K=16: 0.014, K=32: 0.005, K=64: 0.001

## forward / benign stream / depth None: hit rate by K (churn = table writes per flow at K=8)

| policy | K=1 | K=2 | K=4 | K=8 | K=16 | K=32 | K=64 | churn K=8 |
|---|---|---|---|---|---|---|---|---|
| Belady (offline optimum) | 0.525 | 0.698 | 0.829 | 0.913 | 0.962 | 0.983 | 0.992 | 0.0905 |
| decayed LFU, γ=0.99 | 0.358 | 0.575 | 0.748 | 0.871 | 0.938 | 0.970 | 0.986 | 0.2587 |
| decayed LFU, γ=0.999 | 0.358 | 0.562 | 0.729 | 0.856 | 0.934 | 0.970 | 0.986 | 0.2880 |
| LRU | 0.358 | 0.542 | 0.722 | 0.848 | 0.928 | 0.969 | 0.985 | 0.3030 |
| hourly oracle (top-K per hour) | 0.394 | 0.549 | 0.708 | 0.836 | 0.920 | 0.964 | 0.988 | 0.0007 |
| LFU | 0.358 | 0.428 | 0.534 | 0.674 | 0.814 | 0.913 | 0.959 | 0.6523 |
| static top-K from first hour | 0.131 | 0.235 | 0.329 | 0.396 | 0.430 | 0.478 | 0.502 | 0.0000 |
| best static table in hindsight, C(K) | 0.131 | 0.237 | 0.415 | 0.599 | 0.769 | 0.891 | 0.951 | 0 |

Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: K=1: 0.167, K=2: 0.123, K=4: 0.081, K=8: 0.043, K=16: 0.024, K=32: 0.013, K=64: 0.007

## Adaptation after each local-day (attack-phase) boundary, measured in flows

Grouped split, depth 10, K=8, seeds 0-2 (mean). flows_to_recover = flows until a 500-flow bin reaches the day's steady hit rate minus 0.05; excess misses = misses in the first 10,000 flows beyond the steady-state rate. Days with fewer than 20,000 flows in the stream are skipped. Static placement is excluded (it never adapts).

### full stream: flows to recover

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-03 |        0 |           0 |     0 |     0 |
| 2019-04-04 |        0 |           0 |   167 |   333 |
| 2019-04-23 |        0 |           0 |     0 |  4000 |
| 2019-04-24 |        0 |           0 |     0 |     0 |
| 2019-04-25 |        0 |           0 |     0 |     0 |
| 2019-04-26 |      500 |         500 |   500 |  1833 |
| 2019-04-27 |      833 |        5333 |  5500 | 11500 |
| 2019-04-28 |     1500 |        1500 |  1500 |  4000 |
| 2019-04-29 |        0 |           0 |     0 |     0 |

### full stream: excess misses in the first 10,000 flows

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-03 |      -56 |         -80 |  -112 |   -18 |
| 2019-04-04 |       75 |         102 |   120 |   161 |
| 2019-04-23 |      -10 |          -7 |   -18 |  1338 |
| 2019-04-24 |      -40 |         -66 |   -72 |  -108 |
| 2019-04-25 |      202 |         346 |   333 |   241 |
| 2019-04-26 |      -39 |         -46 |   -98 |   462 |
| 2019-04-27 |      386 |         557 |   765 |  2067 |
| 2019-04-28 |       47 |         100 |    60 |   679 |
| 2019-04-29 |        5 |          21 |    20 |    22 |

### benign stream: flows to recover

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-03 |        0 |           0 |     0 |     0 |
| 2019-04-04 |        0 |           0 |   167 |   333 |
| 2019-04-25 |     2333 |        3000 |  3000 |  3167 |
| 2019-04-26 |        0 |           0 |     0 | 10167 |
| 2019-04-27 |        0 |         167 |     0 |     0 |
| 2019-04-28 |      167 |        1000 |  1000 |  2333 |

### benign stream: excess misses in the first 10,000 flows

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-03 |      -56 |         -80 |  -112 |   -18 |
| 2019-04-04 |       75 |         102 |   120 |   161 |
| 2019-04-25 |      146 |         288 |   131 |    48 |
| 2019-04-26 |       -8 |         -28 |   -46 |  2848 |
| 2019-04-27 |      221 |         454 |   369 |   618 |
| 2019-04-28 |     -338 |        -573 |  -658 |  -817 |

