# Meson 15998 design boundary

## Current conclusion

The one-line CUDA normalization candidate is a valid language-classification and duplicate-removal probe, but it does **not** satisfy the issue's precedence contract.

A second provenance-gated candidate was also rejected before execution. Provenance alone is insufficient: removing an unexplained effective CUDA standard is safe only when another authority will replace it.

A production policy therefore needs both:

1. **provenance** — why the CMake File API contains the effective standard;
2. **replacement authority** — whether Meson or explicit CMake configuration will supply a deliberate surviving standard.

## Executed and source-proven precedence

`TargetOptions.get_override_options()` removes an initial option with the same key and appends explicit global or target `cmake.subproject_options()` values.

The compiler-free controls already prove:

1. the one-line candidate converts an unexplained `-std=c++17` into `cuda_std=c++17`;
2. that generated target override defeats an ordinary parent-project default;
3. a global `cmake.subproject_options().set_override_option('cuda_std', 'c++20')` replaces it;
4. a target-specific override replaces both with `c++23`.

Therefore:

- explicit CMake-module overrides already win;
- an ordinary parent-project `cuda_std` loses to the one-line candidate's generated target override;
- the one-line candidate cannot be described as fixing issue #15998.

## New architecture finding: AST generation sees both late authorities

The converter and AST generator already split the relevant responsibilities in a useful way.

`ConverterTarget.postprocess()` currently decides whether a File API `-std=` fragment becomes a generated target `override_options` entry. That is too early for an unexplained CUDA standard because it has not yet resolved replacement authority.

Later, `CMakeInterpreter` generates the Meson target call and computes:

- `override_options = options.get_override_options(tgt.cmake_name, tgt.override_options)`;
- language compile arguments through `options.get_compile_args(...)`.

`TargetOptions` contains both global and target-specific `cmake.subproject_options()` state, and its `SingleTargetOptions.opts` map is the exact late authority that replaces generated target options.

Separately, the interpreter retains `env.coredata.optstore`, which is already used by the converter to inspect language-standard option objects. That is the natural source for the effective surrounding Meson `cuda_std` value.

This means the next candidate does **not** need to push Meson standards into CMake or guess replacement authority during File API parsing. The narrowest boundary is to defer only unexplained standard settlement until target AST generation.

## Provenance sources available today

### File API file group

`CMakeFileGroup.language` and source suffixes determine the Meson language bucket. `compileFlags` supplies effective raw flags. This identifies a CUDA standard fragment but does not explain why it exists.

### CMake trace target properties

The trace parser records `set_property(TARGET ...)`, `set_target_properties(...)`, and `target_compile_options()` values in `trace.targets[name].properties`. Explicit target `CUDA_STANDARD` and direct target `-std=` intent can therefore be distinguished from an otherwise unexplained effective flag.

### CMake trace variables

The parser retains final variables and per-file assignments, including directly written `CMAKE_CUDA_STANDARD`. This is useful evidence but not a complete directory-scope timeline. A final variable value can differ from the value that initialized a particular target, so it is not safe by itself as universal target provenance.

### Meson project and subproject authority

A generated target `cuda_std=...` override naturally outranks the parent project's default. Explicit global or target CMake-module overrides replace generated values later through `TargetOptions`.

The effective surrounding Meson standard is available from the option store, while explicit CMake-module overrides are available only later through `TargetOptions`. This stage split is why immediate normalization is unsafe and deferred settlement is attractive.

## Candidate policies

### Policy A — normalize every CUDA `-std=` fragment

Status: `REJECT AS COMPLETE FIX / RETAIN AS CLASSIFICATION PROBE`.

- Pros: mirrors current C/C++ conversion; removes duplicates; preserves the effective CMake command.
- Cons: turns an unexplained effective value into a target override and defeats the parent Meson default in the reported case.

Focused run `30858277753` remains valid evidence for classification and raw-flag deduplication only.

### Policy B — remove unexplained CUDA `-std=`; override only traced explicit target intent

Status: `REJECT AS PRODUCTION POLICY / RETAIN AS NEGATIVE DESIGN GENERATION`.

This was the candidate encoded by `apply_provenance_candidate.py` and execution PR #6.

It would:

- remove the effective raw CUDA standard;
- emit a target override for traced `CUDA_STANDARD` or matching direct target compile options;
- leave unexplained standards without a target override so the parent Meson default could win.

Blocking compatibility case:

- no explicit target CMake provenance;
- no Meson parent/subproject `cuda_std` replacement authority;
- File API reports the only effective CUDA standard.

