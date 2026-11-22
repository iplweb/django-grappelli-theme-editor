# Publishing to PyPI (Trusted Publishing)

Releases are uploaded by `.github/workflows/publish.yml` using PyPI
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/): GitHub Actions
proves its identity to PyPI with a short-lived OIDC token, so no API token is
stored anywhere.

## One-time setup

1. **Create the GitHub repository** `iplweb/django-grappelli-theme-editor` and
   push `main`.
2. **GitHub environments** (Settings › Environments): create `pypi` and
   `testpypi`. Recommended for `pypi`: *Required reviewers* (yourself), so
   every upload waits for a click, and *Deployment branches and tags* limited
   to tags `v*`.
3. **Pending publisher on PyPI** (the project does not exist yet):
   <https://pypi.org/manage/account/publishing/> › *Add a new pending
   publisher* › GitHub:
   - PyPI project name: `django-grappelli-theme-editor`
   - Owner: `iplweb`
   - Repository name: `django-grappelli-theme-editor`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
4. **Same on TestPyPI** (<https://test.pypi.org/manage/account/publishing/>)
   with environment name `testpypi`.

The first successful upload turns the pending publisher into a normal one.

## Releasing

1. Update `version` in `pyproject.toml` and `CHANGELOG.md`; commit.
2. Optional dry run: Actions › *Publish* › *Run workflow* › `testpypi`, then
   `pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ django-grappelli-theme-editor`.
3. Tag and release: `git tag v0.1.0 && git push --tags`, then create a GitHub
   release from the tag (`gh release create v0.1.0 --generate-notes`).
   Publishing the release triggers the upload (the workflow checks that the
   tag matches the version in `pyproject.toml`).
