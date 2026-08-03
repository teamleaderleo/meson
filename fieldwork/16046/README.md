# Fieldwork: source dependency names from project options

Upstream issue: https://github.com/mesonbuild/meson/issues/16046  
Inspected source: `0b5b32e284709eb5b23ed30207fe978362d30a3d`  
External contact: **not authorized and not performed**

## In simple words

`meson introspect --dependencies meson.build` currently turns a dependency name derived from `get_option()` into the literal package name `unknown`. The option file has already been parsed, so the source interpreter can resolve ordinary project-option defaults instead of inventing that package name.

## Current mechanism

- `IntrospectionInterpreter` handles `dependency()` and records its first argument.
- Its base `AstInterpreter` maps `get_option()` to `func_do_nothing()`, which returns `UnknownValue`.
- `IntrospectionEncoder` serializes `UnknownValue` as the JSON string `"unknown"`.
- `func_project()` already calls `_load_option_file()`, so the option store contains source-known defaults before later statements are visited.

## Candidate boundary

Map `get_option` in `IntrospectionInterpreter` to a source-only resolver that:

1. accepts exactly one literal string option name;
2. looks up the option in `coredata.optstore` with the current subproject key;
3. returns only JSON-safe primitive option values (`str`, `bool`, `int`, or lists of those);
4. returns `UnknownValue` for dynamic names, missing options, feature wrappers, or values the source interpreter cannot safely model.

This is intentionally narrower than the normal interpreter. It does not attempt to configure a build or evaluate feature-option methods.

## Required controls

- combo/string option default used as `dependency(get_option('backend'))` emits the selected default, never `unknown`;
- an explicit source-introspection `-Dbackend=...` override wins if that interface supports project options;
- dynamic or unavailable option names remain conditional/unknown without crashing;
- literal dependencies and subproject options remain unchanged;
- source introspection must never emit a dependency literally named `unknown` merely because its expression could not be evaluated.

## Artifacts

- `candidate.patch` contains the bounded implementation sketch and target-native test shape.
- `reproducer/` is a network-free source tree for the issue behavior.

## Evidence state

`source-reviewed`; `target-test-prepared`; not executed in this environment. Promote only after Meson's unit suite and the focused source-introspection fixture pass on the fork.