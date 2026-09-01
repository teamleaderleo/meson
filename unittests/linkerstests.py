# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Meson development team

from unittest import mock
import unittest

from mesonbuild.compilers.compilers import ManyInOneLinkerOptionStyle
from mesonbuild.linkers import linkers
from mesonbuild.mesonlib import MachineChoice

from run_tests import get_fake_env


class LinkerTests(unittest.TestCase):

    def test_gnuld_rpath_link_modern_bfd(self):
        env = get_fake_env()
        linker = linkers.GnuBFDDynamicLinker(
            [], env, MachineChoice.HOST,
            ManyInOneLinkerOptionStyle('-Wl,', ','), [], version='2.40')
        target = mock.Mock()
        target.determine_rpath_dirs.return_value = ['lib']
        target.install_rpath = ''
        target.build_rpath = ''
        args, _ = linker.build_rpath_args('/build', 'app', target)
        self.assertIn('-Wl,-rpath-link,/build/lib', args)
