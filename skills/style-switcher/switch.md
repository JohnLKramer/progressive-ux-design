# Switch mode

Serve a workspace so the user can flip through its pages in each style. The preview is a local server; it exists only while its process runs.

## Steps

1. **Check the layout.** The workspace needs `pages/<slug>/index.html` for each page and `styles/<id>/` for each style. If either is missing, stop and say what is missing.
2. **Validate everything first.** Run each of these and stop on any problem, showing its output unchanged:
   - `python3 -I <skill-dir>/scripts/validate.py page <workspace>/pages/<slug>/index.html`, once per page.
   - `python3 -I <skill-dir>/scripts/validate.py style <workspace>/styles/<id>`, once per style.

   The server repeats this validation and rebuilds the manifest, so a problem also stops it with a message; keep this step anyway so you can show the problems before starting it. Never serve a page or style that failed. Do not fix it silently.
3. **Start the server as a long-lived process.** Run `python3 -I <skill-dir>/scripts/switcher.py <workspace>` with the harness's background-command facility, so it keeps running after your command returns. Do not append `&` to a short command: it dies when that command ends. The script writes and validates `manifest.json` itself, opens the default browser, and prints the URL on one line.
   - Add `--no-open` when no browser can be reached from where you run. The URL is then the only way in.
   - If it exits with an error, show the error and stop.
4. **Check it is still running, then report.** Read the process output for the URL. If the process has stopped, report that and the error, not a URL. Otherwise give the URL and tell the user:
   - the preview lasts only while that process runs;
   - the port changes on every run, so an old URL stops working;
   - to stop it, end the background process (or press Ctrl-C if it runs in their terminal).

## Reply example

> Preview running at http://127.0.0.1:52831/ (3 pages, 4 styles). Left and right arrows move between pages; the dropdown changes style; the display mode toggle switches between style plus layout (the default, mode 2) and style only; the width dropdown previews the page at 1440, 1280, 1024, 768 or 390 pixels. A style without a layout file shows a yellow note saying so. It stops when I end the process, and the port will differ next time.
