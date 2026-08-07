#!/usr/bin/env python3
"""Apply the Meson #15998 runtime-deferred CUDA standard candidate."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply_tests(root: Path) -> None:
    path = root / "unittests/cmakeinterpretertests.py"
    path.write_text(
        """# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from unittest import TestCase, mock
import tempfile

from mesonbuild.cmake.common import CMakeTarget, TargetOptions
from mesonbuild.cmake.interpreter import ConverterTarget
from mesonbuild.cmake.traceparser import CMakeTarget as CMakeTraceTarget
from mesonbuild.mesonlib import MachineChoice


class CMakeInterpreterTests(TestCase):

    def make_cuda_converter(
        self,
        root: Path,
        *,
        compile_flags: str = '-std=c++17 --generate-code=arch=compute_80,code=sm_80',
        properties: dict[str, list[str]] | None = None,
        supported: list[str] | None = None,
    ) -> ConverterTarget:
        source = root / 'kernel.cu'
        source.write_text('__global__ void kernel() {}\\n', encoding='utf-8')
        build_dir = root / 'build'
        build_dir.mkdir()

        target = CMakeTarget({
            'sourceDirectory': str(root),
            'buildDirectory': str(build_dir),
            'name': 'cuda_target',
            'fullName': 'cuda_target',
            'type': 'EXECUTABLE',
            'fileGroups': [{
                'language': 'CUDA',
                'compileFlags': compile_flags,
                'sources': [str(source)],
            }],
        })

        env = mock.Mock()
        env.coredata.compilers = {MachineChoice.HOST: {}}
        env.get_build_dir.return_value = str(build_dir)
        env.get_source_dir.return_value = str(root)

        converter = ConverterTarget(target, env, MachineChoice.HOST)
        converter._all_lang_stds = mock.Mock(
            return_value=supported or ['none', 'c++11', 'c++14', 'c++17', 'c++20', 'c++23', 'gnu++17'],
        )

        output_target_map = mock.Mock()
        output_target_map.generated.return_value = None
        output_target_map.artifact.return_value = None

        trace = mock.Mock()
        trace.targets = {
            'cuda_target': CMakeTraceTarget(
                'cuda_target',
                'EXECUTABLE',
                properties or {},
            ),
        }
        trace.explicit_headers = set()

        resolved = mock.Mock()
        resolved.include_directories = []
        resolved.link_flags = []
        resolved.public_link_flags = []
        resolved.public_compile_opts = []
        resolved.libraries = []
        resolved.target_dependencies = []

        with mock.patch(
            'mesonbuild.cmake.interpreter.resolve_cmake_trace_targets',
            return_value=resolved,
        ):
            converter.postprocess(
                output_target_map,
                root,
                Path('.'),
                Path('/usr/local'),
                trace,
            )
        return converter

    def test_unexplained_cuda_standard_is_deferred_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir))

            self.assertEqual(converter.override_options, [])
            self.assertEqual(converter.deferred_std_flags, {'cuda': ['-std=c++17']})
            self.assertEqual(
                converter.compile_opts['cuda'],
                [
                    '-std=c++17',
                    '--generate-code=arch=compute_80,code=sm_80',
                ],
            )

    def test_deferred_args_offer_raw_and_clean_runtime_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir))
            options = TargetOptions()

            raw, clean, runtime = converter.compile_args_with_deferred_std(options, 'cuda')

            self.assertTrue(runtime)
            self.assertEqual(
                raw,
                [
                    '-std=c++17',
                    '--generate-code=arch=compute_80,code=sm_80',
                ],
            )
            self.assertEqual(clean, ['--generate-code=arch=compute_80,code=sm_80'])

    def test_subproject_override_selects_clean_args_without_runtime_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir))
            options = TargetOptions()
            options.global_options.set_opt('cuda_std', 'c++23')

            selected, clean, runtime = converter.compile_args_with_deferred_std(options, 'cuda')

            self.assertFalse(runtime)
            self.assertEqual(selected, ['--generate-code=arch=compute_80,code=sm_80'])
            self.assertEqual(clean, selected)
            self.assertEqual(
                options.get_override_options('cuda_target', converter.override_options),
                ['cuda_std=c++23'],
            )

    def test_appended_same_flag_is_not_removed_with_discovered_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir))
            options = TargetOptions()
            options.global_options.append_args('cuda', ['-std=c++17'])

            raw, clean, runtime = converter.compile_args_with_deferred_std(options, 'cuda')

            self.assertTrue(runtime)
            self.assertEqual(raw.count('-std=c++17'), 2)
            self.assertEqual(clean.count('-std=c++17'), 1)

    def test_explicit_target_cuda_standard_becomes_override(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(
                Path(tempdir),
                properties={'CUDA_STANDARD': ['17']},
            )

            self.assertEqual(converter.override_options, ['cuda_std=c++17'])
            self.assertEqual(converter.deferred_std_flags, {})
            self.assertNotIn('-std=c++17', converter.compile_opts['cuda'])

    def test_explicit_target_compile_option_becomes_override(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(
                Path(tempdir),
                properties={'COMPILE_OPTIONS': ['-std=c++17']},
            )

            self.assertEqual(converter.override_options, ['cuda_std=c++17'])
            self.assertEqual(converter.deferred_std_flags, {})
            self.assertNotIn('-std=c++17', converter.compile_opts['cuda'])

    def test_gnu_fallback_is_preserved_verbatim_and_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(
                Path(tempdir),
                compile_flags='-std=gnu++17 --generate-code=arch=compute_80,code=sm_80',
            )

            self.assertEqual(converter.deferred_std_flags, {'cuda': ['-std=gnu++17']})
            self.assertEqual(
                converter.compile_opts['cuda'],
                [
                    '-std=gnu++17',
                    '--generate-code=arch=compute_80,code=sm_80',
                ],
            )

    def test_unknown_cuda_standard_stays_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(
                Path(tempdir),
                compile_flags='-std=c++99 --generate-code=arch=compute_80,code=sm_80',
                supported=['none', 'c++17', 'c++20'],
            )

            self.assertEqual(converter.override_options, [])
            self.assertEqual(converter.deferred_std_flags, {})
            self.assertEqual(
                converter.compile_opts['cuda'],
                [
                    '-std=c++99',
                    '--generate-code=arch=compute_80,code=sm_80',
                ],
            )
""",
        encoding="utf-8",
    )


def apply_candidate(root: Path) -> None:
    common = root / "mesonbuild/cmake/common.py"
    replace_once(
        common,
        """    def set_opt(self, opt: str, val: str) -> None:
        self.opts[opt] = val

    def append_args(self, lang: str, args: T.List[str]) -> None:
""",
        """    def set_opt(self, opt: str, val: str) -> None:
        self.opts[opt] = val

    def has_override_option(self, opt: str) -> bool:
        return opt in self.opts

    def append_args(self, lang: str, args: T.List[str]) -> None:
""",
        "single-target override query",
    )
    replace_once(
        common,
        """    def get_override_options(self, tgt: str, initial: T.List[str]) -> T.List[str]:
        initial = self.global_options.get_override_options(initial)
        if tgt in self.target_options:
            initial = self.target_options[tgt].get_override_options(initial)
        return initial

    def get_compile_args(self, tgt: str, lang: str, initial: T.List[str]) -> T.List[str]:
""",
        """    def get_override_options(self, tgt: str, initial: T.List[str]) -> T.List[str]:
        initial = self.global_options.get_override_options(initial)
        if tgt in self.target_options:
            initial = self.target_options[tgt].get_override_options(initial)
        return initial

    def has_override_option(self, tgt: str, opt: str) -> bool:
        if self.global_options.has_override_option(opt):
            return True
        return tgt in self.target_options and self.target_options[tgt].has_override_option(opt)

    def get_compile_args(self, tgt: str, lang: str, initial: T.List[str]) -> T.List[str]:
""",
        "target override query",
    )

    interpreter = root / "mesonbuild/cmake/interpreter.py"
    replace_once(
        interpreter,
        """from .traceparser import CMakeTraceParser
""",
        """from .traceparser import CMakeTarget as CMakeTraceTarget, CMakeTraceParser
""",
        "trace target import",
    )
    replace_once(
        interpreter,
        """    BooleanNode,
    StringNode,
    IdNode,
""",
        """    BooleanNode,
    StringNode,
    IdNode,
    ComparisonNode,
    TernaryNode,
""",
        "runtime conditional AST imports",
    )
    replace_once(
        interpreter,
        """        # Project default override options (c_std, cpp_std, etc.)
        self.override_options: T.List[str] = []

        # Convert the target name to a valid meson target name
""",
        """        # Project default override options (c_std, cpp_std, etc.)
        self.override_options: T.List[str] = []

        # Effective standard flags whose ownership cannot be settled until the
        # generated Meson subproject resolves its real language options.
        self.deferred_std_flags: T.Dict[Language, T.List[str]] = {}

        # Convert the target name to a valid meson target name
""",
        "deferred standard storage",
    )
    replace_once(
        interpreter,
        """    std_regex = re.compile(r'([-]{1,2}std=|/std:v?|[-]{1,2}std:)(.*)')

    def postprocess(self, output_target_map: OutputTargetMap, root_src_dir: Path, subdir: Path, install_prefix: Path, trace: CMakeTraceParser) -> None:
""",
        """    std_regex = re.compile(r'([-]{1,2}std=|/std:v?|[-]{1,2}std:)(.*)')

    @staticmethod
    def _has_explicit_cmake_standard(
        target: T.Optional[CMakeTraceTarget],
        lang: Language,
        std: str,
    ) -> bool:
        if lang != 'cuda':
            return True
        if target is None:
            return False

        for value in target.properties.get('CUDA_STANDARD', []):
            if std in {value, f'c++{value}', f'gnu++{value}'}:
                return True

        for option in target.properties.get('COMPILE_OPTIONS', []):
            match = ConverterTarget.std_regex.match(option)
            if match and match.group(2) == std:
                return True

        return False

    def postprocess(self, output_target_map: OutputTargetMap, root_src_dir: Path, subdir: Path, install_prefix: Path, trace: CMakeTraceParser) -> None:
""",
        "explicit CMake standard helper",
    )
    replace_once(
        interpreter,
        """        # Detect setting the C, C++ and CUDA standard and do additional compiler args manipulation

        # https://github.com/python/mypy/issues/18826
""",
        """        # Detect setting the C, C++ and CUDA standard and do additional compiler args manipulation
        trace_target = trace.targets.get(self.cmake_name)

        # https://github.com/python/mypy/issues/18826
""",
        "early trace target lookup",
    )
    replace_once(
        interpreter,
        """                    if std not in supported:
                        mlog.warning(
                            'Unknown {0}_std \"{1}\" -> Ignoring. Try setting the project-'
                            'level {0}_std if build errors occur. Known '
                            '{0}_stds are: {2}'.format(i, std, ' '.join(supported)),
                            once=True
                        )
                        continue
                    self.override_options += [f'{i}_std={std}']
""",
        """                    if std not in supported:
                        if i == 'cuda':
                            mlog.warning(
                                'Unknown cuda_std \"{}\" -> Keeping the raw CUDA compiler flag. Known cuda_stds are: {}'.format(
                                    std, ' '.join(supported)
                                ),
                                once=True,
                            )
                            temp += [j]
                        else:
                            mlog.warning(
                                'Unknown {0}_std \"{1}\" -> Ignoring. Try setting the project-'
                                'level {0}_std if build errors occur. Known '
                                '{0}_stds are: {2}'.format(i, std, ' '.join(supported)),
                                once=True
                            )
                        continue
                    if i == 'cuda' and not self._has_explicit_cmake_standard(trace_target, i, std):
                        self.deferred_std_flags.setdefault(i, []).append(j)
                        temp += [j]
                    else:
                        self.override_options += [f'{i}_std={std}']
""",
        "defer unexplained and preserve unknown CUDA standard",
    )
    replace_once(
        interpreter,
        """        # Use the CMake trace, if required
        tgt = trace.targets.get(self.cmake_name)
        if tgt:
""",
        """        # Use the CMake trace, if required
        tgt = trace_target
        if tgt:
""",
        "single trace target lookup",
    )
    replace_once(
        interpreter,
        """    def process_inter_target_dependencies(self) -> None:
""",
        """    def compile_args_with_deferred_std(
        self,
        target_options: 'TargetOptions',
        lang: Language,
    ) -> T.Tuple[T.List[str], T.List[str], bool]:
        initial = self.compile_opts[lang]
        deferred = self.deferred_std_flags.get(lang, [])
        raw = target_options.get_compile_args(self.cmake_name, lang, initial)
        if not deferred:
            return raw, raw, False

        clean = list(initial)
        for flag in deferred:
            try:
                clean.remove(flag)
            except ValueError:
                pass
        clean = target_options.get_compile_args(self.cmake_name, lang, clean)

        if target_options.has_override_option(self.cmake_name, f'{lang}_std'):
            return clean, clean, False
        return raw, clean, True

    def process_inter_target_dependencies(self) -> None:
""",
        "deferred compile-argument branches",
    )
    replace_once(
        interpreter,
        """            # Handle compiler args
            for key, val in tgt.compile_opts.items():
                tgt_kwargs[f'{key}_args'] = options.get_compile_args(tgt.cmake_name, key, val)
""",
        """            # Handle compiler args. An unexplained CUDA standard remains a
            # fallback only when the generated subproject's resolved cuda_std is none.
            for key in tgt.compile_opts:
                raw_args, clean_args, needs_runtime_choice = tgt.compile_args_with_deferred_std(options, key)
                if needs_runtime_choice:
                    condition = ComparisonNode(
                        '==',
                        function('get_option', [f'{key}_std']),
                        symbol('=='),
                        string('none'),
                    )
                    tgt_kwargs[f'{key}_args'] = TernaryNode(
                        condition,
                        symbol('?'),
                        array(raw_args),
                        symbol(':'),
                        array(clean_args),
                    )
                else:
                    tgt_kwargs[f'{key}_args'] = clean_args
""",
        "runtime deferred standard choice",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--tests-only', action='store_true')
    args = parser.parse_args()

    root = args.root.resolve()
    apply_tests(root)
    if not args.tests_only:
        apply_candidate(root)


if __name__ == '__main__':
    main()
