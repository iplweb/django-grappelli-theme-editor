import datetime
import random

from django.core.management.base import BaseCommand

from demo.models import Author, Journal, Publication


class Command(BaseCommand):
    help = "Fill the demo with sample publications (idempotent)."

    def handle(self, *args, **options):
        if Publication.objects.exists():
            self.stdout.write("Demo data already present.")
            return
        rnd = random.Random(42)
        journals = [
            Journal.objects.create(name=n, issn=f"1234-{i:04d}")
            for i, n in enumerate(
                ["Journal of Examples", "Annals of Testing", "Theme Studies Quarterly"]
            )
        ]
        for i in range(1, 58):
            pub = Publication.objects.create(
                title=f"On the colour of admin panels, part {i}",
                kind=rnd.choice(list(Publication.Kind)),
                journal=rnd.choice(journals),
                published_on=datetime.date(2020 + i % 7, 1 + i % 12, 1 + i % 28),
                is_open_access=i % 3 == 0,
            )
            for order, name in enumerate(["Anna Kowalska", "Jan Nowak"][: 1 + i % 2]):
                Author.objects.create(
                    publication=pub,
                    name=name,
                    affiliation="Faculty of Design",
                    order=order,
                )
        self.stdout.write(self.style.SUCCESS("Created demo data."))
