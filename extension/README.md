# Browser extension preview

This is a local blueprint viewer, not a cryptocurrency wallet. It has no network, host, scripting, or signing permission. It stores only the imported design choices in the browser's extension storage.

In Studio, click **Export extension configuration** and **Download preview extension**. Unzip the downloaded extension, open `chrome://extensions`, turn on Developer mode, choose **Load unpacked**, and select the unzipped directory containing `manifest.json`. Open the toolbar popup and import the JSON configuration.

To rebuild the download after changing the extension, run `python extension/package.py` from the repository root. The generated ZIP has `manifest.json` at its root.
