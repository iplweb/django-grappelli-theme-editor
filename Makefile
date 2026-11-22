.PHONY: test test-browser lint messages compilemessages tokens demo

test:
	uv run pytest

test-browser:
	uv run pytest -m playwright

lint:
	uv run ruff format --check src tests scripts example_project
	uv run ruff check src tests scripts example_project

# Package catalog only — run from the package dir so the demo's strings
# never end up in the shipped .po file.
messages:
	cd src/grappelli_theme_editor && uv run django-admin makemessages -l pl -l de -l fr -l es --no-obsolete --no-location

compilemessages:
	cd src/grappelli_theme_editor && uv run django-admin compilemessages

# Regenerate tokens_data.py after upgrading django-grappelli.
tokens:
	uv run python scripts/extract_tokens.py

demo:
	cd example_project && uv run python manage.py migrate && \
		uv run python manage.py load_theme_presets && \
		uv run python manage.py demo_data && \
		uv run python manage.py runserver
