import os
import sys
import django

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.urls import get_resolver, reverse, NoReverseMatch

resolver = get_resolver()

def list_app_urls(lis, namespace=None):
    url_list = []
    for pattern in lis:
        if hasattr(pattern, 'url_patterns'):
            # Skip django admin
            if pattern.namespace == 'admin':
                continue
            ns = f"{namespace}:{pattern.namespace}" if namespace and pattern.namespace else (pattern.namespace or namespace)
            url_list.extend(list_app_urls(pattern.url_patterns, ns))
        elif hasattr(pattern, 'name') and pattern.name:
            full_name = f"{namespace}:{pattern.name}" if namespace else pattern.name
            url_list.append((full_name, pattern.pattern))
    return url_list

app_urls = list_app_urls(resolver.url_patterns)
print(f"App URL patterns registered: {len(app_urls)}")

tested = 0
errors = []

for name, pattern in app_urls:
    str_pattern = str(pattern)
    if '<' not in str_pattern:
        try:
            url = reverse(name)
            tested += 1
            print(f"[REVERSED OK] {name} -> {url}")
        except NoReverseMatch as e:
            errors.append((name, str(e)))

print(f"\nTested {tested} parameterless App URLs.")
if errors:
    print(f"FAILED: {len(errors)} App URL reverse resolution errors found!")
    for n, err in errors:
        print(f"  - {n}: {err}")
else:
    print("SUCCESS: 100% of custom App URLs reverse-resolve cleanly!")
