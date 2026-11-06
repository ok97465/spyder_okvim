# Recording the demos

The README GIFs are captured from the current Spyder editor and Okvim widgets,
with real key input and short captions. The recording host supplies an editor
and status bar; it does not launch the full Spyder desktop.
It uses Spyder's application startup and main-window stylesheet to load the
actual theme, resources, fonts, and palette. Only the caption labels have custom
font sizing. The Spyder version is printed and included in each recording.
The substitution demo hides the optional command guide to keep replacements visible.

Install the project's development dependencies and Pillow, then run from the
repository root:

```bash
python scripts/record_demos.py
```

To refresh selected demos or inspect screenshots before replacing the assets:

```bash
python scripts/record_demos.py --only picker substitute --output /tmp/okvim-demos --frames /tmp/okvim-frames
```

The recorder uses temporary Spyder preferences and sample project files. Its
sample Git repository is temporary too. It leaves your settings and repositories
untouched. Each GIF loops at 1000 × 610 pixels; `--frames` also saves PNGs of the
jump labels, replacement preview, and file/Git picker for visual review.
