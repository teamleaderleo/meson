# Fieldwork: CMake CUDA standard normalization

Upstream issue: https://github.com/mesonbuild/meson/issues/15998

External contact: **not authorized and not performed**

## Reported behavior

A converted CMake target containing CUDA sources can receive both the top-level C++ standard and an unstripped CMake CUDA `-std=` flag. The issue report shows `-std=c++23` and `-std=c++17` on the same NVCC command despite `cuda_std=c++20` being configured.

## Current source boundary

`ConverterTarget` already maps CMake language `CUDA` to Meson language `cuda` and stores file-group flags in `compile_opts['cuda']`. Its standard normalization pass, however, only iterates `c` and `cpp`. As a result, a CUDA `-std=` option is left in raw compile arguments and never becomes a `cuda_std=...` target override.

## Candidate

`candidate.patch` extends the existing normalization pass to `cuda`. The focused unit test constructs a synthetic CMake File API target with a CUDA file group, avoiding a real CUDA compiler. It requires that:

- `-std=c++17` is removed from raw CUDA compile arguments;
- the target records `cuda_std=c++17` rather than `cpp_std=...`;
- unrelated NVCC arguments remain intact;
- the existing C and C++ path is unchanged by construction.

## Important unresolved contract

This candidate proves language classification and deduplication only. It does **not** yet decide precedence between:

1. a standard discovered in CMake File API compile flags;
2. a Meson top-level `cuda_std` project option;
3. an explicit `cmake.subproject_options().set_override_option('cuda_std', ...)` value.

Current C/C++ conversion turns a discovered CMake standard into a target override, which can legitimately outrank a project default. We should not silently change that cross-language contract merely to match one report. The next integration matrix must distinguish an explicit CMake `CUDA_STANDARD` from a compiler/default-generated `-std=` flag and verify explicit subproject overrides.

## Planned gates

1. Run the synthetic unit test before and after `candidate.patch`.
2. Run existing CMake interpreter/unit coverage.
3. Build a real CMake subproject matrix when a CUDA toolchain is available:
   - no CMake standard, Meson `cuda_std=c++20`;
   - explicit CMake `CUDA_STANDARD 17`;
   - explicit Meson subproject override;
   - mixed C++ and CUDA sources in one target.

Evidence state: `source-mapped`, candidate and compiler-free regression prepared; no production claim yet.
