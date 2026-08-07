#!/usr/bin/env python3
"""Apply the Meson #15998 provenance-gated CUDA standard candidate."""

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
        properties: dict[str, list[str]] | None = None,
    ) -> tuple[ConverterTarget, mock.Mock]:
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
                'compileFlags': '-std=c++17 --generate-code=arch=compute_80,code=sm_80',
                'sources': [str(source)],
            }],
        })

        env = mock.Mock()
        env.coredata.compilers = {MachineChoice.HOST: {}}
        env.get_build_dir.return_value = str(build_dir)
        env.get_source_dir.return_value = str(root)

        converter = ConverterTarget(target, env, MachineChoice.HOST)
        converter._all_lang_stds = mock.Mock(
            return_value=['none', 'c++11', 'c++14', 'c++17', 'c++20', 'c++23'],
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
        return converter, converter._all_lang_stds

    def test_unexplained_cuda_standard_is_removed_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter, all_lang_stds = self.make_cuda_converter(Path(tempdir))

            self.assertEqual(converter.override_options, [])
            self.assertEqual(
                converter.compile_opts['cuda'],
                ['--generate-code=arch=compute_80,code=sm_80'],
            )
            all_lang_stds.assert_called_once_with('cuda')

    def test_explicit_target_cuda_standard_becomes_override(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter, _ = self.make_cuda_converter(
                Path(tempdir),
                {'CUDA_STANDARD': ['17']},
            )

            self.assertEqual(converter.override_options, ['cuda_std=c++17'])

    def test_explicit_target_compile_option_becomes_override(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter, _ = self.make_cuda_converter(
                Path(tempdir),
                {'COMPILE_OPTIONS': ['-std=c++17']},
            )

            self.assertEqual(converter.override_options, ['cuda_std=c++17'])

    def test_explicit_subproject_cuda_override_remains_final(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter, _ = self.make_cuda_converter(Path(tempdir))
            options = TargetOptions()

            # An unexplained effective standard no longer becomes a target
            # override, so an ordinary parent-project cuda_std can remain the
            # default outside this generated target option list.
            self.assertEqual(
                options.get_override_options('cuda_target', converter.override_options),
                [],
            )

            options.global_options.set_opt('cuda_std', 'c++20')
            self.assertEqual(
                options.get_override_options('cuda_target', converter.override_options),
                ['cuda_std=c++20'],
            )

            options['cuda_target'].set_opt('cuda_std', 'c++23')
            self.assertEqual(
                options.get_override_options('cuda_target', converter.override_options),
                ['cuda_std=c++23'],
            )
""",
        encoding="utf-8",
    )


def apply_candidate(root: Path) -> None:
    path = root / "mesonbuild/cmake/interpreter.py"
    replace_once(
        path,
        """from .traceparser import CMakeTraceParser
""",
        """from .traceparser import CMakeTarget as CMakeTraceTarget, CMakeTraceParser
""",
        "trace target import",
    )
    replace_once(
        path,
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
        path,
        """        # Detect setting the C, C++ and CUDA standard and do additional compiler args manipulation

        # https://github.com/python/mypy/issues/18826
""",
        """        # Detect setting the C, C++ and CUDA standard and do additional compiler args manipulation
        tgt = trace.targets.get(self.cmake_name)

        # https://github.com/python/mypy/issues/18826
""",
        "early trace target lookup",
    )
    replace_once(
        path,
        """                    self.override_options += [f'{i}_std={std}']
""",
        """                    if self._has_explicit_cmake_standard(tgt, i, std):
                        self.override_options += [f'{i}_std={std}']
""",
        "provenance-gated override",
    )
    replace_once(
        path,
        """        # Use the CMake trace, if required
        tgt = trace.targets.get(self.cmake_name)
        if tgt:
""",
        """        # Use the CMake trace, if required
        if tgt:
""",
        "single trace target lookup",
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
