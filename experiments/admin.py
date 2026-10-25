from django.contrib import admin

from .models import Run


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'model_name', 'status', 'created_at', 'finished_at')
    list_filter = ('status', 'model_name')
    # Configuration and status only; no dataset contents (MLE-F-016).
    readonly_fields = [f.name for f in Run._meta.fields]
