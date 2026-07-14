import os
import difflib

repo_dir = r"c:\Dev\HA\centsys_remote\custom_components\centsys_remote"
h_dir = r"h:\custom_components\centsys_remote"

diff_lines = []

for root, dirs, files in os.walk(h_dir):
    if '__pycache__' in dirs:
        dirs.remove('__pycache__')
    if 'translations' in dirs:
        dirs.remove('translations')
        
    for file in files:
        if file.endswith('.pyc'): continue
        h_path = os.path.join(root, file)
        rel_path = os.path.relpath(h_path, h_dir)
        repo_path = os.path.join(repo_dir, rel_path)
        
        with open(h_path, 'r', encoding='utf-8', errors='replace') as f:
            h_lines = f.readlines()
            
        if os.path.exists(repo_path):
            with open(repo_path, 'r', encoding='utf-8', errors='replace') as f:
                repo_lines = f.readlines()
        else:
            repo_lines = []
            
        diff = list(difflib.unified_diff(repo_lines, h_lines, fromfile=f"repo/{rel_path}", tofile=f"h:/{rel_path}"))
        if diff:
            diff_lines.extend(diff)
            diff_lines.append('\n')

with open(r"c:\Dev\HA\centsys_remote\repo_vs_h_diff.patch", "w", encoding="utf-8") as f:
    f.writelines(diff_lines)
