# Meson 15998 design boundary

## Current conclusion

The one-line CUDA normalization candidate is valid language-classification and duplicate-removal evidence, but it does **not** satisfy the issue's precedence contract.

A second provenance-gated candidate was rejected before execution. Provenance alone is insufficient: removing an unexplained effective CUDA standard is safe only when another authority will replace it.

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

## Architecture finding: generation time is still too early for Meson subproject options

`ConverterTarget.postprocess()` is too early to settle an unexplained File API CUDA standard. It only sees the effective CMake compile fragment plus trace information.

A first deferred design then tried to settle the fragment while `CMakeInterpreter.pretend_to_be_meson()` generated the Meson AST. Static review rejected that timing too.

The CMake flow is:

1. `CMakeInterpreter` configures and analyses CMake;
2. `pretend_to_be_meson()` generates a Meson AST;
3. only then `_do_subproject_meson()` constructs the real Meson subproject `Interpreter` with the caller's `default_options`, command-line and machine-file option state;
4. that interpreter parses `project()` and exposes the final subproject-scoped value through `get_option()` while executing the generated AST.

`OptionStore.get_value_for(OptionKey('cuda_std', machine=...))` without a subproject key resolves the root/global compiler option. Per-subproject compiler values and augments can differ. Therefore an OptionStore query during CMake AST generation cannot be the production authority for the generated subproject.

The narrow safe timing boundary is now: **record the unexplained fallback during conversion, but choose raw-versus-clean compile arguments in the generated Meson program itself**, using the generated subproject's runtime `get_option('cuda_std')`.

## Provenance sources available today

### File API file group

`CMakeFileGroup.language` and source suffixes determine the Meson language bucket. `compileFlags` supplies effective raw flags. This identifies a CUDA standard fragment but does not explain why it exists.

### CMake trace target properties

The trace parser records `set_property(TARGET ...)`, `set_target_properties(...)`, and `target_compile_options()` values in `trace.targets[name].properties`. Explicit target `CUDA_STANDARD` and direct target `-std=` intent can therefore be distinguished from an otherwise unexplained effective flag.

### CMake trace variables

The parser retains final variables and per-file assignments, including directly written `CMAKE_CUDA_STANDARD`. This is useful evidence but not a complete directory-scope timeline. A final variable value can differ from the value that initialized a particular target, so it is not safe by itself as universal target provenance.

### Meson project and subproject authority

Explicit global or target `cmake.subproject_options()` values are already known at AST generation through `TargetOptions` and can statically suppress an unexplained fallback.

Ordinary Meson compiler-option authority is different. The final subproject-scoped `cuda_std` is only reliable after the generated Meson subproject interpreter is constructed and its `project()` state is resolved. That value is available naturally to generated code via `get_option('cuda_std')`.

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

Policy B silently drops that standard and falls back to compiler defaults. Execution PR #6 and workflow run `31019630325` were retired while queued and are not behavior evidence.

### Policy C1 — settle against OptionStore while generating the AST

Status: `REJECT BEFORE EXECUTION / RETAIN AS STATIC REVIEW FINDING`.

This generation correctly introduced replacement authority but queried it too early. A root/global `OptionKey('cuda_std')` does not prove the final value inside the generated CMake subproject, because subproject `default_options`, command-line augments, and machine-file augments are resolved when the real subproject interpreter is constructed after AST generation.

No carrier was created for C1 and it carries no behavior evidence.

### Policy C2 — runtime-deferred fallback in generated Meson

Status: `SELECTED NEXT EXPERIMENT / TRANSFORMER PREPARED / UNEXECUTED`.

`fieldwork/15998/apply_deferred_candidate.py` now prepares this generation.

Conversion behavior:

1. reliable explicit target CMake `CUDA_STANDARD` or matching direct target `-std=` provenance becomes a generated `cuda_std=...` target override;
2. a supported but unexplained effective CUDA `-std=` remains in the raw compile-argument list at its original position and is also recorded as deferred metadata;
3. an unsupported CUDA `-std=` is retained raw rather than newly being discarded by CUDA normalization;
4. unrelated CUDA arguments remain untouched.

AST-generation behavior:

1. a global or target-specific `cmake.subproject_options().set_override_option('cuda_std', ...)` is known through `TargetOptions`, so the generated target uses the clean compile-argument list directly;
2. otherwise the generated `cuda_args` value is a Meson ternary:
   - if `get_option('cuda_std') == 'none'`, use the original raw list including the unexplained CMake fallback;
   - otherwise use the clean list with only the discovered fallback removed.

The branch pair is computed before the runtime choice, and removal operates on the converter-owned base list before `TargetOptions.append_compile_args()` is applied. This prevents an explicitly appended argument equal to the discovered fallback from being accidentally removed.

This design preserves compile-argument ordering when fallback is needed and resolves ordinary Meson project/subproject authority at the stage where it is actually final.

### Policy D — propagate Meson standards into the generated CMake toolchain

Status: `HOLD AS BROADER DESIGN`.

Mapping Meson standards into CMake before configuration would require a wider ownership redesign, including `c++*`/`gnu++*`, `none`, extension modes, compiler support, and precedence against target-level CMake settings. It is no longer the preferred next experiment.

## Required next controls

The prepared transformer carries compiler-free controls for its local classification and branch-building helpers. Before any source can be described as a fix, execution must also prove the generated Meson runtime choice.

| Case | Required outcome |
| --- | --- |
| no explicit CMake standard; generated subproject `cuda_std=c++20` | clean args selected; no generated target override |
| no explicit CMake standard; generated subproject `cuda_std=none` | original raw `-std=` fallback retained in place |
| subproject `default_options: cuda_std=c++20` | same clean branch; proves late subproject resolution |
| command-line or machine-file subproject `cuda_std` augment | clean branch; proves AST-generation timing is no longer authoritative |
| explicit target `CUDA_STANDARD 17`; project C++20 | generated explicit target intent wins unless later CMake-module override replaces it |
| direct target `-std=c++17`; project C++20 | explicit target compile-option intent is not silently lost |
| explicit global `cmake.subproject_options()` C++23 | C++23 wins and no unexplained raw fallback survives |
| target-specific `cmake.subproject_options()` C++23 | target C++23 wins over generated and fallback values |
| appended compile arg equal to fallback | appended arg survives cleanup |
| GNU extension standard | extension form is preserved |
| unsupported CUDA standard | raw flag is retained rather than silently dropped |
| mixed CXX/CUDA target | C++ and CUDA standards remain independently classified |
| global/directory `CMAKE_CUDA_STANDARD 17`; project C++20 | no production claim until target-creation provenance or intended precedence is explicit |

The mandatory negative control remains: unexplained effective CUDA standard + runtime `cuda_std=none` + no `TargetOptions` override must retain the effective standard.

## Current decision

Keep source PR #3 draft and research-only.

- Policy A remains executed classification evidence, not an issue fix.
- Policy B is rejected because it lacks replacement authority.
- Policy C1 is rejected because AST-generation OptionStore lookup is too early for subproject-scoped authority.
- Policy C2 is the current candidate because the generated Meson program can query the final subproject option at execution time while still preserving explicit `TargetOptions` precedence.
- The C2 transformer is prepared but unexecuted. Static review must finish before any read-only carrier is created.

The issue must not be described as resolved until the reporter's parent-authority case, the no-replacement-authority compatibility case, and at least one genuinely subproject-scoped late-option case are executed successfully. The directory/global CMake-standard provenance caveat remains explicitly bounded.