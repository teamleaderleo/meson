# Fieldwork: source dependency names derived from project options

Upstream issue: https://github.com/mesonbuild/meson/issues/16046  
Inspected source base: `0b5b32e284709eb5b23ed30207fe978362d30a3d`  
External contact: **not authorized and not performed**

## In simple words

`meson introspect --dependencies meson.build` evaluates build definitions without configuring a build directory. It already loads project option defaults, but the AST interpreter previously treated every `get_option()` call as unknown. When that value was passed to `dependency()`, JSON serialization turned the unresolved value into a real-looking dependency named `unknown`.

The fork now resolves only source-known primitive project option values. The report's `logind` combo option produces `systemd`, while dynamic, missing, feature-wrapper, unsupported structured values, and invalid option syntax remain unresolved.

## Implemented change

`mesonbuild/ast/introspection.py` now:

- maps `get_option` to a source-introspection-specific handler;
- requires one literal string option name;
- resolves the option through the already-loaded `coredata.optstore` using the current subproject key;
- returns only JSON-safe primitive values (`str`, `bool`, `int`, or lists of those primitives);
- returns `UnknownValue` for missing, dynamic, feature-wrapper, structured, or invalid option identities.

## Fixture correction

The first packet fixture incorrectly used `backend`, a built-in Meson option name. Before execution it was replaced with the actual project-defined shape from the report:

```meson
option('logind', type: 'combo', choices: ['systemd', 'elogind'], value: 'systemd')
```

and:

```meson
logind = get_option('logind')
dependency(logind, version: '>= 209', required: false)
```

## Executed evidence

Fieldwork run `30839352175`, job `91772318148`, compared exact base and candidate:

- base `0b5b32e...` emitted one dependency named `unknown`;
- candidate checkout head `22740b56695248262ba1900a37af2333a00aec8c` emitted `systemd` with unchanged metadata;
- `python3 -m compileall -q mesonbuild` and `git diff --check` passed.

Meson run `30840332069` then exercised the current hardening change:

- the real `logind` fixture still emitted `systemd`;
- `get_option('bad:name')` remained unresolved instead of asserting;
- Python compilation and diff checks passed.

The current production patch is retained in `mesonbuild/ast/introspection.py`; focused outputs and receipts live under `fieldwork/16046/` and Fieldwork Round 005.

## Remaining compatibility work

The focused behavior is established, but this is not a full Meson unit gate. Before promotion beyond the owned fork, add or adapt the repository-native source-introspection test helper for:

- literal dependency control;
- combo/string project option;
- missing or dynamic option name;
- subproject option key;
- feature-option unresolved behavior;
- invalid literal option syntax;
- an unresolved dependency policy that does not confuse `unknown` with a confirmed package where broader expressions remain unmodelled.

## Evidence state

`source-implemented`; `target-executed-focused` on Linux; not a full Meson gate, cross-platform result, independent acceptance, or authorized upstream packet.
