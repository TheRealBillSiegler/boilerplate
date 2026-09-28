"""This script processes an SVG file to add theme-aware CSS classes for colors."""

import argparse
import re
from pathlib import Path
from re import Match


def insert_css(svg_text: str) -> str:
    """Insert a CSS style block into the SVG content.

    The style block ensures that elements with class "logo-blue" remain blue,
    and elements with class "logo-black" change their stroke color based on the theme.

    Args:
        svg_text: The original SVG content as a string.

    Returns:
        The SVG content with the inserted CSS style block.
    """
    style_block = (
        "\n  <style>\n"
        "    .logo-blue { fill: #40B4E5; stroke: #40B4E5; }\n"
        "    @media (prefers-color-scheme: dark) {\n"
        "      .logo-black { stroke: white; }\n"
        "    }\n"
        "    @media (prefers-color-scheme: light) {\n"
        "      .logo-black { stroke: black; }\n"
        "    }\n"
        "  </style>\n"
    )
    # Insert style block after the opening <svg ...> tag.
    return re.sub(r"(<svg[^>]*>)", r"\1" + style_block, svg_text, count=1)


def replace_blue(_: Match[str]) -> str:
    """Replace fill or stroke attributes with blue color with a class attribute.

    Args:
        match: A regex match object representing the color attribute.

    Returns:
        A string with the class attribute for blue elements.
    """
    return ' class="logo-blue"'


def replace_black(_: Match[str]) -> str:
    """Replace stroke attribute with black color with a class attribute.

    Args:
        match: A regex match object representing the black stroke attribute.

    Returns:
        A string with the class attribute for black elements.
    """
    return ' class="logo-black"'


def process_svg(svg_content: str) -> str:
    """Process the SVG content to add theme-aware CSS classes.

    This function inserts a CSS style block into the SVG and replaces any
    occurrences of fill="#40B4E5" or stroke="#40B4E5" with class="logo-blue",
    and stroke="black" with class="logo-black".

    Args:
        svg_content: The original SVG content as a string.

    Returns:
        The modified SVG content.
    """
    svg_content = insert_css(svg_content)
    # Replace any fill or stroke attribute that equals "#40B4E5" with class="logo-blue"
    svg_content = re.sub(r'\s(?:fill|stroke)="(#40B4E5)"', replace_blue, svg_content)
    # Replace any stroke attribute that equals "black" with class="logo-black"
    svg_content = re.sub(r'\sstroke="black"', replace_black, svg_content)
    return svg_content  # noqa: RET504


def main() -> None:
    """Process the SVG file and save the modified version.

    The input path is passed as an argument (defaulting to
    docs/assets/boilerplate-cli-logo.svg). The output file is saved in
    the same directory with '_modified' appended to the file stem.
    """
    parser = argparse.ArgumentParser(
        description="Process an SVG file to add theme-aware CSS classes."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default="docs/assets/boilerplate-cli-logo.svg",
        help="Path to the input SVG file (default: docs/assets/boilerplate-cli-logo.svg)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Optional path for the output file. Defaults to the input directory with '_modified' appended.",
    )

    args = parser.parse_args()
    input_file = Path(args.input_path).resolve()
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = input_file.parent / (input_file.stem + "_modified.svg")

    # Read the SVG content.
    svg_text = input_file.read_text(encoding="utf-8")

    # Process the SVG content.
    modified_svg = process_svg(svg_text)

    # Write the modified SVG content to the output file.
    output_file.write_text(modified_svg, encoding="utf-8")

    print(f"SVG has been updated and saved as {output_file}")


if __name__ == "__main__":
    main()
