"""US-11 unit tests: metric and access-check edge cases (MLE-F-010, MLE-F-002).

The main metric and permission tests live with their apps; these cover the
paths those tests do not reach.
"""
import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View

from accounts.models import Role
from accounts.permissions import RoleRequiredMixin, get_role
from evaluation.metrics import compute_metrics


# ---- metrics -----------------------------------------------------------------

def test_roc_auc_is_none_when_probabilities_do_not_match_the_classes():
    # Three classes but only two probability columns: AUC cannot be computed.
    m = compute_metrics([0, 1, 2, 0, 1, 2], [0, 1, 2, 0, 1, 1],
                        y_proba=[[0.6, 0.4]] * 6, classes=[0, 1, 2])
    assert m['roc_auc'] is None
    assert m['accuracy'] == pytest.approx(5 / 6)


def test_roc_auc_is_none_without_probabilities():
    assert compute_metrics([0, 1, 0, 1], [0, 1, 1, 1])['roc_auc'] is None


@pytest.mark.parametrize('y_true, y_pred', [([], []), ([0, 1], [0])])
def test_metrics_refuse_empty_or_mismatched_input(y_true, y_pred):
    with pytest.raises(ValueError):
        compute_metrics(y_true, y_pred)


# ---- access checks -----------------------------------------------------------

class DataOnlyView(RoleRequiredMixin, View):
    allowed_roles = (Role.STUDENT, Role.DATA_SCIENTIST)

    def get(self, request):
        return HttpResponse('ok')


def test_class_based_view_sends_anonymous_visitors_to_login():
    request = RequestFactory().get('/private/')
    request.user = AnonymousUser()
    response = DataOnlyView.as_view()(request)
    assert response.status_code == 302
    assert '/login' in response.url and 'next=/private/' in response.url


def test_anonymous_user_has_no_role():
    assert get_role(AnonymousUser()) is None
