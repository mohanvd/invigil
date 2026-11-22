# Training run 2026-11-23

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
- Accuracy on unseen sessions: **89.6%** (DR3 near / not-near accuracy, target 80%: PASS)
- Accuracy on training data: 98.0%
  A big gap between these two means the model memorized the training sessions.

Confusion matrix (rows: true, columns: predicted)

```
          near  not_near
near       167        53
not_near    77       959
```

```
              precision    recall  f1-score   support

        near       0.68      0.76      0.72       220
    not_near       0.95      0.93      0.94      1036

    accuracy                           0.90      1256
   macro avg       0.82      0.84      0.83      1256
weighted avg       0.90      0.90      0.90      1256
```

Top features

- rssi_median: 0.407
- rssi_mean: 0.319
- rssi_max: 0.175
- rssi_min: 0.082
- rssi_std: 0.017
