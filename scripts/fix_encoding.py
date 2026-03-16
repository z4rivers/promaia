"""
One-shot script to add encoding='utf-8' to all open() calls missing it.
Skips binary modes ('rb', 'wb'), Image.open(), os.popen(), webbrowser.open(), etc.
"""
import os
import re
import glob

SKIP_PATTERNS = [
    'Image.open',
    'os.popen',
    'webbrowser.open',
    'asyncio.open',
    'open_new',
    'urlopen',
    'subprocess',
    '__pycache__',
]

# Matches: open(anything) or open(anything, 'r') or open(anything, 'w')
# but NOT already having encoding= and NOT binary mode
OPEN_WITH_MODE = re.compile(
    r"""(open\([^)]+,\s*['"]([rwa])['"]\s*)\)""",
)
OPEN_NO_MODE = re.compile(
    r"""(open\([^)]*[^,]\))\s*(as\s)""",
)

def should_skip_line(line):
    stripped = line.strip()
    if 'encoding' in line:
        return True
    if "'rb'" in line or "'wb'" in line or '"rb"' in line or '"wb"' in line:
        return True
    for pattern in SKIP_PATTERNS:
        if pattern in line:
            return True
    return False

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    changed = False
    new_lines = []

    for line in lines:
        if should_skip_line(line) or 'open(' not in line:
            new_lines.append(line)
            continue

        original_line = line

        # Case 1: open(path, 'r') -> open(path, 'r', encoding='utf-8')
        # Case 2: open(path, 'w') -> open(path, 'w', encoding='utf-8')
        # Case 3: open(path) as f -> open(path, encoding='utf-8') as f

        # Handle mode specified: open(xxx, 'r') -> open(xxx, 'r', encoding='utf-8')
        if re.search(r"""open\([^)]+,\s*['"][rwa]['"]""", line):
            line = re.sub(
                r"""(open\([^)]+,\s*['"][rwa]['"]\s*)\)""",
                r"""\1, encoding='utf-8')""",
                line
            )
        # Handle no mode: open(xxx) -> open(xxx, encoding='utf-8')
        elif re.search(r"""open\([^)]+\)\s*as""", line):
            line = re.sub(
                r"""(open\([^)]+)\)\s*(as)""",
                r"""\1, encoding='utf-8') \2""",
                line
            )
        elif re.search(r"""open\([^)]+\)""", line) and 'as' not in line:
            # open() used in other contexts, skip to be safe
            pass

        if line != original_line:
            changed = True
        new_lines.append(line)

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    return False

def main():
    py_files = glob.glob('promaia/**/*.py', recursive=True)
    fixed_files = []

    for filepath in sorted(py_files):
        if fix_file(filepath):
            fixed_files.append(filepath)
            print(f"  FIXED: {filepath}")

    print(f"\nDone. Fixed {len(fixed_files)} files out of {len(py_files)} scanned.")

if __name__ == '__main__':
    main()
