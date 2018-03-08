from unittest import TestSuite, TextTestRunner, defaultTestLoader
from glob import glob
import os
import sys


class DakaraTestRunner:
    """Manage the running of tests

    Arguments:
        target (str): if provided, the corresponding test will be run,
            otherwise all test cases will be run.
    """
    def __init__(self, target=None):
        # create test suite
        self.test_suite = TestSuite()

        # move to project folder
        # TODO maybe use a cleaner way
        directory = os.path.dirname(os.path.abspath(__file__))
        os.chdir(directory)
        sys.path.append(directory)

        # add tests
        # if a test was provided, load it
        if target is not None:
            self.test_suite.addTest(
                    defaultTestLoader.loadTestsFromName(target)
                    )

        # otherwise, scan folder for tests
        else:
            targets = glob("tests_*.py")
            for target in targets:
                target_name, _ = os.path.splitext(target)
                self.test_suite.addTest(
                        defaultTestLoader.loadTestsFromName(target_name)
                        )

    def run(self):
        """Run the collected test(s)
        """
        runner = TextTestRunner()
        runner.run(self.test_suite)


if __name__ == '__main__':
    dakara_test_runner = DakaraTestRunner()
    dakara_test_runner.run()
