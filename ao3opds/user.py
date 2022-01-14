""" Manages user authentication with AO3. """

import os
import warnings
import re
from typing import Callable
import urllib
import urllib.error
import warnings
import AO3

SLEEP_TIME = 300  # Wait 300 seconds if AO3 tells us to slow down
MAX_SLEEPS = 3 # Wait up to 3 times for a work.

def get_marked_for_later(session: AO3.Session, load=True, verbose=False):
    """ Gets a list of works from the Marked For Later list of a user.
    
    Arguments:
        session (AO3.Session): A session for a user.
        load (bool): If `True`, each work's metadata is loaded.
            Otherwise, the works are returned without loading.
            Defaults to `True`.
        verbose (bool): If `True`, status messages are printed to stdout
            as this function executes. A good idea when using this
            function as part of a script. Defaults to `False`.

    Returns:
        list[AO3.Work]: A list of works from the Marked For Later list
        of the user associated with `session`.
    """
    works: list[AO3.Work] = session.get_marked_for_later()
    if verbose:
        print(
            str(len(works)) + " works found in " + session.username +
            "'s Marked for Later list")
    # If we aren't loading works, we're done!
    if not load:
        return works
    # If we are loading works, try loading each one:
    for work in works:
        if verbose:
            print("\nDownloading metadata for work #" + str(work.id))
        # Oddly, works returns by `get_marked_for_later` are not
        # initialized with the session they are generated from.
        # So set that here (otherwise restricted works won't load):
        work.set_session(session)
        # Works are not loaded by `get_marked_for_later` (i.e. no data
        # is fetched from AO3), so load them here:
        if work.loaded is False:
            response = load_work(work)
            # Skip to the next work if we couldn't load this one:
            if not response:
                warnings.warn("Could not load work " + str(work.id))
                continue
            if verbose:
                print('Loaded metadata for work #' + str(work.id) +
                    ', "' + work.title + '"')
    return works

def download_marked_for_later(
        session: AO3.Session, destination_dir: str=None, filetype: str="EPUB",
        verbose=False):
    """ Downloads works in a user's _Marked For Later_ list. """
    works = get_marked_for_later(session, load=True, verbose=verbose)
    for work in works:
        if not work.loaded:
            # Skip works that we couldn't load:
            if verbose:
                print("\nWork #" + str(work.id) + " is not loaded. Skipping.")
            continue
        if verbose:
            print("\nPreparing to download work #" + str(work.id))
        # Find a name/path for the file:
        filename = get_filename(work, filetype, destination_dir=destination_dir)
        # Attempt to download the work:
        response = download_work(work, filename, filetype=filetype)
        if not response:
            warnings.warn('Could not download work "' + work.title + '"')
            continue
        if verbose:
            print('Download successful. File written to ' + filename)

def request(
        req:Callable, *args, _sleep_time:int=SLEEP_TIME, _num_sleeps:int=0,
        **kwargs):
    """ Attempts to perform `req`; sleeps if AO3 asks us to slow down. """
    try:
        req(*args, **kwargs)
    except urllib.error.HTTPError as error:
        if error.code == 429 and _num_sleeps < MAX_SLEEPS:  # too many requests
            return request(req, *args, _sleep_time, _num_sleeps + 1, **kwargs)
        return False # Failure response
    return True # Success response

def load_work(work:AO3.Work, load_chapters=False):
    """ Attempt to load `work`'s metadata. """
    return request(work.reload, load_chapters=load_chapters)

def download_work(work:AO3.Work, filename:str, filetype:str="EPUB"):
    """ Attempt to download `work` """
    return request(work.download_to_file, filename, filetype=filetype)

def get_filename(
        work: AO3.Work, filetype: str="EPUB", destination_dir:str= None):
    """ Gets a filename for a work. """
    # By default, try to preserve the filename used by AO3:
    filename = _get_filename_from_metadata(work, filetype)
    # If that doesn't work, turn the title into a filename:
    if filename is None:
        filename = _get_valid_filename(work.title) + '.' + filetype.lower()
    # If `destination_dir` is provided, place filename inside it:
    if destination_dir is not None:
        # Deal with '~', if present:
        destination_dir = os.path.expanduser(destination_dir)
        filename = os.path.abspath(os.path.join(destination_dir, filename))
    return filename

def _get_filename_from_metadata(work: AO3.Work, filetype: str="EPUB"):
    """ Gets the name of a file from the metadata for `work`. """
    # This code mirrors the logic in `AO3.Work.download()`, including
    # a call to the private attribute `_soup`:
    download_button = work._soup.find("li", {"class": "download"})
    for download_type in download_button.findAll("li"):
        if download_type.a.getText() == filetype.upper():
            url = f"https://archiveofourown.org/{download_type.a.attrs['href']}"
            return _get_filename_from_URL(url)
    return None

def _get_filename_from_URL(url):
    """ Gets the name of a file as represented in `url` """
    # The URL has 6 components; we only want the path:
    path = urllib.parse.urlparse(url).path
    # The path is hierarchical; split it up into each segment
    # (e.g. '/path/to/file' -> '', 'path', 'to', 'file'):
    path_segments = path.split('/')
    # Get the last non-empty segment; that's the (url-encoded) filename:
    filename_encoded = [
        segment for segment in path_segments if segment != ""][-1]
    # Decode the filename:
    filename = urllib.parse.unquote(filename_encoded)
    return filename

def _get_valid_filename(name: str):
    """ Converts a name into a valid filename. """
    name = name.strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', name)
