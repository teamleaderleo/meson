# Fieldwork: CMake CUDA standard normalization

Upstream issue: https://redirect.github.com/mesonbuild/meson/issues/15998

External contact: **not authorized and not performed**

## Reported behavior

A converted CMake target containing CUDA sources can receive both the top-level standard and an unstripped CMake CUDA `-std=` flag. The issue report shows conflicting standard flags on the same NVCC command even though a Meson `cuda_std` value is configured.

## Source boundary

`ConverterTarget` maps CMake language `CUDA` to Meson language `cuda` and stores file-group flags in `compile_opts['cuda']`. The original standard-normalization pass visited only C and C++, leaving a CUDA `-std=` option in raw compiler arguments.

## Executed classification probe

The one-line source candidate extends the existing normalization loop to CUDA. Focused run `30858277753` established on a compiler-free synthetic File API target that:

- `-std=c++17` is removed from raw CUDA compile arguments;
- the target records `cuda_std=c++17` rather than `cpp_std=...`;
- unrelated NVCC arguments remain intact;
- Python compilation and diff hygiene pass.

Evidence class: `compiler-free-target-executed` for language classification and raw duplicate removal only.

## Why the one-line candidate is incomplete

Turning every effective CUDA standard into a generated target override defeats an ordinary parent-project `cuda_std`. Explicit `cmake.subproject_options()` overrides still replace that value, but the reporter's no-explicit-CMake-standard case remains wrong.

## Rejected provenance-only candidate

`apply_provenance_candidate.py` records a later design generation that would remove every effective raw CUDA standard and emit a target override only for traced explicit target `CUDA_STANDARD` or direct target `-std=` intent.

Independent design review found a blocking no-replacement-authority case before execution:

- no explicit target CMake provenance;
- no Meson parent/subproject `cuda_std` authority;
- File API reports the only effective CUDA standard.

Removing that standard would silently fall back to compiler defaults. Provenance alone is therefore insufficient.

Execution PR #6 and run `31019630325` were retired while queued. They are not behavior evidence. The temporary workflow was removed from the default branch.

## Current design requirement

A safe repair needs both:

1. provenance for the effective CMake standard;
2. knowledge that another deliberate standard authority will replace it.

The next implementation must preserve both cases:

- parent Meson `cuda_std` wins when CMake has no explicit target standard;
- an unexplained effective CMake standard remains when Meson supplies no replacement authority.

Possible boundaries are passing effective project/subproject `cuda_std` into conversion, deferring the decision until target AST generation, or moving Meson standard authority into the generated CMake toolchain.

`DESIGN.md` records the full matrix and rejected generations.

## Current state

`RESEARCH HOLD — CLASSIFICATION PROBE GREEN — PRODUCTION POLICY NOT SELECTED`.

No source on this branch should be described as a complete fix for issue #15998.
