
## Invalid option syntax hardening

- Workflow run: https://github.com/teamleaderleo/meson/actions/runs/30840332069
- Starting head: 0f4276f66fcbb6c382febbe195f4674b8d0f7101
- The source handler now returns `UnknownValue` for option strings containing a subproject separator or otherwise failing `OptionKey` construction.
- The project-defined `logind` option still resolves to `systemd`.
- `get_option('bad:name')` no longer widens source introspection into an assertion failure and remains unresolved.
- Gates: focused JSON assertions, `python3 -m compileall -q mesonbuild`, and `git diff --check`.
- Evidence class: target-executed focused path on Linux; not a full Meson gate.
