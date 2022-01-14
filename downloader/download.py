""" Functions for fetching pages and scraping information from AO3. """

import os
import time
import urllib.request
import urllib.parse
import urllib.error
import re
import urllib

# Ref search string:
# https://archiveofourown.org/works/search?utf8=✓&commit=Search&work_search%5Bquery%5D=&work_search%5Btitle%5D=100000+Galleons&work_search%5Bcreators%5D=&work_search%5Brevised_at%5D=&work_search%5Bcomplete%5D=&work_search%5Bcrossover%5D=&work_search%5Bsingle_chapter%5D=0&work_search%5Bword_count%5D=&work_search%5Blanguage_id%5D=&work_search%5Bfandom_names%5D=&work_search%5Brating_ids%5D=&work_search%5Bcharacter_names%5D=&work_search%5Brelationship_names%5D=&work_search%5Bfreeform_names%5D=&work_search%5Bhits%5D=&work_search%5Bkudos_count%5D=&work_search%5Bcomments_count%5D=&work_search%5Bbookmarks_count%5D=&work_search%5Bsort_column%5D=_score&work_search%5Bsort_direction%5D=desc
# A string for searching for works by title:
SEARCH_URL = "https://archiveofourown.org/works/search?commit=Search&work_search%5Bquery%5D=&work_search%5Btitle%5D={title}&work_search%5Bcreators%5D=&work_search%5Brevised_at%5D=&work_search%5Bcomplete%5D=&work_search%5Bcrossover%5D=&work_search%5Bsingle_chapter%5D=0&work_search%5Bword_count%5D=&work_search%5Blanguage_id%5D=&work_search%5Bfandom_names%5D=&work_search%5Brating_ids%5D=&work_search%5Bcharacter_names%5D=&work_search%5Brelationship_names%5D=&work_search%5Bfreeform_names%5D=&work_search%5Bhits%5D=&work_search%5Bkudos_count%5D=&work_search%5Bcomments_count%5D=&work_search%5Bbookmarks_count%5D=&work_search%5Bsort_column%5D=_score&work_search%5Bsort_direction%5D=desc"
WORK_URL = "https://archiveofourown.org/works/{work}?view_adult=true&view_full_work=true"

WAIT_TIME = 300  # How long to wait if the server asks us to slow down
NUM_WAITS = 2 # The maximum number of times we'll wait before skipping a file

WORKNUM_RE = re.compile('<a href="/works/([0-9]+)">')
DOWNLOAD_RE = re.compile('<a href="(/downloads/[^"]+)">EPUB</a>')

FILENAME = "downloads.txt"

# -----------------------------------------------------
# DEFINE FUNCTIONS
# The script itself follows these function definitions.
# -----------------------------------------------------

def get_titles(filename):
    """ Returns a list of titles, each a line in `filename` """
    # Get list of work titles from a local file:
    titles = []
    with open(filename, 'r') as file:
        for title in file:
            # Remove leading/terminal whitespace
            title = title.strip()
            if title != "":
                titles.append(title)
    return titles

def get_page(url, decode=None, _waits=0, verbose=True, **kwargs):
    """ Returns the page located at `url`.

    `kwargs` are used to format the URL (via `str.format()`).
    """
    formatted_url = url.format(**kwargs)
    try:
        with urllib.request.urlopen(formatted_url) as response:
            page = response.read()
    except urllib.error.HTTPError as err:
        ## Too many requests:
        if err.code == 429 and _waits < NUM_WAITS:
            if verbose:
                print('\nBreak time! Pausing for', WAIT_TIME, 'seconds.')
            time.sleep(WAIT_TIME)
            return get_page(url, decode=decode, _waits=_waits+1, **kwargs)
        # If we can't handle it, return None:
        if verbose:
            print("Error when loading page:", err)
        return None
    if decode is not None:
        page = page.decode(decode)
    return page

def parse_page(page, pattern):
    """ Returns the first match for capture group 1 of `pattern` in `page` """
    match = pattern.search(page)
    if match is None:
        return None
    # Get the first capture group in the first matching substring:
    return match.group(1)

def find_on_page(url, pattern, **kwargs):
    """ Returns the first matching for group 1 in `pattern` in the page at `url` """
    page = get_page(url, decode='utf8', **kwargs)
    if page is None:
        return None
    match = parse_page(page, pattern)
    return match

def get_download_url(title):
    """ Returns a URL to an EPUB for `title` (or None, if unsuccessful). """
    # URL-encode the title so we can safely insert it into the search URL:
    # (Use a strict search on the first attempt by quoting the title)
    encoded_title = urllib.parse.quote_plus('"' + title + '"')

    # Get the worknum for the first search result:
    work_num = find_on_page(SEARCH_URL, WORKNUM_RE, title=encoded_title)
    # If that didn't work, try again without quoting the title:
    if work_num is None:
        encoded_title = urllib.parse.quote_plus(title)
        work_num = find_on_page(SEARCH_URL, WORKNUM_RE, title=encoded_title)
    if work_num is None:
        return None

    # Now find the page for the worknum and get the (relative) download url:
    download_url_relative = find_on_page(WORK_URL, DOWNLOAD_RE, work=work_num)
    if download_url_relative is None:
        return None

    # Turn that into an absolute URL based on the work's page:
    work_url = WORK_URL.format(work=work_num)
    download_url = urllib.parse.urljoin(work_url, download_url_relative)

    return download_url

def get_filename(url):
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

def matching_filenames(filename1, filename2):
    """ Returns True if filename1 and filename2 are roughly the same. """
    # First, strip any surrounding spaces:
    filename1, filename2 = filename1.strip(), filename2.strip()
    # Second, remove any extensions; we're just checking the title portion:
    filename1 = os.path.splitext(filename1)[0]
    filename2 = os.path.splitext(filename2)[0]
    return filename1 == filename2

def download_EPUB(
        source, destination="~/Downloads/",
        require_filename=None, verbose=True):
    """ Download from `source` URL to `destination` path.

    If `require_filename` is passed, `source` is only downloaded if the filename
    in `source` matches `require_filename`. This helps avoid
    """
    # Download the file at `source`:
    # (Don't pass `decode` arg; we need to write raw bytes, as EPUB is zipped)
    page = get_page(source, verbose=verbose)
    if page is None:
        if verbose:
            print('Failed to download EPUB.')
        return
    # Write to a file at `destination`:
    filename = get_filename(source)
    # Check to see if the filename is what we expected (and halt if not):
    if (
            require_filename is not None and
            not matching_filenames(filename, require_filename)):
        if verbose:
            print(
                'Filename "' + filename + '" does not match "' +
                require_filename + '".', 'Skipping download.')
        return
    destination = os.path.expanduser(destination)  # Deal with `~`, if present
    path = os.path.abspath(os.path.join(destination, filename))
    try:
        with open(path, 'wb') as file:  # Use 'wb' mode to write binary file
            file.write(page)
    except OSError as err:
        if verbose:
            print('Could not open file "', path)
            print('Full error:', err)
        return
    except IOError as err:
        if verbose:
            print('Could not write to file "', path)
            print('Full error:', err)
        # Don't leave an empty file on disk:
        os.remove(path)
        return
    except Exception as err:
        if verbose:
            print('Error raised:"', err)
        return
    if verbose:
        print('Download successful!', len(page), 'bytes written.')
