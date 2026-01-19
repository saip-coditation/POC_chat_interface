# Deployment Guide: AI Data Platform Package

This guide explains how to install the package locally for development and how to publish it to PyPI for distribution.

## 1. Local Installation (For Development)
To use the package locally without publishing it (e.g., for testing in another project):

1. Navigate to the package directory:
   ```bash
   cd ai-data-platform-package
   ```

2. Install in "editable" mode:
   ```bash
   pip install -e .
   ```
   *This links the package to your python environment. Any changes you make to the code will be immediately reflected without needing to reinstall.*

## 2. Building for Distribution
To create the distribution files (`.tar.gz` and `.whl`) for sharing or uploading:

1. Install build tools:
   ```bash
   pip install --upgrade build
   ```

2. Run the build command:
   ```bash
   python -m build
   ```
   *This creates a `dist/` folder containing your package files.*

## 3. Uploading to PyPI (Public)
To make the package installable by anyone (`pip install ai-data-platform`):

1. Install twine:
   ```bash
   pip install twine
   ```

2. Upload to PyPI:
   ```bash
   twine upload dist/*
   ```
   *You will be prompted for your PyPI username and password (or API token).*

## 4. Installing from PyPI
Once uploaded, anyone can install it via:

```bash
pip install ai-data-platform
```
