import os
import py_compile
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

errors: list[tuple[str, str]] = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    if f"{os.sep}.venv{os.sep}" in dirpath:
        continue
    for filename in filenames:
        if not filename.endswith('.py'):
            continue
        path = os.path.join(dirpath, filename)
        try:
            py_compile.compile(path, doraise=True)
        except Exception as e:
            errors.append((path, str(e)))

print('py_compile_ok:', len(errors) == 0)
print('error_count:', len(errors))
for path, err in errors[:20]:
    print('ERROR:', path)
    print(' ', err)

sys.exit(1 if errors else 0)
