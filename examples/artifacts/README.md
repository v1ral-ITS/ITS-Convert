# ITS-Convert public AppImage demo

This is a neutral example produced by ITS-Convert and standard public AppImage tools. It contains `examples/hello.py`, a launcher, desktop metadata, an ITS icon, and the upstream AppImage runtime. It contains no personal application, custom private builder, or credentials.

## Run

On x86_64 Linux with `python3` installed:

```bash
sha256sum -c SHA256SUMS
chmod +x hello-x86_64.AppImage
./hello-x86_64.AppImage --appimage-extract-and-run
```

Expected output:

```text
Hello from ITS-Convert | ImPerial TeK. Solutions
```

The extract-and-run flag avoids requiring FUSE. This Python demo uses the host's `python3`; it does not embed a Python interpreter. It is not a Windows executable.

## Build provenance

- Built and executed on October 13, 2026, in Ubuntu WSL on x86_64.
- Source: [`../hello.py`](../hello.py), distributed under this repository's MIT license.
- Backend: `itsconvert build examples/hello.py --builder appimage --use-appimagetool --output-dir dist/appimage-demo`.
- Standard tool: [AppImage/appimagetool release 1.9.1](https://github.com/AppImage/appimagetool/releases/tag/1.9.1), `appimagetool-x86_64.AppImage`.
- Tool SHA-256: `ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0`.
- Demo SHA-256: `c3653aa81ef3ebd081fbed0ff6782114998653d2bce1cef7fef2a06c39c7e3ca`.
- AppImage runtime is supplied by the upstream tool, with its [upstream source and license](https://github.com/AppImage/type2-runtime). Repository MIT licensing applies to our source, not to a replacement of upstream licenses.

## Rebuild

Install the Python project and put appimagetool on PATH. Then:

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 itsconvert build examples/hello.py --builder appimage --use-appimagetool --output-dir dist/appimage-demo
./dist/appimage-demo/hello-x86_64.AppImage --appimage-extract-and-run
sha256sum dist/appimage-demo/hello-x86_64.AppImage
```

The GitHub AppImage workflow performs the same neutral build. Timestamps and upstream runtime downloads may change rebuilt bytes; verify the committed artifact against `SHA256SUMS` rather than expecting every rebuild to be byte-identical.

This directory is included in the npm tarball, Python source distribution, and wheel data under `share/itsconvert/examples/artifacts`. The demo is never executed automatically during installation.
