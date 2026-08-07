#!/usr/bin/env python3
"""Apply the base-complete Meson #15998 runtime-deferred candidate.

This is the authoritative entry point for an immutable public-base checkout.
`apply_deferred_candidate.py` contains the implementation/unit transformations;
this wrapper normalizes the public-base CUDA anchors and adds generated-AST
controls for the runtime fallback choice.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import apply_deferred_candidate as deferred


def apply_ast_tests(root: Path) -> None:
    path = root / "unittests/cmakeinterpreterasttests.py"
    path.write_text(
        """# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from unittest import TestCase, mock
import tempfile

from mesonbuild.ast import AstIndentationGenerator, AstPrinter
from mesonbuild.cmake.common import CMakeTarget, TargetOptions
from mesonbuild.cmake.interpreter import CMakeInterpreter, ConverterTarget
from mesonbuild.cmake.traceparser import CMakeTarget as CMakeTraceTarget
from mesonbuild.mesonlib import MachineChoice


class CMakeInterpreterAstTests(TestCase):

    def make_cuda_converter(self, root: Path) -> ConverterTarget:
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
            'cuda_target': CMakeTraceTarget('cuda_target', 'EXECUTABLE', {}),
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

    def render(self, converter: ConverterTarget, options: TargetOptions) -> str:
        cmake = object.__new__(CMakeInterpreter)
        cmake.project_name = 'cuda_project'
        cmake.project_version = ''
        cmake.languages = ['cuda']
        cmake.targets = [converter]
        cmake.custom_targets = []
        cmake.subdir = Path('subprojects/cuda_project')

        ast = cmake.pretend_to_be_meson(options)
        ast.accept(AstIndentationGenerator())
        printer = AstPrinter(update_ast_line_nos=True)
        ast.accept(printer)
        printer.post_process()
        return printer.result

    def test_unexplained_cuda_standard_emits_runtime_option_choice(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir))
            rendered = self.render(converter, TargetOptions())

            self.assertIn("get_option('cuda_std')", rendered)
            self.assertIn("?", rendered)
            self.assertIn("-std=c++17", rendered)
            self.assertIn("--generate-code=arch=compute_80,code=sm_80", rendered)

    def test_explicit_subproject_override_avoids_runtime_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            converter = self.make_cuda_converter(Path(tempdir))
            options = TargetOptions()
            options.global_options.set_opt('cuda_std', 'c++23')
            rendered = self.render(converter, options)

            self.assertNotIn("get_option('cuda_std')", rendered)
            self.assertNotIn("-std=c++17", rendered)
            self.assertIn("cuda_std=c++23", rendered)
            self.assertIn("--generate-code=arch=compute_80,code=sm_80", rendered)
""",
        encoding="utf-8",
    )


def apply_candidate(root: Path) -> None:
    interpreter = root / "mesonbuild/cmake/interpreter.py"
    deferred.replace_once(
        interpreter,
        """        # Detect setting the C and C++ standard and do additional compiler args manipulation
""",
        """        # Detect setting the C, C++ and CUDA standard and do additional compiler args manipulation
""",
        "include CUDA in standard-classification comment",
    )
    deferred.replace_once(
        interpreter,
        """        for i in T.cast('T.Tuple[Language, ...]', ('c', 'cpp')):
""",
        """        for i in T.cast('T.Tuple[Language, ...]', ('c', 'cpp', 'cuda')):
""",
        "include CUDA in standard classification",
    )
    deferred.apply_candidate(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--tests-only', action='store_true')
    args = parser.parse_args()

    root = args.root.resolve()
    deferred.apply_tests(root)
    apply_ast_tests(root)
    if not args.tests_only:
        apply_candidate(root)


if __name__ == '__main__':
    main()
