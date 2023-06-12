
from setuptools import setup

setup(
    name='make_tree',
    version='1.0.0',
    packages=['make_tree'],
    entry_points={
        'console_scripts': [
            'make_tree = make_tree.make_tree:main'
        ]
    },
    test_suite='tests',
    install_requires=[
        'ete3==3.1.3',
        'numpy==1.24.3',
        'six==1.16.0',
    ],
    extras_require={
        'testing': ['pytest'],
    },
)
