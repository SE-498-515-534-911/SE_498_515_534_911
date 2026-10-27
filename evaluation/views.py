"""GET /api/evaluate/<run_id> (US-22, MLE-F-010, MLE-F-011; SAD 4.3.5, 4.4.2).

The browser polls this endpoint after ``POST /api/train``. While the run is
queued or running, ``metrics`` is null and the answer is still 200, so
progress is not treated as an error. Once the model is trained, the first call
evaluates it (see ``run_evaluation``) and the run becomes COMPLETED.
"""
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from accounts.api_errors import error_response
from accounts.permissions import DATA_ROLES, data_user_required, get_role
from experiments.models import Run

from .run_evaluation import evaluate_and_complete


def _iso(moment):
    return moment.isoformat().replace('+00:00', 'Z') if moment else None


def evaluate(request, run_id):
    if request.method != 'GET':
        return error_response(
            request, 'METHOD_NOT_ALLOWED', 'Only GET requests are allowed.', 405
        )
    if not request.user.is_authenticated:
        return error_response(request, 'AUTH_REQUIRED', 'Please log in to continue.', 401)
    # Student and Data Scientist only; the Admin cannot see run results (SRS Table 4.1-1).
    if get_role(request.user) not in DATA_ROLES:
        return error_response(
            request, 'FORBIDDEN', 'You do not have permission to do this.', 403
        )

    # Filtering by owner makes another user's run look exactly like a missing one (MLE-SR-005).
    run = (
        Run.objects.select_related('owner', 'dataset', 'artifact')
        .filter(pk=run_id, owner=request.user)
        .first()
    )
    if run is None:
        return error_response(request, 'NOT_FOUND', 'We could not find that run.', 404)

    evaluation = None
    if run.status in (Run.Status.TRAINED, Run.Status.COMPLETED):
        evaluation = evaluate_and_complete(run)  # may turn the run into FAILED

    error = None
    if run.status == Run.Status.FAILED:
        error = {'code': 'TRAINING_FAILED', 'message': run.error_message}

    return JsonResponse({
        'run_id': run.pk,
        'status': run.status,
        'dataset_id': run.dataset_id,
        'model': run.model_name,
        'metrics': evaluation.metrics if evaluation else None,
        'averaging': evaluation.averaging if evaluation else None,
        'confusion_matrix': evaluation.confusion_matrix if evaluation else None,
        'notes': evaluation.notes if evaluation else [],
        # US-23: a ranked list, or null with a message when the model has none.
        'feature_importance': evaluation.feature_importance if evaluation else None,
        'feature_importance_message': (
            evaluation.feature_importance_message if evaluation else ''
        ),
        'started_at': _iso(run.started_at),
        'finished_at': _iso(run.finished_at),
        'error': error,
    })


@data_user_required
def results_page(request, run_id):
    """The Results screen (SAD 4.5.3): metric tiles, bar chart and confusion matrix.

    The page only needs the run id; its script polls ``/api/evaluate/<run_id>``
    and draws what comes back. The run must belong to the user, otherwise 404.
    """
    run = get_object_or_404(Run, pk=run_id, owner=request.user)
    return render(request, 'evaluation/results.html', {'run': run})
