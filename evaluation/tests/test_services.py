import pytest
from sklearn.datasets import load_iris, make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC

from evaluation.services import evaluate_model

TOL = 0.001


def test_binary_model_matches_sklearn_reference():
    X, y = make_classification(n_samples=200, random_state=0)
    X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=0)
    model = LogisticRegression(max_iter=500).fit(X_train, y_train)

    m = evaluate_model(model, X_test, y_test)

    assert m['accuracy'] == pytest.approx(accuracy_score(y_test, model.predict(X_test)), abs=TOL)
    assert m['f1'] == pytest.approx(f1_score(y_test, model.predict(X_test)), abs=TOL)
    assert m['roc_auc'] == pytest.approx(
        roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]), abs=TOL
    )


def test_multiclass_model_uses_macro_average():
    X, y = load_iris(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=1, stratify=y)
    model = LogisticRegression(max_iter=500).fit(X_train, y_train)

    m = evaluate_model(model, X_test, y_test)

    expected = f1_score(y_test, model.predict(X_test), average='macro')
    assert m['f1'] == pytest.approx(expected, abs=TOL)
    assert m['roc_auc'] is not None


def test_model_without_probabilities_has_no_roc_auc():
    X, y = make_classification(n_samples=100, random_state=2)
    model = LinearSVC(dual='auto').fit(X, y)
    m = evaluate_model(model, X, y)
    assert m['roc_auc'] is None
    assert 0.0 <= m['accuracy'] <= 1.0
