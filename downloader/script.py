""" A script for downloading EPUB files from AO3 based on a list of titles """

from download import get_titles, get_download_url, download_EPUB

# The local text file to pull filenames from:
FILENAME = "downloader/downloads.txt"

# Function for pulling filenames from a local text file:
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

# Here's the script! 
titles = get_titles(FILENAME)
for title in titles:
    print("\nSearching for '" + title + "'")
    download_url = get_download_url(title)
    if download_url is None:
        print("Could not find download URL. Skipping.")
        continue
    print("Found URL: ", download_url)
    download_EPUB(download_url, require_filename=title, verbose=True)
