from django.db import models


class Journal(models.Model):
    name = models.CharField(max_length=200)
    issn = models.CharField("ISSN", max_length=9, blank=True)

    def __str__(self):
        return self.name


class Publication(models.Model):
    class Kind(models.TextChoices):
        ARTICLE = "article", "Article"
        BOOK = "book", "Book"
        CHAPTER = "chapter", "Chapter"

    title = models.CharField(max_length=300)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    journal = models.ForeignKey(
        Journal, null=True, blank=True, on_delete=models.SET_NULL
    )
    published_on = models.DateField(null=True, blank=True)
    is_open_access = models.BooleanField(default=False)
    abstract = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Author(models.Model):
    publication = models.ForeignKey(
        Publication, related_name="authors", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=200)
    affiliation = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name
