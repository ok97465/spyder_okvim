#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""Setup script for spyder-okvim."""
# %% Import
# Third party imports
from setuptools import find_packages, setup

# Local imports
from spyder_okvim import __version__
from spyder_okvim.spyder.config import CONF_SECTION

setup(
    name=CONF_SECTION,
    version=__version__,
    author="ok97465",
    author_email="ok97465@kakao.com",
    description="A plugin to enable vim keybindings to the spyder editor",
    license="MIT license",
    url="https://github.com/ok97465/spyder_okvim",
    install_requires=[
		# "python>=3.9",
		# "spyder>6"
    ],
    packages=find_packages(),
    entry_points={
        "spyder.plugins": ["spyder_okvim = spyder_okvim.spyder.plugin:OkVim"],
    },
    classifiers=[
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Education",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering",
    ],
)
