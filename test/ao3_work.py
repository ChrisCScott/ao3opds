""" Provides an `AO3.Work` for testing. """

import sys
import warnings
import AO3
import pickle

PICKLE_FILE = 'test/work_pickle'
TEST_WORK_ID = 2080878  # A work called "I am Groot"
# Read it here: https://archiveofourown.org/works/2080878

# To limit network use during tests, try to load the Work via pickle:
try:
    with open(PICKLE_FILE, 'rb') as file:
        TEST_WORK = pickle.load(file)
    if TEST_WORK.id != TEST_WORK_ID:
        raise BaseException('Wrong work loaded, go to except block')
except:
    # Loads all metadata and full-text content via network requests:
    TEST_WORK = AO3.Work(TEST_WORK_ID)
    # Attempt to write this to file to accelerate future tests:
    try:
        # Increase recursion limit to account for high level of
        # recursion in BeautifulSoup objects. See:
        # https://docs.python.org/3/library/pickle.html#what-can-be-pickled-and-unpickled
        # https://stackoverflow.com/a/52975220
        limit = sys.getrecursionlimit()
        sys.setrecursionlimit(10000)
        with open(PICKLE_FILE, 'wb') as file:
            pickle.dump(TEST_WORK, file, pickle.HIGHEST_PROTOCOL)
    except:
        warnings.warn(
            "Could not write test work to disk. " +
            "Repeated tests may result in rate-limiting.")
    finally:
        sys.setrecursionlimit(limit)
