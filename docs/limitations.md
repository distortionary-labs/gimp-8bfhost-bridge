# Limitations

- **Color modes.** Indexed images must be converted to RGB first, and 32-bit integer and floating-point images to 8 or 16 bits (**Image > Precision**). 16-bit grayscale layers with an alpha channel are not supported yet, because 8bf-host cannot write that layout back as PAM, the image format the plug-in exchanges with it.
- **Color profiles.** Filters receive sRGB-encoded samples. GIMP converts images in linear precision, or with a profile other than sRGB, on the way out and back, which can shift colors slightly in pixels the filter did not change.
- **The menu follows 8bf-host at startup.** GIMP registers a plug-in's menu entries when it starts, so filters you add, and changes to the settings, appear in the menu after a restart.
- **Filters that cannot run** on your system are listed with "(cannot run)" after their name. GIMP has no way to grey out a single plug-in entry, so choosing one shows 8bf-host's reason instead.
- **Filter windows.** The dialog belongs to the 8bf-host process, so it may open behind GIMP's window.
- **Progress.** 8bf-host does not report progress, so GIMP's progress bar only shows that a filter is running. Cancel a filter from its own dialog.
- **About boxes.** The plug-in has no menu entry for a filter's About box; `8bf-host about <filter id>` shows it.
- **Filter compatibility.** Everything in 8bf-host's [compatibility notes](https://github.com/distortionary-labs/8bf-host/blob/main/docs/compatibility.md) applies. Some commercial filters check for Photoshop specifically and refuse to run anywhere else.
