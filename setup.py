""" A setuptools-based setup module. """

from os import path
from setuptools import setup, find_packages

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='ao3opds', # Required

    # Versions should comply with PEP 440:
    # https://www.python.org/dev/peps/pep-0440/
    #
    # For a discussion on single-sourcing the version across setup.py and the
    # project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.0.1a2',  # Required

    # A one-line description of what this project does.
    description='A tool for generating OPDS feeds of AO3 works',  # Optional

    # An optional longer description of the project. PyPI uses this for the
    # body of text it shows users. This is the same as the README.
    long_description=long_description,  # Optional

    # The README is in Markdown. Valid values are:
    # text/plain, text/x-rst, and text/markdown
    long_description_content_type='text/markdown',  # Optional

    # A valid link to the project's main homepage.
    # url='https://github.com/ChrisCScott/ao3downloader',  # Optional

    # My name.
    author='Christopher Scott',  # Optional

    # My email address.
    author_email='christopher@christopherscott.ca',  # Optional

    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: End Users/Desktop',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Multimedia'

        # Pick your license as you wish
        'License :: Other/Proprietary License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',

        'Natural Language :: English'
    ],

    # This field adds keywords for your project which will appear on the
    # project page. What does your project relate to?
    keywords='ao3 archive of our own epub',  # Optional

    # You can just specify package directories manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),  # Required

    # To include static files (e.g. Jinja templates), we can set this
    # flag to True and specify the files in MANIFEST.in:
    include_package_data=True,  # Optional

    # This field lists other packages that your project depends on to run.
    # Any package you put here will be installed by pip when your project is
    # installed, so they must be valid existing projects.
    #
    # For an analysis of "install_requires" vs pip's requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'ao3-api>=2',
        'Flask>=2',
        'Jinja2>=3',
    ],  # Optional

    # List additional groups of dependencies here (e.g. development
    # dependencies).
    extras_require={  # Optional
    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.
    # package_data={  # Optional
    #     'sample': ['package_data.dat'],
    # },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files
    # data_files=[('my_data', ['data/data_file'])],  # Optional

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # `pip` to create the appropriate form of executable for the target
    # platform.
    #
    # For example, the following would provide a command called `sample` which
    # executes the function `main` from this package when invoked:
    # entry_points={  # Optional
    #     'console_scripts': [
    #         'sample=sample:main',
    #     ],
    # },

    # List additional URLs that are relevant to your project as a dict.
    project_urls={  # Optional
        'Bug Reports': 'https://github.com/ChrisCScott/ao3opds/issues',
        'Say Thanks!': 'https://twitter.com/ChrisCScott',
        'Source': 'https://github.com/ChrisCScott/ao3opds/',
    },
)
