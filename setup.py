
from setuptools import setup

setup(
    name='make_tree',
    packages=['make_tree'],
    entry_points={
        'console_scripts': [
            'make_tree = make_tree.make_tree:main'
        ]
    },
    install_requires=[
        'ete3==3.1.3',
        'numpy==1.24.3',
        'six==1.16.0',
    ],
    description='Simple script for drawing phylogenetic trees',
    version='1.0.0',
    author='cfe-lab',
    author_email='vmysak@bccfe.ca',
    license='GPL-3.0',
    url='https://github.com/cfe-lab/make_tree',
    test_suite='tests',
    extras_require={
        'testing': ['pytest'],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Operating System :: OS Independent',
    ],
)
