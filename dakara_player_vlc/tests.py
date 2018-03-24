from unittest import TestSuite, TextTestRunner, defaultTestLoader
from glob import glob
import os


DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class DakaraTestRunner:
    """Manage the running of tests

    Arguments:
        target (str): if provided, the corresponding test will be run,
            otherwise all test cases will be run.
    """
    def __init__(self, target=None):
        # create test suite
        self.test_suite = TestSuite()

        # add tests
        # if a test was provided, use it
        if target is not None:
            targets = [target]

        # otherwise, scan folder for tests
        else:
            targets = [os.path.splitext(os.path.basename(f))[0]
                       for f in glob(os.path.join(DIRECTORY, "tests_*.py"))]

        # tests are loaded by name inside the dakara_player_vlc module, so we
        # add this name to the targets

        for target in targets:
            target_name = 'dakara_player_vlc.' + target
            self.test_suite.addTests(
                    defaultTestLoader.loadTestsFromName(target_name)
                    )

    def run(self):
        """Run the collected test(s)
        """
        runner = TextTestRunner()
        results = runner.run(self.test_suite)

        return results.wasSuccessful()