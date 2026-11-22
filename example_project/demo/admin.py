from django.contrib import admin

from .models import Author, Journal, Publication


class AuthorInline(admin.TabularInline):
    model = Author
    extra = 1
    sortable_field_name = "order"


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "journal", "published_on", "is_open_access")
    list_filter = ("kind", "is_open_access", "journal")
    search_fields = ("title",)
    date_hierarchy = "published_on"
    inlines = [AuthorInline]
    fieldsets = (
        (None, {"fields": ("title", "kind", "journal")}),
        (
            "Details",
            {
                "fields": ("published_on", "is_open_access", "abstract"),
                "classes": ("grp-collapse grp-open",),
            },
        ),
    )


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("name", "issn")
    search_fields = ("name",)
