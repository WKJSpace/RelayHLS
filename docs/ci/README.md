# Optional GitHub Actions template

`verify-release.yml` runs the offline release verifier and tests. It launches no
decoder, vendor or measurement workflow. This release provides the template
without installing it in `.github/workflows/`: the publishing credentials have
repository access but do not have GitHub's workflow scope. A maintainer with
that permission can install it later. The same checks run locally with:

```bash
python3 scripts/verify_release.py
python3 -m unittest discover -s tests -p 'test_*.py'
```
