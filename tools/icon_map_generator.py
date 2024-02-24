#!/usr/bin/env python3
import json
import os
import re
from argparse import ArgumentParser
from string import Template

CSS_ICON_NAME_PARSER = Template(
    r"""\.$prefix-([^:]*?):(?=[^}]*?content:\s*['"](.*?)['"])"""
)


def generate(css_file, json_file, prefix):
    """Generate a file that contains code for character names"""
    # check css_file exists
    if not os.path.isfile(css_file):
        raise FileNotFoundError("File '{}' not found".format(css_file))

    # load css file
    with open(css_file, "r") as file:
        css_content = file.read()

    # parse css file
    css_matcher = re.findall(
        CSS_ICON_NAME_PARSER.substitute(prefix=prefix), css_content, re.S
    )

    # convert icons
    icon_dict = {}
    for name, code in css_matcher:
        if code.startswith("\\"):
            code_hex = "0x" + code[1:]

        else:
            code_hex = hex(ord(code))

        icon_dict[name] = code_hex

    # write json file
    with open(json_file, "w") as file:
        file.write(json.dumps(icon_dict))


def get_arg_parser():
    """Create the parser"""
    parser = ArgumentParser(
        description="Generate icon name-hexadecimal code map from a CSS font file"
    )

    parser.add_argument(
        "css_file", help="file with CSS rules mapping icons name and character"
    )

    parser.add_argument("json_file", help="output file with hexadecimal code for icons")

    parser.add_argument("prefix", help="prefix of the CSS rules")

    return parser


if __name__ == "__main__":
    parser = get_arg_parser()

    args = parser.parse_args()

    generate(args.css_file, args.json_file, args.prefix)

    print("JSON file saved in '{}'".format(args.json_file))
