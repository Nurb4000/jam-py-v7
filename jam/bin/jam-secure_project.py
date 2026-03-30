#!/usr/bin/env python3
import os
import shutil

# --- Step 1: Ask user for new builder name ---
while True:
    new_name = input("Enter new builder HTML name (e.g., xybuilder.html): ").strip()
    if new_name:
        break
    print("ERROR: Name cannot be empty!")

if not new_name.endswith(".html"):
    new_name += ".html"

# --- Step 2: Ask for virtualenv path ---
while True:
    venv_path = input("Enter path to your Python virtualenv: ").strip()
    if os.path.exists(venv_path):
        break
    print("ERROR: Path does not exist!")

# --- Step 3: Determine site-packages dynamically ---
lib_path = os.path.join(venv_path, "lib")
python_dirs = [d for d in os.listdir(lib_path) if d.startswith("python")]
if not python_dirs:
    print("ERROR: Could not find pythonX.Y folder in lib/")
    exit(1)
site_packages_path = os.path.join(lib_path, python_dirs[0], "site-packages")
if not os.path.exists(site_packages_path):
    print("ERROR: site-packages folder not found.")
    exit(1)

# --- Step 4: Paths ---
builder_py = os.path.join(site_packages_path, "jam/admin/builder.py")
wsgi_py = os.path.join(site_packages_path, "jam/wsgi.py")
html_old = os.path.join(site_packages_path, "jam/html/builder.html")
html_new = os.path.join(site_packages_path, "jam/html", new_name)

# --- Step 5: Backup files ---
for file_path in [builder_py, wsgi_py, html_old]:
    if os.path.exists(file_path):
        backup_path = file_path + ".bak"
        if not os.path.exists(backup_path):
            shutil.copy(file_path, backup_path)
            print(f"Backup created: {backup_path}")
    else:
        print(f"WARNING: File not found, skipping backup: {file_path}")

# --- Step 6: Patch builder.py ---
if os.path.exists(builder_py):
    with open(builder_py, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("'builder.html'", f"'{new_name}'")
    with open(builder_py, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patched: {builder_py}")

# --- Step 7: Patch wsgi.py ---
if os.path.exists(wsgi_py):
    with open(wsgi_py, "r", encoding="utf-8") as f:
        content = f.read()
    # Replace /builder.html → /new_name
    content = content.replace("/builder.html", f"/{new_name}")
    # Replace 'builder.html' → 'new_name' (handles list and os.path.exists)
    content = content.replace("'builder.html'", f"'{new_name}'")
    with open(wsgi_py, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patched: {wsgi_py}")

# --- Step 8: Move HTML file ---
if os.path.exists(html_old):
    shutil.move(html_old, html_new)
    print(f"HTML file moved: {html_old} → {html_new}")
else:
    print(f"WARNING: HTML file not found: {html_old}")

print("\n✅ Done! Builder is now secured with new name:", new_name)
print("Backups of original files are kept with .bak extension.")
