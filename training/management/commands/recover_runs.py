"""``python manage.py recover_runs [--all]``: restart recovery for training runs (SAD 4.4.3)."""
from django.core.management.base import BaseCommand

from training.recovery import STALE_AFTER_SECONDS, fail_interrupted_runs


class Command(BaseCommand):
    help = 'Mark training runs that were interrupted by a server restart as FAILED.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Fail every QUEUED or RUNNING run. Use this at start-up, before the server accepts requests.',
        )

    def handle(self, *args, **options):
        count = fail_interrupted_runs(stale_after=0 if options['all'] else STALE_AFTER_SECONDS)
        self.stdout.write(f'{count} interrupted training run(s) marked as FAILED.')
