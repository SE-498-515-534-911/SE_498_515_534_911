"""Prepare the TC-PERF-03 test data: 20 accounts, each with a dataset and completed runs (US-30).

Every account is created, uploaded to, trained and evaluated through the
application's own code (upload validation and storage, the training job,
evaluation), so the load test reads realistic data.

Run from the repository root, with the same database the server uses:
    python loadtest/seed.py                  # 20 accounts, 4 completed runs each
    python loadtest/seed.py --users 5 --runs 2
Inside Docker:
    docker compose exec web python loadtest/seed.py

Accounts: load_user_01 ... load_user_20, password LOAD_TEST_PASSWORD below.
Existing accounts are kept and skipped, so the script can be run again.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOAD_TEST_PASSWORD = 'LoadTest!2026pw'
MODELS = ('logistic_regression', 'decision_tree', 'random_forest', 'knn')


def username(number):
    return f'load_user_{number:02d}'


def sample_csv(rows=1000, seed=0):
    """sample_1000rows.csv: 5 columns (numbers and text) with a few missing values, target 'bought'."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        'age': rng.integers(18, 80, rows),
        'income': rng.normal(50, 15, rows).round(2),
        'city': rng.choice(['Pune', 'Delhi', 'Chennai', 'Mumbai'], rows),
        'visits': rng.poisson(4, rows),
    })
    df['bought'] = np.where(df['income'] + 3 * df['visits'] + rng.normal(0, 10, rows) > 62, 'yes', 'no')
    df.loc[rng.choice(rows, rows // 40, replace=False), 'income'] = np.nan
    return df.to_csv(index=False).encode('utf-8')


def seed(users=20, runs=4, stdout=sys.stdout):
    """Create the accounts and their data. Returns {username: [run ids]}."""
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile

    from accounts.models import Role
    from datasets.services import upload_dataset
    from evaluation.run_evaluation import evaluate_and_complete
    from experiments.models import Run
    from training import jobs

    # Train in this process: the seed runs once, before the test, and needs no isolation.
    settings.TRAINING_JOB_ISOLATION = False
    User = get_user_model()
    created = {}
    for number in range(1, users + 1):
        name = username(number)
        if User.objects.filter(username=name).exists():
            stdout.write(f'{name}: already there, skipped\n')
            continue
        user = User.objects.create_user(name, f'{name}@example.com', LOAD_TEST_PASSWORD)
        user.profile.role = Role.DATA_SCIENTIST
        user.profile.save()

        upload = SimpleUploadedFile('sample_1000rows.csv', sample_csv(seed=number), content_type='text/csv')
        dataset = upload_dataset(user, upload)
        run_ids = []
        for index in range(runs):
            run = Run.objects.create(
                owner=user, dataset=dataset, target_column='bought', model_name=MODELS[index % len(MODELS)],
                params_json={}, preprocessing_json={'missing': 'median', 'categorical': 'one_hot'},
                split_json={'test_size': 0.2, 'random_state': 42},
            )
            jobs.execute_run(run.pk)
            run.refresh_from_db()
            evaluate_and_complete(run)
            run.refresh_from_db()
            if run.status != Run.Status.COMPLETED:
                raise SystemExit(f'{name}: run {run.pk} ended {run.status}: {run.error_message}')
            run_ids.append(run.pk)
        created[name] = run_ids
        stdout.write(f'{name}: dataset {dataset.pk}, completed runs {run_ids}\n')
    return created


def main(argv=None):
    parser = argparse.ArgumentParser(description='Seed the TC-PERF-03 load-test accounts.')
    parser.add_argument('--users', type=int, default=20)
    parser.add_argument('--runs', type=int, default=4, help='completed runs per account')
    args = parser.parse_args(argv)

    sys.path.insert(0, str(ROOT))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django

    django.setup()
    seed(args.users, args.runs)
    return 0


if __name__ == '__main__':
    sys.exit(main())
