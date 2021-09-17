#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup

setup(
    name='un-t-ann-gle',
    version='0.1',
    description='un-t-ann-gle splits a formatted file into text + annotations',
    author='Hennie Brugman',
    author_email='hennie.brugman@di.huc.knaw.nl',
    url='https://github.com/knaw-huc/un-t-ann-gle',
    packages=find_packages(exclude=["tests", "*.tests", "*.tests.*", "tests.*"]),
    package_dir={'un-t-ann-gle': 'untanngle'},
    include_package_data=True,
    install_requires=[],
    license='LICENSE'
)
