from fraud_detection.pipelines import anomaly, supervised


def test_default_module_placeholders():
    assert anomaly.default_anomaly_baseline() == "Isolation Forest"
    assert supervised.default_supervised_baseline() == "LightGBM"
