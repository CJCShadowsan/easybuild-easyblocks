##
# Copyright 2013 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
##
"""
EasyBuild support for building and installing PSI, implemented as an easyblock

@author: Kenneth Hoste (Ghent University)
@author: Ward Poelmans (Ghent University)
"""

import os
import shutil

import easybuild.tools.environment as env
from easybuild.easyblocks.generic.configuremake import ConfigureMake
from easybuild.framework.easyconfig import BUILD
from easybuild.tools.modules import get_software_root


class EB_PSI(ConfigureMake):
    """
    Support for building and installing PSI
    """

    def __init__(self, *args, **kwargs):
        """Initialize class variables custom to PSI."""
        super(EB_PSI, self).__init__(*args, **kwargs)

        self.psi_srcdir = None
        self.install_psi_objdir = None
        self.install_psi_srcdir = None

    @staticmethod
    def extra_options():
        """Extra easyconfig parameters specific to PSI."""

        extra_vars = [
            # always include running PSI unit tests (takes about 2h or less)
            ('runtest', ["tests TESTFLAGS='-u -q'", "Run tests included with PSI, without interruption.", BUILD]),
        ]
        return ConfigureMake.extra_options(extra_vars)

    def configure_step(self):
        """
        Configure build outside of source directory.
        """
        try:
            objdir = os.path.join(self.builddir, 'obj')
            os.makedirs(objdir)
            os.chdir(objdir)
        except OSError, err:
            self.log.error("Failed to prepare for configuration of PSI build: %s" % err)

        if self.toolchain.options['usempi']:
            # PSI doesn't require a Fortran compiler itself, but may require it to link to BLAS/LAPACK correctly
            # we should always specify the sequential Fortran compiler,
            # to avoid problems with -lmpi vs -lmpi_mt during linking
            fcompvar = 'F77_SEQ'
        else:
            fcompvar = 'F77'

        # update configure options
        # using multi-threaded BLAS/LAPACK is important for performance,
        # cfr. http://sirius.chem.vt.edu/psi4manual/latest/installfile.html#sec-install-iii
        opt_vars = [
            ('cc', 'CC'),
            ('cxx', 'CXX'),
            ('fc', fcompvar),
            ('libdirs', 'LDFLAGS'),
            ('blas', 'LIBBLAS_MT'),  
            ('lapack', 'LIBLAPACK_MT'),
        ]
        for (opt, var) in opt_vars:
            self.cfg.update('configopts', "--with-%s='%s'" % (opt, os.getenv(var)))

        # -DMPICH_IGNORE_CXX_SEEK dances around problem with order of stdio.h and mpi.h headers
        # both define SEEK_SET, this makes the one for MPI be ignored
        self.cfg.update('configopts', "--with-opt='%s -DMPICH_IGNORE_CXX_SEEK'" % os.getenv('CFLAGS'))

        # explicitely specify Python binary to use
        pythonroot = get_software_root('Python')
        if not pythonroot:
            self.log.error("Python module not loaded.")
        env.setvar('PYTHON', os.path.join(pythonroot, 'bin', 'python'))

        # specify location of Boost
        boostroot = get_software_root('Boost')
        if not boostroot:
            self.log.error("Boost module not loaded.")
        self.cfg.update('configopts', "--with-boost=%s" % boostroot)

        # enable support for plugins
        self.cfg.update('configopts', "--with-plugins")

        # In order to create new plugins with PSI, it needs to know the location of the source
        # and the obj dir after install. These env vars give that information to the configure script.
        self.psi_srcdir = os.path.basename(self.cfg['start_dir'].rstrip(os.sep))
        self.install_psi_objdir = os.path.join(self.installdir, 'obj')
        self.install_psi_srcdir = os.path.join(self.installdir, self.psi_srcdir)
        env.setvar('PSI_OBJ_INSTALL_DIR', self.install_psi_objdir)
        env.setvar('PSI_SRC_INSTALL_DIR', self.install_psi_srcdir)

        super(EB_PSI, self).configure_step(cmd_prefix=self.cfg['start_dir'])

    def install_step(self):
        """Custom install procedure for PSI."""
        super(EB_PSI, self).install_step()

        # the obj and unpacked sources must remain available for working with plugins
        try:
            for subdir in ['obj', self.psi_srcdir]:
                shutil.copytree(os.path.join(self.builddir, subdir), os.path.join(self.installdir, subdir))
        except OSError, err:
            self.log.error("Failed to copy obj and unpacked sources to install dir: %s" % err)

    def sanity_check_step(self):
        """Custom sanity check for PSI."""
        custom_paths = {
            'files': ['bin/psi%s' % self.version.split('.')[0]],
            'dirs': ['include', 'share/psi'],
        }
        super(EB_PSI, self).sanity_check_step(custom_paths=custom_paths)

    def make_module_extra(self):
        """Custom variables for PSI module."""
        txt = super(EB_PSI, self).make_module_extra()
        txt += self.moduleGenerator.set_environment('PSI4DATADIR', '$root/share/psi')
        return txt
