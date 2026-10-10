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
- Browse acquisitions grouped by visit date in the left tree
- View standalone enface images such as BAF and extra IR/SLO captures
- View the fundus/IR localizer image alongside the B-scan stack
- Step through B-scans with a slider, spinbox, arrow keys, or mouse wheel
- Zoom (mouse wheel) and pan (drag) on both images
- Double-click either image to open a larger detail view
- Scan-position overlay: current B-scan line + full scan-area box on the
  fundus image
- Optional ETDRS rings (1, 3 and 6 mm) on the fundus image, matching colored
  lines on the B-scan, and a lateral scale bar. Lateral millimeters are an
  estimate and are labeled as such. See [ETDRS rings](#etdrs-rings)
- Contrast/brightness adjustment
- Patient/series/B-scan metadata table (`View > Image Info`)
- Packaged as a standalone executable - no Python installation required to
  run it

## Download

Prebuilt Windows and macOS builds are available under
[Releases](../../releases) (or as [Actions build artifacts](../../actions)
for the latest commit).

**macOS note:** builds are universal binaries that run on both Apple Silicon
(M1/M2/…) and Intel Macs. They are not code-signed/notarized (that requires a
paid Apple Developer account), so macOS Gatekeeper will block the app the
first time you launch it.

**First launch (pick one method):**

1. **Right-click > Open** (not double-click): right-click `OCT Viewer.app`,
   choose **Open**, then click **Open** again in the warning dialog.
2. If you still see *"the developer cannot be verified"*, macOS has quarantined
   the download. Open **Terminal** and run (adjust the path if needed):

   ```bash
   xattr -cr ~/Downloads/OCT\ Viewer.app
   ```

   Then right-click the app > **Open** again.
3. Or: try to open the app once (it will fail), then go to **System Settings >
   Privacy & Security**, scroll down, and click **Open Anyway** next to OCT
   Viewer.

After the first successful launch, you can open it normally by double-clicking.

**App bounces in the Dock then disappears?** The app is crashing on launch.
Open **Terminal**, run (adjust the path), and paste the output when reporting
issues:

```bash
~/Downloads/OCT\ Viewer.app/Contents/MacOS/OCT\ Viewer
```

That prints the real error (missing library, architecture mismatch, etc.)
instead of failing silently.

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

### Testing a build before tagging a release

You cannot fully test a macOS `.app` from Windows. Use GitHub Actions instead:

1. Push your changes to `main`.
2. Open **Actions → Build → Run workflow** (`workflow_dispatch`) - no tag needed.
3. Wait for the job to finish (macOS is slower: universal arm64 + Intel).
4. Download the macOS/Windows artifacts from that run and try them (or rely on
   the CI smoke test, which launches the frozen app and fails on import crashes).
5. Only then tag `vX.Y.Z` to create the GitHub Release.

CI already checks: universal Mach-O slices, code signature, and a short launch
smoke test (arm64 + Rosetta x86_64 on macOS).

## ETDRS rings

The overlay draws the standard 1, 3 and 6 mm circles on the localizer and
marks where the current B-scan crosses each circle. The center is the
localizer coordinate origin. Eyepy does not read a fovea landmark, so that
origin (the image center) is the assumed fovea.

Lateral millimeters are estimated. The viewer says so next to the checkboxes,
prints "estimated" on the image, and prefixes the scale bar with "est.".
B-scan depth, in mm per pixel, is read from the file and is separate from
this estimate.

The estimate has two parts, and neither is stored as a millimeter scale in
the `.e2e`:

- Eyepy reports B-scan positions as degrees from the localizer center, and
  hardcodes the localizer field to 30°. It has not identified the real field
  size or a lateral mm-per-pixel value in this format. The only B-scan scale
  it can read is axial (`scale_y`, mm per pixel).
- Degrees are turned into millimeters with 288 µm per degree, the Spectralis
  standard eye (axial length 24.385 mm). A nominal 20° scan is often about
  6 mm in HEYEX; this factor makes it 5.76 mm. Refraction and corneal
  curvature change the real transverse size, and those adjustments are not
  applied.

There is no place to type a measurement in by hand. People using this viewer
normally have only the `.e2e`.

### Follow-up: read the lateral scale from the file

Replace the hardcoded 30° field and `MM_PER_DEG` in
`src/oct_viewer/etdrs.py` once the `.e2e` actually yields them. The same 30°
assumption is copied for standalone enface images in `src/oct_viewer/parser.py`.
Keep the on-image "estimated" label until a decoded value matches a
known-good export, then drop the label for series where the scale was read.

1. Collect paired data from the same exam: the `.e2e`, a HEYEX `.vol` or
   `.xml` export (those store localizer `ScaleX` in mm and the field angle),
   and a HEYEX screenshot of the ETDRS grid. Include more than one field size
   (for example 20°, 30°, and 55°) and eyes with different refraction, so one
   hardcoded constant cannot fit every file by accident.
2. Decode localizer metadata, chunk type 10025. It is 100 bytes: 24 unknown
   bytes, a timestamp, and a 6-float affine transform. Eyepy parses the
   transform and does not apply it. Check whether it maps pixels to
   millimeters or to degrees.
3. Search the chunk types eyepy still treats as unknown for a mm-per-pixel
   value or a field angle that matches `ScaleX` and `Angle` in the paired
   VOL/XML file.
4. The measurements chunk (type 7) stores refraction and corneal curvature.
   HEYEX adjusts transverse scale from those, and it does not let the operator
   replace its preset axial length of 24.385 mm. See whether those two fields
   reproduce the VOL/XML scale. Axial length itself does not appear to be in
   the `.e2e`.
5. When a field matches, use it for the rings and the scale bar, and remove
   the "estimated" label on that series. Leave the label where the field is
   missing.

## How it works

The `.e2e` format has no public specification. This project combines two
MIT-licensed, independently reverse-engineered readers:

- [`oct-converter`](https://github.com/marksgraham/OCT-Converter) for the chunk
  directory layout and date helpers used to read patient demographics
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
