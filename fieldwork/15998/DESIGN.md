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

## Provenance sources available today

### File API file group

`CMakeFileGroup.language` and source suffixes determine the Meson language bucket. `compileFlags` supplies effective raw flags. This identifies a CUDA standard fragment but does not explain why it exists.

### CMake trace target properties

The trace parser records `set_property(TARGET ...)`, `set_target_properties(...)`, and `target_compile_options()` values in `trace.targets[name].properties`. Explicit target `CUDA_STANDARD` and direct target `-std=` intent can therefore be distinguished from an otherwise unexplained effective flag.

### CMake trace variables

The parser retains final variables and per-file assignments, including directly written `CMAKE_CUDA_STANDARD`. This is useful evidence but not a complete directory-scope timeline. A final variable value can differ from the value that initialized a particular target, so it is not safe by itself as universal target provenance.

### Meson project and subproject authority

A generated target `cuda_std=...` override naturally outranks the parent project's default. Explicit global or target CMake-module overrides replace generated values later through `TargetOptions`.

The converter currently does not know whether the surrounding Meson project has a non-`none` `cuda_std` default while it is deciding how to process the File API flag.

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

### Policy C — provenance plus explicit replacement authority

Status: `NEXT DESIGN BOUNDARY`.

Only suppress an unexplained effective CUDA standard when the converter knows that a non-`none` Meson `cuda_std` authority will replace it. Otherwise retain the effective standard as fallback.

Possible implementations:

1. pass the effective project/subproject `cuda_std` into `ConverterTarget.postprocess()`;
2. retain an unexplained standard as deferred metadata and decide during target AST generation, after `TargetOptions` are known;
3. represent the discovered value as a fallback that explicit Meson project or CMake-module options can remove without losing no-authority behavior.

Required difficulty: ordinary project defaults and explicit `cmake.subproject_options()` are applied at different stages. A correct design must avoid converting the fallback into another unconditional target override.

### Policy D — propagate Meson standards into the generated CMake toolchain

Status: `HOLD AS BROADER DESIGN`.

Map Meson standards into CMake before configuration, then normalize the resulting effective flags.

This requires passing project/subproject option ownership into `CMakeInterpreter.configure()` or `CMakeToolchain`, mapping `c++*`, `gnu++*`, `none`, extension modes, and compiler support, and preserving explicit CMake target overrides. The current architecture applies `TargetOptions` only after CMake analysis while generating Meson AST, so this is not a one-line follow-up.

## Required matrix

| Case | Required outcome |
| --- | --- |
| no explicit CMake standard; Meson project `cuda_std=c++20` | exactly C++20; unexplained effective CMake flag does not become a target override |
| no explicit CMake standard; Meson `cuda_std=none` | retain the effective CMake standard; do not silently fall back to compiler default |
| explicit target `CUDA_STANDARD 17`; project C++20 | explicit target intent is retained or deliberately diagnosed |
| direct target `-std=c++17`; project C++20 | explicit compile-option intent is not silently lost |
| global/directory `CMAKE_CUDA_STANDARD 17`; project C++20 | no claim until target-creation provenance is reliable |
| explicit Meson subproject override C++23 | C++23 wins over fallback, discovered, and project values |
| mixed CXX/CUDA target | C++ and CUDA standards remain independently classified |
| GNU extension standards | extension mode is preserved rather than collapsed |
| unsupported standard | no silent semantic loss |

## Current decision

Keep source PR #3 in draft and research-only state.

- Policy A remains executed classification evidence, not an issue fix.
- Policy B is rejected before execution because it lacks replacement authority.
- The next implementation must first expose the effective Meson `cuda_std` authority at the conversion or AST-generation boundary and add the no-authority negative control.

The current issue must not be described as resolved until both the reporter's parent-authority case and the no-replacement-authority compatibility case are preserved.
