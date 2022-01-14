""" Provides an `AO3.Work` for testing. """

import warnings
import AO3
import pickle

PICKLE_FILE = 'work_pickle'
TEST_WORK_ID = 18117086

# To limit network use during tests, try to load the Work via pickle:
try:
    with open(PICKLE_FILE, 'rb') as file:
        TEST_WORK = pickle.load(file)
except:
    # Loads all metadata and full-text content via network requests:
    TEST_WORK = AO3.Work(TEST_WORK_ID)
    # Attempt to write this to file to accelerate future tests:
    try:
        with open(PICKLE_FILE, 'wb'):
            pickle.dump(TEST_WORK, file, pickle.HIGHEST_PROTOCOL)
    except:
        warnings.warn(
            "Could not write test work to disk. " +
            "Repeated tests may result in rate-limiting.")
