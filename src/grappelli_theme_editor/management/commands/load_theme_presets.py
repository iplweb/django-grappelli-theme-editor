import json
from importlib import resources

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from grappelli_theme_editor import revisions
from grappelli_theme_editor.models import Theme


class Command(BaseCommand):
    help = "Create the bundled example themes (skips existing ones by slug)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Reset presets that already exist to the bundled version.",
        )

    def handle(self, *args, overwrite=False, **options):
        files = sorted(
            f
            for f in resources.files("grappelli_theme_editor.presets").iterdir()
            if f.name.endswith(".json")
        )
        created = updated = 0
        for f in files:
            slug = f.name.removesuffix(".json")
            data = json.loads(f.read_text(encoding="utf-8"))
            theme = Theme.objects.filter(slug=slug).first()
            if theme is not None and not overwrite:
                continue
            is_new = theme is None
            theme = theme or Theme(slug=slug)
            theme.update_from_dict(data, allow_custom_css=True)
            try:
                theme.full_clean()
            except ValidationError as e:
                raise CommandError(f"Preset {f.name} is invalid: {e}") from e
            with revisions.revision(comment="load_theme_presets"):
                theme.save()
            created += is_new
            updated += not is_new
        self.stdout.write(
            self.style.SUCCESS(f"Presets: {created} created, {updated} updated.")
        )
