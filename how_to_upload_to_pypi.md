# How to Upload Your Python Project to PyPI (2025 Guide)

This document is a checklist for uploading your Python project to PyPI (Python Package Index).

## 1. Update the Version

- Update the `version` field in `pyproject.toml`.
- Also update the version in your main module’s `__init__.py` (for example, `spyder_okvim/__init__.py`) to keep them in sync.

## 2. Remove Previous Build Files

Delete the following folders/files if they exist:

```bash
rm -rf build/ dist/ spyder_okvim.egg-info/
```

## 3. Build the Package

Create the distribution files with:

```bash
python -m build
```
- This generates `.whl` and `.tar.gz` files in the `dist/` folder.

## 4. Upload to PyPI

Upload the built package using **twine**:

```bash
twine upload dist/*
```
- The first time, you will be asked for your PyPI username and password.

## 5. (Optional) Test Upload with TestPyPI

If you want to test your upload before publishing to the real PyPI:

```bash
twine upload --repository testpypi dist/*
```
- Recommended for first-time uploads.

## 6. Additional Notes

- If you don’t have a PyPI account, [register here](https://pypi.org/account/register/).
- To prevent issues with your README on PyPI, [follow this guide](https://packaging.python.org/en/latest/guides/making-a-pypi-friendly-readme/).
- If you don’t have `build` or `twine` installed:
  ```bash
  pip install build twine
  ```

---

### Quick Checklist

1. [ ] Update version (`pyproject.toml` & `__init__.py`)
2. [ ] Remove `build/ dist/ *.egg-info/`
3. [ ] Run `python -m build`
4. [ ] Run `twine upload dist/*`
5. [ ] Check your package on the PyPI website

---

### Common Errors

- **HTTPError: 400 Bad Request**  
  → This occurs if you upload a version that already exists. Always increase the version!
- **Broken README rendering**  
  → Check image links and Markdown syntax.

---

### Official Documentation

- [Official PyPI Packaging Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
