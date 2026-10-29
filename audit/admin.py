from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only view of the audit log in Django's admin site (US-38, MLE-SR-005).

    Nobody, not even an Admin, can add, change or delete an entry here: a log
    that can be edited proves nothing. (The Admin console of US-37 shows the
    same log inside the application.)
    """

    list_display = ('timestamp', 'action', 'user', 'target', 'ip_address')
    list_filter = ('action',)
    search_fields = ('target', 'user__username')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
