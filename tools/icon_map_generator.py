#!/usr/bin/env python3
import re
import os
import sys
from configparser import ConfigParser
from argparse import ArgumentParser

CSS_ICON_NAME_PARSER = r"""\.fa-([^:]*?):(?=[^}]*?content:\s*['"](.*?)['"])"""

def generate(css_file, ini_file):
    # check css_file exists
    if not os.path.isfile(css_file):
        raise IOError("File '{}' not found".format(
            css_file
            ))

    # load css file
    with open(css_file, 'r') as file:
        css_content = file.read()

    # create ini file structure
    ini_content = ConfigParser()

    # parse css file
    css_matcher = re.findall(
            CSS_ICON_NAME_PARSER,
            css_content,
            re.S,
            )

    # feed ini file
    ini_dict = {}
    for name, code in css_matcher:
        if code.startswith('\\'):
            code_hex = '0x' + code[1:]

        else:
            import ipdb
            ipdb.set_trace()
            code_hex = hex(ord(code))

        ini_dict[name] = code_hex

    ini_content['map'] = ini_dict

    # write ini file
    with open(ini_file, 'w') as file:
        ini_content.write(file)


def get_arg_parser():
    parser = ArgumentParser()

    parser.add_argument(
            'css_file',
            help="File with CSS rules mapping icons name and character."
            )

    parser.add_argument(
            'ini_file',
            help="Output file with hexadecimal code for icons."
            )

    return parser

if __name__ == '__main__':
    parser = get_arg_parser()

    args = parser.parse_args()

    generate(
            args.css_file,
            args.ini_file
            )

    sys.stdout.write("INI file saved in '{}'\n".format(args.ini_file))

