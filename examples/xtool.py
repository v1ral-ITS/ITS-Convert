#!/usr/bin/env python3
"""
XTool - A multi-purpose tool example for ITS-Convert
This demonstrates a script that can be built into an AppImage
"""

import argparse
import sys
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="XTool - Multi-purpose utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  xtool info          Show system information
  xtool greet John     Greet someone
  xtool calc 5 + 3     Simple calculator
  xtool --version     Show version
        """
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        help="Command to execute: info, greet, calc"
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments for the command"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    if args.version:
        print("XTool v1.0.0")
        print("Built with ITS-Convert")
        return 0

    if args.verbose:
        print(f"[DEBUG] Running command: {args.command}")
        print(f"[DEBUG] Arguments: {args.args}")

    if args.command == "info":
        return cmd_info()
    elif args.command == "greet":
        return cmd_greet(args.args)
    elif args.command == "calc":
        return cmd_calc(args.args)
    elif args.command == "help" or args.command is None:
        parser.print_help()
        return 0
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        return 1

def cmd_info():
    """Show system information"""
    import platform
    import socket

    print("=" * 50)
    print("System Information")
    print("=" * 50)
    print(f"Hostname: {socket.gethostname()}")
    print(f"Platform: {platform.platform()}")
    print(f"Python: {platform.python_version()}")
    print(f"Processor: {platform.processor()}")
    print(f"Architecture: {platform.machine()}")
    print(f"Current directory: {os.getcwd()}")
    print(f"User: {os.getenv('USER', os.getenv('USERNAME', 'unknown'))}")
    print("=" * 50)
    return 0

def cmd_greet(name_parts):
    """Greet someone"""
    if not name_parts:
        print("Usage: xtool greet <name>")
        return 1

    name = " ".join(name_parts)
    greetings = [
        f"Hello, {name}!",
        f"Hi there, {name}!",
        f"Greetings, {name}!",
        f"Welcome, {name}!",
        f"Hey {name}, how are you?",
    ]

    import random
    print(random.choice(greetings))
    return 0

def cmd_calc(expr_parts):
    """Simple calculator"""
    if not expr_parts:
        print("Usage: xtool calc <expression>")
        print("Example: xtool calc 5 + 3")
        return 1

    expression = " ".join(expr_parts)

    try:
        result = eval(expression)
        print(f"Result: {result}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
