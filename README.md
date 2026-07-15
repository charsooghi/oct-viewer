# OCT Viewer

A free, standalone viewer for Heidelberg Engineering **HEYEX `.e2e`** export
files - for anyone who has an OCT/fundus scan file but no HEYEX license to
open it with.

> **Disclaimer:** This is a personal data-recovery/viewing tool, **not a
> certified medical device**. The `.e2e` format is proprietary and
> undocumented; this project relies on community reverse-engineering work
> (see [Credits](#credits)). Rendering may differ from Heidelberg's own
> HEYEX software, and some files or scan types may not be fully supported.
> Do not use this for clinical diagnosis or treatment decisions.

> **Trademark notice:** "HEYEX" and "Spectralis" are trademarks of Heidelberg
> Engineering GmbH. This project is an independent, community effort and is
> **not affiliated with, endorsed by, or sponsored by Heidelberg Engineering**.
> Those names are used here only to describe file-format compatibility.

## Features

- Open a `.e2e` file and browse every patient/series it contains
- View the fundus/IR localizer image alongside the B-scan stack
- Step through B-scans with a slider, spinbox, arrow keys, or mouse wheel
- Zoom (mouse wheel) and pan (drag) on both images
- Double-click either image to open a larger detail view
- Scan-position overlay: current B-scan line + full scan-area box on the
  fundus image
- Contrast/brightness adjustment
- Patient/series/B-scan metadata table (`View > Image Info`)
- Packaged as a standalone executable - no Python installation required to
  run it

## Download

Prebuilt Windows and macOS builds are available under
[Releases](../../releases) (or as [Actions build artifacts](../../actions)
for the latest commit).

**macOS note:** builds are not code-signed/notarized (that requires a paid
Apple Developer account). On first launch, **right-click the app > Open**,
then click **Open** in the dialog - double-clicking will refuse to open an
unsigned app the first time.

## Running from source

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m oct_viewer.main [optional/path/to/file.e2e]
```

(entry point lives at `src/oct_viewer/main.py`; run with `PYTHONPATH=src` set
to `src/` so `oct_viewer` is importable)

## Building a standalone executable

```bash
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed \
  --name "OCT Viewer" \
  --paths src \
  --collect-all oct_converter \
  --collect-all eyepy \
  --copy-metadata imageio \
  --hidden-import PySide6.QtSvg \
  src/run_app.py
```

The build appears under `dist/OCT Viewer/`. This must be run on the target
OS (PyInstaller does not cross-compile) - see `.github/workflows/build.yml`
for the CI setup that builds both Windows and macOS automatically.

## How it works

The `.e2e` format has no public specification. This project combines two
MIT-licensed, independently reverse-engineered readers:

- [`oct-converter`](https://github.com/marksgraham/OCT-Converter) for patient
  demographics
- [`eyepy`](https://github.com/MedVisBonn/eyepy) for per-series B-scan pixel
  data, the localizer image, and scan-position metadata

Parsing is best-effort throughout - if a piece of a file can't be decoded, it
is skipped with a warning rather than crashing the whole load.

## Credits

This project would not exist without the prior reverse-engineering and
open-source work of the OCT file format community, notably:

- [eyepy](https://github.com/MedVisBonn/eyepy) (Olivier Morelle et al.)
- [OCT-Converter](https://github.com/marksgraham/OCT-Converter) (Mark Graham et al.)
- [LibE2E](https://github.com/neurodial/LibE2E) and the broader
  [uocte](https://bitbucket.org/uocte/uocte/wiki/Home) documentation effort

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for full license texts.

## License

[MIT](LICENSE)
