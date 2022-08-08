import unittest
import os
from subprocess import run, PIPE, STDOUT
from ..reader import read_ase
from dotenv import load_dotenv


def run_blender_script(script_path: str, args=list()):
    return run([os.environ['BLENDER_PATH'], '--background', '--python', script_path, '--'] + args)


class AseExportTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        load_dotenv()

    def test_flat(self):
        run_blender_script('src\\tests\\scripts\\export_flat_test.py')
        read_ase('./flat.ase')

    def test_smooth(self):
        pass


if __name__ == '__main__':
    print()
    unittest.main()
