## Summary

- 

## Type

- [ ] Bug fix
- [ ] Feature
- [ ] Documentation
- [ ] Refactor
- [ ] Release maintenance

## Safety Checklist

- [ ] No telemetry, analytics, ads, cloud sync, or surprise background services added
- [ ] Window hide/restore behavior was tested or is not affected
- [ ] Managed windows are restored or safely handled on failure paths
- [ ] Settings and logs remain local-only
- [ ] No secrets, local paths, generated files, or private machine data included

## Verification

- [ ] `python -m ruff check . --no-cache`
- [ ] `python -m pytest -p no:cacheprovider`
- [ ] Basic import check: `python -c "import shelfygai; print(shelfygai.__version__)"`
- [ ] Manual check on Windows 10 or Windows 11, if UI/window behavior changed
- [ ] Packaged app smoke test, if packaging changed: `.\scripts\build_exe.ps1 -SmokeTest`

## Notes For Reviewers

-
