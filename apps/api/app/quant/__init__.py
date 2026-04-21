"""Quant demo workload — synthetic OHLCV data, alpha features, LightGBM training, inference.

The pipeline is structured to mirror a real quant research loop and to be
swappable with a true data-vendor feed later:

    bronze (GCS/MinIO)  ─►  silver (daily_prices_silver)  ─►  gold (features_gold)
                                                                       │
                                                          training ─►  MLflow registry
                                                                       │
                                                           inference ─►  /serving/<model>/predict
"""
