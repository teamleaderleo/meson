# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from unittest import TestCase, mock
import tempfile

from mesonbuild.cmake.common import CMakeTarget
from mesonbuild.cmake.interpreter import ConverterTarget
from mesonbuild.mesonlib import MachineChoice


class CMakeInterpreterTests(TestCase):

    def test_cuda_standard_is_normalized_as_cuda_override(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            source = root / 'kernel.cu'
            source.write_text('__global__ void kernel() {}\n', encoding='utf-8')
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
            converter._all_lang_stds = mock.Mock(return_value=['none', 'c++11', 'c++14', 'c++17', 'c++20', 'c++23'])

            output_target_map = mock.Mock()
            output_target_map.generated.return_value = None
            output_target_map.artifact.return_value = None

            trace = mock.Mock()
            trace.targets = {}
            trace.explicit_headers = set()

            converter.postprocess(output_target_map, root, Path('.'), Path('/usr/local'), trace)

            self.assertEqual(converter.override_options, ['cuda_std=c++17'])
            self.assertEqual(
                converter.compile_opts['cuda'],
                ['--generate-code=arch=compute_80,code=sm_80'],
            )
            converter._all_lang_stds.assert_called_once_with('cuda')
