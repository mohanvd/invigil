# Training run 2026-11-22

Data: `data\raw`

## type

- Rows: 1256 windows from 24 sessions
- Accuracy on unseen sessions: **100.0%** (DR2 classification accuracy, target 85%: PASS)
- Accuracy on training data: 100.0%
  A big gap between these two means the model memorized the training sessions.
- Banned devices flagged as banned: 100.0%

Confusion matrix (rows: true, columns: predicted)

```
          phone  earpiece
phone       876         0
earpiece      0       380
```

```
              precision    recall  f1-score   support

       phone       1.00      1.00      1.00       876
    earpiece       1.00      1.00      1.00       380

    accuracy                           1.00      1256
   macro avg       1.00      1.00      1.00      1256
weighted avg       1.00      1.00      1.00      1256
```

Top features

- mfr_oraimo: 0.273
- n_adv: 0.195
- adv_interval_ms: 0.183
- mfr_apple: 0.076
- mfr_none: 0.047
- spec_active: 0.043
- spec_adv_frac: 0.037
- spec_longest_run: 0.023
- spec_sweeps: 0.023
- spec_scattered: 0.022

## band

- Rows: 1256 windows from 24 sessions
- Accuracy on unseen sessions: **59.7%** (DR3 distance band accuracy, target 80%: FAIL)
- Accuracy on training data: 96.9%
  A big gap between these two means the model memorized the training sessions.

Confusion matrix (rows: true, columns: predicted)

```
      near  mid  far
near    98  121    1
mid     85  317  196
far      1  102  335
```

```
              precision    recall  f1-score   support

        near       0.53      0.45      0.49       220
         mid       0.59      0.53      0.56       598
         far       0.63      0.76      0.69       438

    accuracy                           0.60      1256
   macro avg       0.58      0.58      0.58      1256
weighted avg       0.59      0.60      0.59      1256
```

Top features

- rssi_median: 0.173
- rssi_mean: 0.162
- rssi_max: 0.156
- spec_active: 0.117
- rssi_min: 0.096
- spec_mean_frac: 0.077
- spec_adv_frac: 0.044
- adv_interval_ms: 0.042
- n_adv: 0.027
- spec_longest_run: 0.027
