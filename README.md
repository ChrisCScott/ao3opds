# AO3OPDS
A tool for generating OPDS feeds of works from Archive of Our Own.

## Use
Using the script is as easy as entering the filenames of EPUB files in
`downloads.txt` (one filename per line - capitalization matters!) and
running `script.py` (i.e. `$ python3 script.py`). No setup is required
other than having `python3` installed and correctly identifying the file
(this package does not add its path to any environment variables.)

## Background
This tool is a script to re-attempt manual EPUB downloads from AO3
that had failed for some reason in somewhat large numbers (~300 files
over several weeks). The only record of each work was the (empty)
download file, so I wrote this script to look up a work with the same
name as the file and try to download it.

This leaves a lot to be desired. The main drawback is that very few
works are uniquely named, so the wrong work is often downloaded.
There are some ways to limit the frequency with which this happens
(checking for identical filenames, being strict about capitalization,
etc.), but there just isn't a reliable way to identify a work from a
truncated filename alone - you need metadata.

One solution would be to synchronize with a user's "Marked for Later"
list on AO3 itself and download newly-added works from that list
automatically. The list provides all the metadata required to correctly
identify a work. (Publishing the relevant metadata to an OPDS catalogue
might be a convenient alternative to downloading.)
