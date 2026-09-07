import os
import sys
import json
import logging
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score

# Ensure root directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.features.feature_extractor import FeatureExtractor
from model.dataset_generator import generate_benchmark_dataset, TARGET_CLASSES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def train_and_evaluate(dataset_csv_path: Path = None) -> dict:
    """Train the multi-class ensemble fire classifier and persist artifacts."""
    Config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    if dataset_csv_path and Path(dataset_csv_path).exists():
        logger.info(f"Loading dataset from: {dataset_csv_path}")
        df = pd.read_csv(dataset_csv_path)
    else:
        logger.info("Generating synthetic benchmark satellite dataset...")
        df = generate_benchmark_dataset(num_samples_per_class=450)
        benchmark_path = Config.DATA_DIR / "fire_classification_benchmark.csv"
        df.to_csv(benchmark_path, index=False)
        logger.info(f"Saved benchmark dataset ({len(df)} samples) to {benchmark_path}")

    feature_cols = FeatureExtractor.get_model_feature_names()
    X = df[feature_cols].copy()
    y_raw = df["label"].copy()

    # Encode labels
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(y_raw)
    class_names = list(label_encoder.classes_)
    logger.info(f"Classes: {class_names}")

    # Stratified Train-Test Split (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    logger.info(f"Training instances: {len(X_train)}, Testing instances: {len(X_test)}")

    # Model Architecture: Calibrated Ensemble
    # 1. Random Forest (handles nonlinear tabular splits, spatial distance boundaries)
    rf_clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=4,
        random_state=42,
        n_jobs=1
    )

    # 2. Gradient Boosting (fine-tunes boundary probabilities and subtle thermal contrasts)
    gb_clf = GradientBoostingClassifier(
        n_estimators=80,
        learning_rate=0.1,
        max_depth=4,
        random_state=42
    )

    # Soft Voting Ensemble
    ensemble = VotingClassifier(
        estimators=[
            ('rf', rf_clf),
            ('gb', gb_clf)
        ],
        voting='soft'
    )

    # 5-Fold Stratified Cross-Validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(ensemble, X_train, y_train, cv=cv, scoring='f1_macro')
    logger.info(f"5-Fold CV Macro F1: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

    # Fit ensemble on full training set
    logger.info("Fitting ensemble classifier...")
    ensemble.fit(X_train, y_train)

    # Evaluation on Hold-Out Test Set
    y_pred = ensemble.predict(X_test)
    y_pred_proba = ensemble.predict_proba(X_test)

    accuracy = float(accuracy_score(y_test, y_pred))
    f1_macro = float(f1_score(y_test, y_pred, average='macro'))
    f1_weighted = float(f1_score(y_test, y_pred, average='weighted'))
    
    report_dict = classification_report(y_test, y_pred, target_names=class_names, output_dict=True)
    conf_matrix = confusion_matrix(y_test, y_pred).tolist()

    # Extract feature importances from the RF sub-estimator
    rf_fitted = ensemble.named_estimators_['rf']
    importances = rf_fitted.feature_importances_
    feat_importance_dict = {
        feat: round(float(imp), 4)
        for feat, imp in sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)
    }

    logger.info(f"Holdout Test Accuracy: {accuracy:.4f}")
    logger.info(f"Holdout Test F1-Macro: {f1_macro:.4f}")
    logger.info(f"Top 5 Features: {list(feat_importance_dict.items())[:5]}")

    # Build evaluation report metadata
    metrics = {
        "model_type": "Ensemble (RandomForest + GradientBoosting)",
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "accuracy": round(accuracy, 4),
        "f1_macro": round(f1_macro, 4),
        "f1_weighted": round(f1_weighted, 4),
        "cv_f1_macro_mean": round(float(cv_scores.mean()), 4),
        "cv_f1_macro_std": round(float(cv_scores.std()), 4),
        "classes": class_names,
        "classification_report": report_dict,
        "confusion_matrix": conf_matrix,
        "feature_importances": feat_importance_dict
    }

    # Save artifacts
    model_bundle = {
        "model": ensemble,
        "classes": class_names,
        "feature_names": feature_cols,
        "label_encoder": label_encoder,
        "metrics": metrics
    }

    model_path = Config.ARTIFACTS_DIR / "fire_classifier.joblib"
    metrics_path = Config.ARTIFACTS_DIR / "metrics.json"

    joblib.dump(model_bundle, model_path)
    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"Saved model artifact -> {model_path}")
    logger.info(f"Saved metrics -> {metrics_path}")
    return metrics

if __name__ == "__main__":
    train_and_evaluate()