Policy B silently drops that standard and falls back to compiler defaults. A clean provenance test would not make that behavior safe.

Execution PR #6 and workflow run `31019630325` were retired while queued. They are not behavior evidence. The temporary workflow was removed from the default branch.

### Policy C — deferred settlement at AST generation

Status: `SELECTED NEXT EXPERIMENT BOUNDARY / NOT YET PRODUCTION-ACCEPTED`.

Instead of immediately turning every effective CUDA standard into an override or deleting unexplained values, retain a small per-language deferred record on `ConverterTarget` containing:

- the effective standard token;
- whether reliable target-level CMake provenance exists;
- enough information to remove the corresponding raw compile fragment only when settlement is decided.

At target AST generation, settle the record in this order:

1. **explicit target CMake provenance** — emit the generated `cuda_std=...` target override; a later explicit `cmake.subproject_options()` override can still replace it through existing `TargetOptions` behavior;
2. **explicit global/target `cmake.subproject_options()` replacement** — suppress an unexplained fallback and let that explicit override win;
3. **effective surrounding Meson `cuda_std` is non-`none`** — suppress the unexplained fallback and emit no generated target override, allowing the ordinary Meson project/subproject standard to remain authoritative;
4. **no replacement authority** — preserve the effective CMake standard as a raw CUDA compile fallback rather than silently dropping to the compiler default.

This directly preserves both previously conflicting cases:

- reporter case: parent Meson `cuda_std` replaces an unexplained effective CMake flag;
- compatibility case: unexplained effective CMake standard survives when Meson supplies no replacement.

The implementation should add a small `TargetOptions` query helper rather than reach into `SingleTargetOptions.opts` from the interpreter. For example, `has_override_option(target, option)` can check global then target-specific state without changing existing precedence behavior.

Open semantic caveat: a directory/global `CMAKE_CUDA_STANDARD` that initialized a target is still not reliably distinguishable from an unexplained effective File API value using final trace-variable state alone. Policy C therefore remains an experiment boundary until that case is either given reliable creation-time provenance or its intended precedence is explicitly specified and tested.

### Policy D — propagate Meson standards into the generated CMake toolchain

Status: `HOLD AS BROADER DESIGN`.

Map Meson standards into CMake before configuration, then normalize the resulting effective flags.

`CMakeInterpreter.configure()` constructs the CMake toolchain from the environment before File API analysis and does not receive `TargetOptions`; explicit `cmake.subproject_options()` target overrides are only applied later during Meson AST generation. Pushing all precedence into the toolchain would therefore require a broader ownership redesign and still needs mapping for `c++*`, `gnu++*`, `none`, extension modes, and compiler support.

This is no longer the preferred next experiment.

## Required next implementation controls

The next candidate should be compiler-free first and must include all of these before any execution carrier is considered authoritative:

| Case | Required outcome |
| --- | --- |
| no explicit CMake standard; Meson project `cuda_std=c++20` | exactly C++20; unexplained effective CMake flag is removed without creating a target override |
| no explicit CMake standard; Meson `cuda_std=none` | retain the effective CMake `-std=` fallback |
| explicit target `CUDA_STANDARD 17`; project C++20 | generated explicit target intent wins unless a later CMake-module override replaces it |
| direct target `-std=c++17`; project C++20 | explicit target compile-option intent is not silently lost |
| explicit global `cmake.subproject_options()` C++23 | C++23 wins and no unexplained raw fallback survives |
| target-specific `cmake.subproject_options()` C++23 | target C++23 wins over generated and fallback values |
| global/directory `CMAKE_CUDA_STANDARD 17`; project C++20 | no production claim until target-creation provenance or intended precedence is explicit |
| mixed CXX/CUDA target | C++ and CUDA standards remain independently classified |
| GNU extension standards | extension mode is preserved rather than collapsed |
| unsupported standard | no silent semantic loss |

One additional negative control is mandatory: an unexplained effective CUDA standard with `cuda_std=none` and no `TargetOptions` override must remain present after generated AST settlement.

## Current decision

Keep source PR #3 in draft and research-only state.

- Policy A remains executed classification evidence, not an issue fix.
- Policy B is rejected before execution because it lacks replacement authority.
- Policy C is now the narrowest viable experiment boundary because AST generation can see both the surrounding Meson option store and late `TargetOptions` authority.
- No new execution carrier should be created until the deferred-settlement implementation and the no-authority negative control exist in source form.

The current issue must not be described as resolved until both the reporter's parent-authority case and the no-replacement-authority compatibility case are preserved, and the directory/global CMake-standard caveat is explicitly settled or bounded.