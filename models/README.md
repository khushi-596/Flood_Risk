# Model assets

## Current model: explainable weighted risk engine

`risk_engine/v1/risk_weights.yaml` is the Day 1 model. It is a human-auditable
configuration, not a trained neural network. The backend combines the five signals
defined there into a score from 0 to 1 and returns the main reasons and confidence.
This is the right hackathon starting point because it stays demonstrable when real
data is incomplete and its outcome is explainable to citizens and officials.

No GPU or Colab runtime is needed for this version.

## Later trained-model contract

Only begin GPU work after the team has a labelled dataset and a baseline to beat. Run
the training notebook in Colab, then add the exported artifact here:

```text
models/artifacts/
  flood_risk_v2.joblib
  flood_risk_v2.metadata.json
```

The metadata must record the feature schema, training-data source/date, validation
metrics, threshold, package versions, and commit SHA. Do not commit large model
weights to git; use release storage and retain this directory's contract file instead.

Suitable GPU candidates are road-image waterlogging classification, satellite-image
segmentation, or a learned rainfall forecast. The initial terrain/rain/history/drain/
report score should remain as the fallback if any trained model is unavailable.
