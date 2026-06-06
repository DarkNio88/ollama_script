#!/usr/bin/env python3
"""Interactive Ollama model remover using a curses selector.

Usage: python3 ollama_rm_interactive.py

Requirements: `ollama` must be installed and in PATH.
"""
import curses
import subprocess
import json
import shlex
import sys
import urllib.request
import difflib
import argparse


def get_models():
    try:
        # Ollama does not support JSON output here; use plain text parsing
        p = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        import re
        lines = p.stdout.splitlines()
        models = []
        for line in lines:
            line = line.rstrip()
            if not line:
                continue
            # Skip header lines like 'NAME' or similar
            # Split columns by 2+ spaces to support tabular output like:
            # NAME   ID   SIZE   MODIFIED
            cols = re.split(r"\s{2,}", line.strip())
            if not cols:
                continue
            # If it's header line starting with NAME, skip
            if cols[0].upper() == "NAME":
                continue
            name = cols[0]
            size = None
            modified = None
            if len(cols) >= 3:
                # cols[2] often SIZE
                size = cols[2]
            if len(cols) >= 4:
                modified = cols[3]
            models.append((name, size, modified))
        return models
    except FileNotFoundError:
        print("`ollama` not found in PATH", file=sys.stderr)
        sys.exit(1)


def run_rm(model):
    cmd = ["ollama", "rm", model]
    try:
        p = subprocess.run(cmd)
        return p.returncode == 0
    except FileNotFoundError:
        return False


def check_updates():
    """Fetch the script from GitHub and compare to local file, printing a unified diff."""
    raw_url = "https://raw.githubusercontent.com/DarkNio88/ollama_script/main/ollama_rm_interactive.py"
    creator = "DarkNio88"
    try:
        with urllib.request.urlopen(raw_url, timeout=10) as resp:
            remote = resp.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"Failed to fetch remote file: {e}")
        return
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            local = f.read().splitlines()
    except Exception as e:
        print(f"Failed to read local file: {e}")
        return

    if remote == local:
        print(f"No updates found — local script is up to date. (creator: {creator})")
        return

    diff = difflib.unified_diff(local, remote, fromfile='local', tofile='remote', lineterm='')
    print(f"Creator: {creator}\n")
    print('\n'.join(diff))


def notify_update_available():
    """Quick check: if remote differs, print a short notification to console."""
    raw_url = "https://raw.githubusercontent.com/DarkNio88/ollama_script/main/ollama_rm_interactive.py"
    creator = "DarkNio88"
    try:
        with urllib.request.urlopen(raw_url, timeout=5) as resp:
            remote = resp.read().decode('utf-8')
    except Exception:
        return
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            local = f.read()
    except Exception:
        return
    if remote != local:
        print(f"[UPDATE] A newer version of ollama_rm_interactive.py is available (creator: {creator}). Run with --check-updates to see changes.")


def apply_updates(auto=False):
    """Fetch remote script and overwrite local file after confirmation.
    If auto=True, do not ask for confirmation.
    """
    raw_url = "https://raw.githubusercontent.com/DarkNio88/ollama_script/main/ollama_rm_interactive.py"
    creator = "DarkNio88"
    try:
        with urllib.request.urlopen(raw_url, timeout=10) as resp:
            remote = resp.read().decode('utf-8')
    except Exception as e:
        print(f"Failed to fetch remote file: {e}")
        return
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            local = f.read()
    except Exception as e:
        print(f"Failed to read local file: {e}")
        return
    if remote == local:
        print(f"Local script is already up to date. (creator: {creator})")
        return
    print(f"Remote version differs from local (creator: {creator}). Showing diff:\n")
    diff = difflib.unified_diff(local.splitlines(), remote.splitlines(), fromfile='local', tofile='remote', lineterm='')
    print('\n'.join(diff))
    if not auto:
        resp = input("Overwrite local script with remote version? [y/N]: ").strip().lower()
        if resp != 'y':
            print("Aborted update.")
            return
    # write backup
    try:
        with open(__file__ + '.bak', 'w', encoding='utf-8') as b:
            b.write(local)
        with open(__file__, 'w', encoding='utf-8') as f:
            f.write(remote)
        print("Update applied. Backup written to " + __file__ + ".bak")
    except Exception as e:
        print(f"Failed to write updated file: {e}")


def curses_menu(stdscr, items):
    curses.curs_set(0)
    h, w = stdscr.getmaxyx()
    selected = 0
    offset = 0
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "Select models to remove (space to toggle, Enter to confirm, q to quit)")
        # visible area height
        visible_h = h - 3
        for vis_idx in range(visible_h):
            idx = offset + vis_idx
            if idx >= len(items):
                break
            item = items[idx]
            x = 2
            y = vis_idx + 2
            # Do not make the 'NAME' header selectable
            is_header = item["name"].upper() == "NAME"
            prefix = "[x] " if item.get("selected") else "[ ] "
            display = item["name"]
            if item.get("size"):
                display = f"{display} ({item['size']})"
            if is_header:
                stdscr.addstr(y, x, "    " + display)
            else:
                if idx == selected:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(y, x, prefix + display)
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(y, x, prefix + display)
        stdscr.refresh()

        k = stdscr.getch()
        if k in (curses.KEY_UP, ord('k')):
            # move up skipping headers
            nxt = selected - 1
            while nxt >= 0 and items[nxt]["name"].upper() == "NAME":
                nxt -= 1
            selected = max(0, nxt)
            if selected < offset:
                offset = selected
        elif k in (curses.KEY_DOWN, ord('j')):
            nxt = selected + 1
            while nxt < len(items) and items[nxt]["name"].upper() == "NAME":
                nxt += 1
            selected = min(len(items) - 1, nxt)
            if selected >= offset + visible_h:
                offset = selected - visible_h + 1
        elif k == ord(' '):
            if items[selected]["name"].upper() != "NAME":
                items[selected]["selected"] = not items[selected]["selected"]
        elif k in (curses.KEY_ENTER, 10, 13):
            return [it["name"] for it in items if it["selected"]]
        elif k in (ord('q'), 27):
            return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-updates", action="store_true", help="Check for updates from GitHub repo")
    parser.add_argument("--apply-updates", action="store_true", help="Fetch and apply updates from GitHub repo (asks confirmation)")
    parser.add_argument("--yes-apply", action="store_true", help="Apply updates without confirmation")
    args = parser.parse_args()

    if args.check_updates:
        check_updates()
        return
    if args.apply_updates:
        apply_updates(auto=args.yes_apply)
        return

    # Notify user if remote script differs (non-blocking short check)
    notify_update_available()

    models = get_models()
    if not models:
        print("No models found.")
        return
    # models may be list[str] or list[(name,size)] depending on parsing
    items = []
    for m in models:
        if isinstance(m, tuple):
            if len(m) == 3:
                name, size, modified = m
            elif len(m) == 2:
                name, size = m
                modified = None
            else:
                name = m[0]
                size = None
                modified = None
        else:
            name, size, modified = m, None, None
        items.append({"name": name, "size": size, "modified": modified, "selected": False})
    # Insert header row (non-selectable)
    items.insert(0, {"name": "NAME", "size": "SIZE", "selected": False})
    try:
        selected = curses.wrapper(curses_menu, items)
    except KeyboardInterrupt:
        print("Cancelled.")
        return

    if not selected:
        print("No models selected. Exiting.")
        return

    print("About to remove:")
    for m in selected:
        print(" -", m)
    confirm = input("Proceed? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        return

    for m in selected:
        print(f"Removing {m}...")
        ok = run_rm(m)
        print("OK" if ok else "FAILED")


if __name__ == '__main__':
    main()
