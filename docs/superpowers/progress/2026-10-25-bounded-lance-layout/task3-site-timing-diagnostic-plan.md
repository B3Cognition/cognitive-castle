# One explicit-site timing stage — static preparation only

`task3-site-timing-diagnostic.py::test_site_startup_attribution` safely hash-loads the unchanged previous timing helper (f675dcbe…), reuses its host timers, and substitutes exactly one fixed Python `-I -S` worker. Guardian/product files and original2s/128MiB task/192MiB total/background preemption remain unchanged. No source, database, engine, model or network request is made. Root owns one fresh preflight/launch; no retry or qualification execution.

Worker consumes bounded original stdin, records early absolute monotonic entry/emit times, imports stdlib site, wraps existing site.addpackage, runs site.main exactly once, then times psutil import. Per-.pth durations are ordinal-only, max16; excess refuses before executing another .pth. No names, contents, paths or bodies are returned. Psutil-preloaded and prefix-changed indicators prevent misreading cached-import or venv results. Each fixed scalar timing response/record is <=2KiB. Failure reports the bounded record then fails the test. The unchanged host record is also retained; nested host intervals must not be added as exclusive totals.

Manual-site is attribution evidence, not startup parity/acceptance: under Python3.12 site.main restores venv prefixes, but sys.flags.no_site stays1 and initial sys/time/json imports precede explicit site.main. Guardian's own ordinary startup is unchanged and remains in the host residual interval. No startup/cap/production behavior change is proposed by this measurement.

Root's fixed command, once independently admitted:

```
/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 5 --rss-mib 256 .superpowers/sdd/2026-10-25-bounded-lance-layout/task3-site-timing-diagnostic.py::test_site_startup_attribution --noconftest -x -q -s -p no:cacheprovider --basetemp /private/tmp/castle-task3-site-timing-20261025-v1
```

Static AST/compile/Ruff only; author has not executed the fixture or worker. No retained data fixture; root exclusively captures output and performs external cleanup as in the preceding one-shot diagnostic.
