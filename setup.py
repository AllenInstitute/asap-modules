#!/usr/bin/env python
import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ""

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import shlex
        import pytest
        self.pytest_args += " --cov=renderapps --cov-report html "\
                            "--junitxml=/tmp/test-reports/test.xml"

        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


with open('tests/test_requirements.txt', 'r') as f:
    test_required = f.read().splitlines()

with open('requirements.txt', 'r') as f:
    required = f.read().splitlines()

setup(name='render-modules',
      version='0.0.1',
      description='A set of python modules for doing higher level processing steps used '
                  ' render, developed for processing array tomography and EM images.'
                  'see http://github.com/saalfeldlab/render',
      author='Sharmishtaa Seshamani, Forrest Collman, Russel Torres, Gayathri Mahalingam, Sam Kinn',
      author_email='forrestc@alleninstitute.org',
      url='https://github.com/AllenInstitute/render-modules/',
      packages=find_packages(),
      install_requires=required,
      setup_requires=['flake8'],
      tests_require=test_required,
      cmdclass={'test': PyTest})
