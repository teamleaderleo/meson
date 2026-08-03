# Meson 15998 design boundary

## Why the one-line candidate is incomplete

The CMake File API reports effective compile flags. An effective `-std=c++17` fragment does not by itself say whether the project explicitly requested C++17, CMake selected it from a global variable, or the compiler/toolchain injected it as a default.

Turning every such fragment into a Meson target override fixes language classification and removes a duplicate, but it can also make an inferred/default CMake value outrank the user's top-level Meson `cuda_std`.

## Provenance sources available today

### File API file group

`CMakeFileGroup.language` and source suffixes determine the Meson language bucket. `compileFlags` supplies the effective raw flags. This is enough to associate `-std=` with `cuda`, but not enough to prove why the flag exists.

### CMake trace target properties

The trace parser records arbitrary values from `set_property(TARGET ...)` and `set_target_properties(...)` in `trace.targets[name].properties`. Therefore an explicitly traced target property such as `CUDA_STANDARD` can be distinguished from an otherwise unexplained effective flag.

Limit: a project may set `CMAKE_CUDA_STANDARD` as a directory/global variable and let CMake initialize the target property internally. That initialization is not necessarily represented by an explicit `set_target_properties` trace call.

### Meson subproject overrides

`TargetOptions.get_override_options()` removes an initial option with the same key and appends the explicit global/target subproject override. An explicit `cmake.subproject_options().set_override_option('cuda_std', ...)` therefore has an existing mechanism to outrank a discovered initial override.

### Meson project default

A converted target-level `cuda_std=...` override naturally outranks the parent project's default. This is the dangerous case when the discovered value has no explicit provenance.

## Candidate policies

### Policy A — normalize every CUDA `-std=` fragment

- Pros: mirrors current C/C++ behavior; removes duplicates; preserves effective CMake commands.
- Cons: can preserve a compiler/default-generated value as a target override and defeat the requested Meson project default.

### Policy B — strip unexplained CUDA `-std=` fragments; override only explicit trace properties

- Pros: lets Meson project `cuda_std` win unless CMake explicitly requested a target standard.
- Cons: may lose standards initialized through `CMAKE_CUDA_STANDARD` or other CMake mechanisms not represented as explicit target-property trace events.

### Policy C — propagate Meson standards into the generated CMake toolchain

Map Meson `cpp_std`/`cuda_std` into CMake `CMAKE_CXX_STANDARD`/`CMAKE_CUDA_STANDARD` plus extension mode before configuring the subproject, then normalize the resulting effective flags.

- Pros: aligns CMake generation with the Meson project defaults and avoids starting from an unrelated compiler default.
- Cons: broad cross-language behavior change; needs mapping for `gnu++*`, `c++*`, `none`, compiler support, explicit CMake project settings, and subproject override precedence.

## Required matrix

| Case | Expected question |
| --- | --- |
| no CMake standard; project `cuda_std=c++20` | Does the converted CUDA command contain exactly C++20? |
| explicit target `CUDA_STANDARD 17`; project C++20 | Does explicit CMake intent win, warn, or get overridden? |
| global `CMAKE_CUDA_STANDARD 17`; project C++20 | Can provenance be recovered, and which contract wins? |
| explicit Meson subproject override C++23 | Does it outrank both discovered and project defaults? |
| mixed CXX/CUDA target | Are C++ and CUDA standards independently classified? |
| GNU extension standards | Are `gnu++*` and `CXX_EXTENSIONS`/`CUDA_EXTENSIONS` preserved? |
| unsupported standard | Is the flag retained, warned, or rejected without silent semantic loss? |

## Current decision

Keep the one-line candidate as an executable classification/deduplication probe only. Do not mark the fork draft ready or describe it as resolving the issue until the matrix identifies the intended provenance and precedence policy.
