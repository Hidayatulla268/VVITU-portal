import os
import sys
import django

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.template.loader import get_template
from django.template import TemplateSyntaxError

templates_dir = os.path.abspath(os.path.dirname(__file__) + '/../templates')
errors = []

for root, dirs, files in os.walk(templates_dir):
    for f in files:
        if f.endswith('.html'):
            rel_path = os.path.relpath(os.path.join(root, f), templates_dir).replace('\\', '/')
            try:
                get_template(rel_path)
                print(f"[OK] {rel_path}")
            except TemplateSyntaxError as e:
                print(f"[SYNTAX ERROR] {rel_path}: {e}")
                errors.append((rel_path, str(e)))
            except Exception as e:
                print(f"[ERROR] {rel_path}: {e}")
                errors.append((rel_path, str(e)))

print("\n=========================================")
if errors:
    print(f"FAILED: Found {len(errors)} template errors!")
    for t, err in errors:
        print(f"  - {t}: {err}")
else:
    print("SUCCESS: All templates compiled with 0 syntax errors!")
print("=========================================")
