""" A package for downloading works from AO3 based on their filenames.

The motivation for this package is that sometimes downloads can fail,
and once the tab is closed the only record of what was (attempted to be)
downloaded is the filename of the empty download file. Sometimes this
happens to hundreds of files someone's wife tried to download over the
course of several days. Just as an example.

The package is designed to run as a script, simply by executing
`main.py`. But most of the heavy lifting is done by the functions of
`download.py`, which are intended to be reusable.
"""

__all__ = ['script', 'download', 'user']

__version__ = '0.0.1'
__author__ = 'Christopher Scott'
__copyright__ = 'Copyright (C) 2022 Christopher Scott'
__license__ = 'All rights reserved'
