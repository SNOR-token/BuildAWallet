"""Package only extension source files, without developer files or secrets."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
output = root.parent / "static" / "blueprint-extension.zip"
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for name in ("manifest.json", "popup.html", "popup.css", "popup.js"):
        archive.write(root / name, name)
print(output)
