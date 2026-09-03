"""Application icon discovery and system integration for MoveAny (CLI and GUI)."""

import os
import sys


def get_asset_path(filename: str) -> str | None:
    """Find the path to an asset file in package or project root directories."""
    candidates = [
        # Inside moveany/assets/ (bundled package data)
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", filename),
        # Inside root assets/
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", filename),
        # Relative to current working directory
        os.path.join(os.getcwd(), "assets", filename),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def get_icon_path(size: int | None = None, ext: str = "ico") -> str | None:
    """Get the path to an icon file.

    Priority: if size is specified, try that size first.
    Otherwise prefer the highest available resolution (512x512),
    then fall back to smaller sizes for backward compatibility.
    """
    ext = ext.lstrip(".").lower()
    sizes_to_try = []

    if size:
        sizes_to_try = [size]
    else:
        # Prefer 512x512 as the high-res source, then fallback
        sizes_to_try = [512, 256, 128, 64, 48, 32, 24, 20, 16]

    for s in sizes_to_try:
        patterns = [
            f"icon_{s}x{s}.{ext}",
            f"icon_{s}.{ext}",
            f"icon-{s}.{ext}",
        ]
        for name in patterns:
            path = get_asset_path(name)
            if path:
                return path

    # Last resort: default names
    default_names = [
        f"icon.{ext}",
        f"moveany.{ext}",
        "icon.ico" if ext != "ico" else "icon.png",
    ]
    for name in default_names:
        path = get_asset_path(name)
        if path:
            return path
    return None


def set_cli_icon() -> bool:
    """Set the Windows console window and taskbar identity icon for the MoveAny CLI process.

    Returns True if the icon was successfully set, False otherwise.
    Safe to call on any platform (no-op on Linux/macOS).

    Uses the highest available resolution icon from the ICO file to prevent
    Windows from scaling small icons, which causes blurriness.
    """
    if sys.platform != "win32":
        return False

    try:
        import ctypes

        # Set explicit AppUserModelID so Windows taskbar groups and identifies MoveAny
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HELIX.MoveAny.CLI")
        except Exception:
            pass

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return False

        ico_path = get_icon_path(ext="ico")
        if not ico_path or not os.path.isfile(ico_path):
            return False

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        # Try multiple sizes - prefer larger sizes to avoid scaling/blurriness
        # Windows taskbar typically uses 256x256 or 128x128 for good quality
        sizes_to_try = [(256, 256), (128, 128), (48, 48), (32, 32), (16, 16)]

        h_icon_sm = None
        h_icon_lg = None

        for large, small in sizes_to_try:
            h_icon_sm = ctypes.windll.user32.LoadImageW(None, ico_path, IMAGE_ICON, small, small, LR_LOADFROMFILE)
            h_icon_lg = ctypes.windll.user32.LoadImageW(None, ico_path, IMAGE_ICON, large, large, LR_LOADFROMFILE)

            # If we got good icons, use them and break
            if h_icon_sm and h_icon_lg:
                break

        success = False
        if h_icon_sm:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_icon_sm)
            success = True
        if h_icon_lg:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_icon_lg)
            success = True

        return success
    except Exception:
        return False


def set_window_icon(window) -> bool:
    """Set the window and taskbar icon for a Tkinter window.

    Safe to call cross-platform.

    Uses the highest available resolution PNG to prevent blurry rendering
    in the window titlebar and taskbar.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HELIX.MoveAny.GUI")
        except Exception:
            pass

    success = False
    # Try setting iconphoto with the highest resolution PNG available
    # Try 512 first, then 256, then 128
    for size in [512, 256, 128]:
        png_path = get_icon_path(size=size, ext="png")
        if png_path and os.path.isfile(png_path):
            try:
                import tkinter as tk
                photo = tk.PhotoImage(file=png_path)
                window.iconphoto(True, photo)
                # Retain a reference on the window to prevent garbage collection
                window._app_icon_photo = photo
                success = True
                break  # Use the highest quality size we found
            except Exception:
                pass

    # Fall back to iconbitmap if iconphoto failed or not on Windows
    if not success:
        ico_path = get_icon_path(ext="ico")
        if sys.platform == "win32" and ico_path and os.path.isfile(ico_path):
            try:
                window.iconbitmap(ico_path)
                success = True
            except Exception:
                pass

    return success
