# Meson 15998 design boundary

## Current conclusion

The one-line CUDA normalization candidate is a valid language-classification and duplicate-removal probe, but it does **not** satisfy the current issue's stated precedence contract.

The reporter says the CMake project does not request a C++ or CUDA standard and expects Meson's parent `cuda_std` to win. Converting every effective CUDA `-std=` fragment into a Meson target override leaves the unexplained CMake `c++17` value above the parent project default. It removes the duplicate, but selects the wrong surviving standard for the reported case.

## Executed and source-proven precedence

`TargetOptions.get_override_options()` removes an initial option with the same key and appends explicit global or target `cmake.subproject_options()` values.

The compiler-free unit controls now prove:

1. an unexplained discovered `-std=c++17` becomes `cuda_std=c++17` and remains a target override when no explicit CMake-module override is supplied;
2. a global `cmake.subproject_options().set_override_option('cuda_std', 'c++20')` replaces it;
3. a target-specific override replaces both with `c++23`.

Therefore:

- explicit CMake-module overrides already win;
- an ordinary parent-project `cuda_std` loses to the one-line candidate's discovered target override;
- the one-line candidate cannot be described as fixing issue #15998.

## Provenance sources available today

### File API file group

`CMakeFileGroup.language` and source suffixes determine the Meson language bucket. `compileFlags` supplies effective raw flags. This identifies a CUDA standard fragment but does not explain why it exists.

### CMake trace target properties

The trace parser records `set_property(TARGET ...)` and `set_target_properties(...)` values in `trace.targets[name].properties`. An explicitly traced target `CUDA_STANDARD` can therefore be distinguished from an otherwise unexplained effective flag.

### CMake trace variables

The parser retains final variables and per-file assignments, including a directly written `CMAKE_CUDA_STANDARD`. This is useful evidence but not a complete directory-scope timeline. A final/global value can differ from the value that initialized a particular target, so it is not safe by itself as universal target provenance.

### Explicit compile options

`target_compile_options()` is represented in trace target properties. A direct `-std=` option can be explicit CMake intent even when `CUDA_STANDARD` is absent. Any provenance-gated repair must account for this route rather than treating target properties as the only explicit source.

### Meson project default

A generated target `cuda_std=...` override naturally outranks the parent project's default. This is the exact failing policy when the discovered value has no explicit CMake provenance.

## Candidate policies

### Policy A — normalize every CUDA `-std=` fragment

Status: `REJECT AS COMPLETE FIX / RETAIN AS CLASSIFICATION PROBE`.

- Pros: mirrors current C/C++ conversion; removes duplicates; preserves the effective CMake command.
- Cons: defeats parent Meson precedence in the reported no-explicit-CMake-standard case.

### Policy B — remove unexplained CUDA `-std=` fragments; override only explicit CMake intent

Status: `NEXT CONTROLLED EXPERIMENT`.

- Remove the effective raw CUDA standard from `cuda_args` so Meson emits at most one standard flag.
- Add a target `cuda_std` override only when the trace establishes explicit target intent, beginning with `CUDA_STANDARD` and direct target compile options.
- Leave an unexplained effective standard without a target override so the parent Meson `cuda_std` can win.

Required negative controls:

- no explicit CMake standard: parent Meson default remains authoritative;
- explicit target `CUDA_STANDARD`: CMake target intent is retained;
- explicit target compile option: the option is not silently discarded;
- explicit Meson CMake-module override: it remains final authority;
- global/directory `CMAKE_CUDA_STANDARD`: stay held until target-scoped provenance is reliable.

### Policy C — propagate Meson standards into the generated CMake toolchain

Status: `HOLD AS BROADER DESIGN`.

Map Meson standards into CMake before configuration, then normalize the resulting effective flags.

This requires passing project/subproject option ownership into `CMakeInterpreter.configure()` or `CMakeToolchain`, mapping `c++*`, `gnu++*`, `none`, extension modes, and compiler support, and preserving CMake target overrides. The current architecture applies `TargetOptions` only after CMake analysis while generating Meson AST, so this is not a one-line follow-up.

## Required matrix

| Case | Required outcome |
| --- | --- |
| no CMake standard; project `cuda_std=c++20` | exactly C++20; unexplained CMake effective flag does not become a target override |
| explicit target `CUDA_STANDARD 17`; project C++20 | explicit target intent is retained or deliberately diagnosed |
| direct target `-std=c++17`; project C++20 | explicit compile-option intent is not silently lost |
| global/directory `CMAKE_CUDA_STANDARD 17`; project C++20 | no claim until target-scoped provenance is established |
| explicit Meson subproject override C++23 | C++23 wins over discovered and project values |
| mixed CXX/CUDA target | C++ and CUDA standards remain independently classified |
| GNU extension standards | extension mode is preserved rather than collapsed |
| unsupported standard | no silent semantic loss |

## Current decision

Keep the source PR in draft. The next implementation experiment is provenance-gated CUDA normalization, not promotion of the one-line loop expansion. The new compiler-free precedence control must pass before any production candidate is selected, and the current issue must not be described as resolved until the no-explicit-CMake-standard case leaves Meson's parent `cuda_std` authoritative.
