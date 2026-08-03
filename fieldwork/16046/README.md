# Fieldwork: source dependency names derived from project options

Upstream issue: https://github.com/mesonbuild/meson/issues/16046  
Inspected source base: `0b5b32e284709eb5b23ed30207fe978362d30a3d`  
External contact: **not authorized and not performed**

## In simple words

`meson introspect --dependencies meson.build` evaluates build definitions without configuring a build directory. It already loads project option defaults, but the AST interpreter previously treated every `get_option()` call as unknown. When that value was passed to `dependency()`, JSON serialization turned the unresolved value into a real-looking dependency named `unknown`.

The fork now resolves only source-known primitive project option values. The report's `logind` combo option therefore produces `systemd`, while dynamic, missing, feature-wrapper, and unsupported structured values remain unresolved.

## Implemented change

`mesonbuild/ast/introspection.py` now:

- maps `get_option` to a source-introspection-specific handler;
- requires one literal string option name;
- resolves the option through the already-loaded `coredata.optstore` using the current subproject key;
- returns only JSON-safe primitive values (`str`, `bool`, `int`, or lists of those primitives);
- leaves unsupported values as `UnknownValue` rather than pretending to configure a build.

The production source commit is present on `fieldwork/16046-source-option-dependency`.

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

## Exact execution contract

Against base `0b5b32e...`, the fixture must emit one dependency named `unknown`. Against the fork candidate, it must emit `systemd` with the same version, required, fallback, and conditional fields.

The focused gate also compiles the Python package and runs `git diff --check`. Execution is carried by Fieldwork Round 005; no passing result is claimed until its retained receipt lands.

## Hardening edge

`OptionKey.from_string` assumes valid option syntax. Source introspection should remain conservative for invalid literal option names rather than widening its failure surface. After the principal base-versus-candidate result is retained, add an invalid-name control and return `UnknownValue` for syntax that cannot form an `OptionKey`.

## Required compatibility controls

- literal dependency name remains unchanged;
- string/combo project option resolves;
- missing or dynamic option name remains unresolved;
- subproject option uses the correct subproject key;
- feature options remain unresolved until their method semantics are modeled;
- invalid literal option syntax does not crash source introspection;
- no unresolved expression is silently presented as a confirmed package dependency.

## Evidence state

`source-implemented`; corrected focused fixture retained; target execution pending through Fieldwork Round 005. This is not yet a full Meson gate or an accepted upstream-ready patch.
