# AO3OPDS
A tool for generating OPDS feeds of works from Archive of Our Own.

## Use
This package is in development. Currently it provides classes for
fetching metadata from AO3 and converting that to OPDS acquisition
feeds. Supporting serving those feeds to client devices (e.g. via
installation as a CGI script on a webserver) is planned future
functionality.

This package also includes a legacy script for downloading AO3 works
as EPUBs directly to one's local device, found at `script.py`. This
script is probably not what you want! (See *Background*, below, for
why.) Using the script is as easy as entering the filenames of EPUB
files in `downloads.txt` (one filename per line - capitalization
matters!) and running `script.py` (i.e. `$ python3 script.py`). No setup
is required other than having `python3` installed and correctly
identifying the file (this package does not add its path to any
environment variables.)

## Background
This tool started as a script to re-attempt manual EPUB downloads from
AO3 that had failed for some reason in somewhat large numbers (~300
files over several weeks). The only record of each work was the (empty)
download file, so I wrote this script to look up a work with the same
name as the file and try to download it.

This leaves a lot to be desired. The main drawback is that very few
works are uniquely named, so the wrong work is often downloaded.
There are some ways to limit the frequency with which this happens
(checking for identical filenames, being strict about capitalization,
etc.), but there just isn't a reliable way to identify a work from a
truncated filename alone - you need metadata.

This package has grown from there into a tool that lets a user generate
an OPDS feed from their Marked for Later list (or any other list of AO3
works), which they can then import via their ebook reader (e.g.
MapleRead). This way you always get the files you want, where you want
them.
