#!/usr/bin/env python3
"""Apply the Meson #15998 deferred CUDA standard settlement candidate."""

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
        meson_std: str,
        compile_flags: str = '-std=c++17 --generate-code=arch=compute_80,code=sm_80',
        properties: dict[str, list[str]] | None = None,
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
        env.coredata.optstore.get_value_for.return_value = meson_std
        env.get_build_dir.return_value = str(build_dir)
        env.get_source_dir.return_value = str(root)

        converter = ConverterTarget(target, env, MachineChoice.HOST)
        converter._all_lang_stds = mock.Mock(
            return_value=['none', 'c++11', 'c++14', 'c++17', 'c++20', 'c++23', 'gnu++17'],
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

    def test_unexplained_standard_yields_to_parent_meson_standard(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir), meson_std='c++20')
            options = TargetOptions()

            converter.settle_deferred_stds(options)

            self.assertEqual(converter.override_options, [])
            self.assertEqual(
                converter.compile_opts['cuda'],
                ['--generate-code=arch=compute_80,code=sm_80'],
            )

    def test_unexplained_standard_survives_without_replacement_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir), meson_std='none')
            options = TargetOptions()

            converter.settle_deferred_stds(options)

            self.assertEqual(converter.override_options, [])
            self.assertEqual(
                converter.compile_opts['cuda'],
                [
                    '--generate-code=arch=compute_80,code=sm_80',
                    '-std=c++17',
                ],
            )

    def test_explicit_target_cuda_standard_becomes_override(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(
                Path(tempdir),
                meson_std='c++20',
                properties={'CUDA_STANDARD': ['17']},
            )
            options = TargetOptions()

            converter.settle_deferred_stds(options)

            self.assertEqual(converter.override_options, ['cuda_std=c++17'])
            self.assertNotIn('-std=c++17', converter.compile_opts['cuda'])

    def test_explicit_target_compile_option_becomes_override(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(
                Path(tempdir),
                meson_std='c++20',
                properties={'COMPILE_OPTIONS': ['-std=c++17']},
            )
            options = TargetOptions()

            converter.settle_deferred_stds(options)

            self.assertEqual(converter.override_options, ['cuda_std=c++17'])
            self.assertNotIn('-std=c++17', converter.compile_opts['cuda'])

    def test_global_subproject_override_suppresses_unexplained_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir), meson_std='none')
            options = TargetOptions()
            options.global_options.set_opt('cuda_std', 'c++23')

            converter.settle_deferred_stds(options)

            self.assertNotIn('-std=c++17', converter.compile_opts['cuda'])
            self.assertEqual(
                options.get_override_options('cuda_target', converter.override_options),
                ['cuda_std=c++23'],
            )

    def test_target_subproject_override_suppresses_unexplained_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir), meson_std='none')
            options = TargetOptions()
            options['cuda_target'].set_opt('cuda_std', 'c++23')

            converter.settle_deferred_stds(options)

            self.assertNotIn('-std=c++17', converter.compile_opts['cuda'])
            self.assertEqual(
                options.get_override_options('cuda_target', converter.override_options),
                ['cuda_std=c++23'],
            )

    def test_gnu_fallback_is_preserved_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(
                Path(tempdir),
                meson_std='none',
                compile_flags='-std=gnu++17 --generate-code=arch=compute_80,code=sm_80',
            )
            options = TargetOptions()

            converter.settle_deferred_stds(options)

            self.assertIn('-std=gnu++17', converter.compile_opts['cuda'])
            self.assertEqual(converter.override_options, [])
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
        """        # Project default override options (c_std, cpp_std, etc.)
        self.override_options: T.List[str] = []

        # Convert the target name to a valid meson target name
""",
        """        # Project default override options (c_std, cpp_std, etc.)
        self.override_options: T.List[str] = []

        # Effective standard flags whose ownership cannot be settled until
        # generated target options and the surrounding Meson default are known.
        self.deferred_std_flags: T.Dict[Language, str] = {}

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
        """                    self.override_options += [f'{i}_std={std}']
""",
        """                    if i == 'cuda' and not self._has_explicit_cmake_standard(trace_target, i, std):
                        self.deferred_std_flags[i] = j
                    else:
                        self.override_options += [f'{i}_std={std}']
""",
        "defer unexplained CUDA standard",
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
        """    def settle_deferred_stds(self, target_options: 'TargetOptions') -> None:
        for lang, flag in self.deferred_std_flags.items():
            opt = f'{lang}_std'
            if target_options.has_override_option(self.cmake_name, opt):
                continue

            try:
                meson_std = self.env.coredata.optstore.get_value_for(
                    OptionKey(opt, machine=self.for_machine),
                )
            except KeyError:
                meson_std = 'none'

            if meson_std == 'none':
                self.compile_opts[lang].append(flag)

        self.deferred_std_flags.clear()

    def process_inter_target_dependencies(self) -> None:
""",
        "deferred standard settlement",
    )
    replace_once(
        interpreter,
        """            install_tgt = options.get_install(tgt.cmake_name, tgt.install)

            # Generate target kwargs
""",
        """            install_tgt = options.get_install(tgt.cmake_name, tgt.install)
            tgt.settle_deferred_stds(options)

            # Generate target kwargs
""",
        "settle standards before target kwargs",
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
