"""Desktop webapp manager for SigmaOS-webapp-manager.

The engine plans .desktop launchers for websites (pure string generation),
parses an applications directory, validates removals (path-traversal guard)
and plans isolated browser profiles (one data dir per site, derived from a
stable URL hash). Writing/unlinking files is the thin execute layer --
self_test() only exercises the pure plan/parse layer (tempfile for any fs use).
Principles: Defensive Programming, Fail-Fast, Separation of Concerns, KISS.
"""
import argparse, hashlib, os, re, shlex, sys, urllib.parse

ENGINE = {
    "name": "sigma-webapp",
    "summary": "Create, list, remove and isolate desktop webapps",
    "language": "python",
    "verbs": ["create", "list", "remove", "isolate-plan"],
    "principles": ["Defensive Programming", "Fail-Fast",
                   "Separation of Concerns", "KISS", "Deterministic Testing"],
}

cli_doc = """\
$ sigma-webapp create "Mail" https://mail.example.com --write
~/.local/share/applications/mail.desktop
$ sigma-webapp list
Mail  https://mail.example.com  chromium
$ sigma-webapp remove ~/.local/share/applications/mail.desktop --apps-dir ~/.local/share/applications --execute
$ sigma-webapp isolate-plan https://mail.example.com
chromium --user-data-dir=... --app=https://mail.example.com
"""


class WebappError(Exception):
    pass


DEFAULT_APPS_DIR = os.path.expanduser("~/.local/share/applications")
DEFAULT_PROFILE_ROOT = os.path.expanduser("~/.local/share/sigma-webapps/profiles")
BROWSERS = ("chromium", "google-chrome", "firefox", "brave-browser", "vivaldi")


# --------------------------------------------------------------------------- #
#  PURE plan / parse layer
# --------------------------------------------------------------------------- #
def validate_url(url):
    """Validate an http(s) URL; returns it unchanged."""
    if not isinstance(url, str) or not url.strip():
        raise WebappError("empty URL")
    url = url.strip()
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise WebappError(f"URL must be http(s): {url!r}")
    if not parts.netloc or " " in url:
        raise WebappError(f"malformed URL: {url!r}")
    return url


def slug(name):
    """Derive a .desktop filename stem from an app name."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    if not s:
        raise WebappError(f"cannot derive a filename from name: {name!r}")
    return s


def create_plan(name, url, icon="web-browser", browser="chromium",
                profile=None):
    """Generate a .desktop webapp launcher (pure string building)."""
    if not isinstance(name, str) or not name.strip():
        raise WebappError("empty app name")
    if any(c in name for c in "\n\r[]"):
        raise WebappError(f"app name contains illegal characters: {name!r}")
    url = validate_url(url)
    if browser not in BROWSERS:
        raise WebappError(f"unknown browser {browser!r} "
                          f"(choose from {', '.join(BROWSERS)})")
    if not icon or "\n" in icon:
        raise WebappError(f"bad icon: {icon!r}")
    # .desktop Exec parsing follows the Desktop Entry spec (no shell quoting);
    # validate_url already rejects whitespace in URLs.
    exec_line = f"{browser} --app={url}"
    if profile:
        exec_line += f" --user-data-dir={profile}"
    content = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        f"Name={name.strip()}\n"
        f"Comment=Web application: {url}\n"
        f"Exec={exec_line}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Network;WebBrowser;\n"
        "StartupNotify=true\n"
        f"X-SigmaOS-URL={url}\n"
        f"X-SigmaOS-Browser={browser}\n"
    )
    return {"filename": slug(name) + ".desktop", "content": content,
            "url": url, "name": name.strip(), "browser": browser}


def parse_apps(directory):
    """Parse .desktop launchers in `directory` into app records."""
    if not os.path.isdir(directory):
        return []
    apps = []
    for entry in sorted(os.listdir(directory)):
        if not entry.endswith(".desktop"):
            continue
        path = os.path.join(directory, entry)
        fields = {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                in_entry = False
                for raw in fh:
                    line = raw.rstrip("\n")
                    if line.strip() == "[Desktop Entry]":
                        in_entry = True
                        continue
                    if line.startswith("["):
                        in_entry = False
                    if not in_entry or "=" not in line or line.startswith("#"):
                        continue
                    key, _, value = line.partition("=")
                    fields[key.strip()] = value.strip()
        except OSError:
            continue
        if "Name" not in fields:
            continue
        apps.append({
            "file": entry,
            "name": fields.get("Name", entry),
            "url": fields.get("X-SigmaOS-URL", ""),
            "browser": fields.get("X-SigmaOS-Browser", ""),
            "exec": fields.get("Exec", ""),
            "webapp": "X-SigmaOS-URL" in fields,
        })
    return apps


def remove_plan(path, apps_dir=DEFAULT_APPS_DIR, execute=False):
    """Validate a launcher removal; refuses anything outside apps_dir."""
    if not path or not isinstance(path, str):
        raise WebappError("no launcher path given")
    ap = os.path.abspath(os.path.expanduser(path))
    ad = os.path.abspath(os.path.expanduser(apps_dir))
    if not ap.endswith(".desktop"):
        raise WebappError("refusing to remove a non-.desktop file")
    if os.path.dirname(ap) != ad:
        raise WebappError(f"refusing to remove outside {ad}")
    if not os.path.isfile(ap):
        raise WebappError(f"no such launcher: {ap}")
    return {"action": "remove", "path": ap, "execute": bool(execute)}


def isolate_plan(url, browser="chromium", profile_root=DEFAULT_PROFILE_ROOT):
    """Plan an isolated per-site browser profile (stable URL-derived hash)."""
    url = validate_url(url)
    if browser not in BROWSERS:
        raise WebappError(f"unknown browser: {browser!r}")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    profile = os.path.join(os.path.expanduser(profile_root), digest)
    argv = [browser, f"--user-data-dir={profile}", f"--app={url}",
            "--no-first-run", "--disable-sync", "--no-default-browser-check"]
    return {"argv": argv, "profile": profile, "hash": digest, "url": url}


# --------------------------------------------------------------------------- #
#  Execute layer (side-effecting; never run by self_test directly)
# # --------------------------------------------------------------------------- #
def write_desktop(path, content):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    p.add_argument("--apps-dir", default=DEFAULT_APPS_DIR)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = sub.add_parser("create", help="plan (and optionally write) a webapp")
    cr.add_argument("name")
    cr.add_argument("url")
    cr.add_argument("--icon", default="web-browser")
    cr.add_argument("--browser", default="chromium", choices=list(BROWSERS))
    cr.add_argument("--profile", default=None)
    cr.add_argument("--write", action="store_true", help="write the .desktop file")
    ls = sub.add_parser("list", help="list installed webapps")
    rm = sub.add_parser("remove", help="remove a webapp launcher")
    rm.add_argument("path")
    rm.add_argument("--execute", action="store_true", help="perform the removal")
    ip = sub.add_parser("isolate-plan", help="plan an isolated browser profile")
    ip.add_argument("url")
    ip.add_argument("--browser", default="chromium", choices=list(BROWSERS))
    ip.add_argument("--profile-root", default=DEFAULT_PROFILE_ROOT)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "create":
            plan = create_plan(args.name, args.url, args.icon, args.browser,
                               args.profile)
            path = os.path.join(os.path.expanduser(args.apps_dir), plan["filename"])
            if args.write:
                write_desktop(path, plan["content"])
                print(path)
            else:
                print(plan["content"], end="")
        elif args.cmd == "list":
            for a in parse_apps(args.apps_dir):
                kind = "webapp" if a["webapp"] else "desktop"
                print(f'{a["name"]}  {a["url"] or "-"}  '
                      f'{a["browser"] or "-"}  [{kind}: {a["file"]}]')
        elif args.cmd == "remove":
            plan = remove_plan(path=args.path, apps_dir=args.apps_dir,
                               execute=args.execute)
            if plan["execute"]:
                os.remove(plan["path"])
                print(f'removed {plan["path"]}')
            else:
                print(f'would remove {plan["path"]} (pass --execute)')
        elif args.cmd == "isolate-plan":
            plan = isolate_plan(args.url, args.browser, args.profile_root)
            print(" ".join(shlex.quote(a) for a in plan["argv"]))
        return 0
    except (WebappError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


# --------------------------------------------------------------------------- #
#  Tests (pure plan/parse layer; filesystem use limited to tempfile)
# --------------------------------------------------------------------------- #
def self_test() -> None:
    plan = create_plan("Mail", "https://mail.example.com/inbox?a=1")
    assert plan["filename"] == "mail.desktop"
    content = plan["content"]
    assert "[Desktop Entry]" in content and "Type=Application" in content
    assert "Name=Mail" in content
    assert "Exec=chromium --app=https://mail.example.com/inbox?a=1" in content
    assert "Icon=web-browser" in content
    assert "X-SigmaOS-URL=https://mail.example.com/inbox?a=1" in content
    assert content.endswith("\n")
    assert create_plan("My  WebApp!", "http://x.example.com")["filename"] == \
        "my-webapp.desktop"
    for bad in (("", "https://x.example.com"),
                ("Mail", "ftp://x.example.com"),
                ("Mail", "not a url"),
                ("Mail", ""),
                ("Mail", "https://x.example.com", "web-browser", "netscape"),
                ("Bad\nName", "https://x.example.com")):
        try:
            create_plan(*bad)
        except WebappError:
            pass
        else:
            raise AssertionError(f"bad create not rejected: {bad!r}")

    assert validate_url(" https://ok.example.com/x ") == "https://ok.example.com/x"
    try:
        validate_url("javascript:alert(1)")
    except WebappError:
        pass
    else:
        raise AssertionError("non-http scheme not rejected")

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        write_desktop(os.path.join(d, "mail.desktop"),
                      create_plan("Mail", "https://mail.example.com")["content"])
        write_desktop(os.path.join(d, "calc.desktop"),
                      "[Desktop Entry]\nName=Calc\nType=Application\n"
                      "Exec=gnome-calculator\nIcon=calc\n")
        apps = parse_apps(d)
        assert [a["name"] for a in apps] == ["Calc", "Mail"], apps
        assert apps[1]["webapp"] is True and apps[0]["webapp"] is False
        assert apps[1]["url"] == "https://mail.example.com"
        # removal must stay inside the apps dir
        ok = remove_plan(os.path.join(d, "mail.desktop"), d)
        assert ok["path"].endswith("mail.desktop") and ok["execute"] is False
        for bad in (("../../etc/passwd.desktop", d),
                    (os.path.join(d, "notes.txt"), d),
                    (os.path.join(d, "ghost.desktop"), d),
                    ("/etc/hosts", d)):
            try:
                remove_plan(*bad)
            except WebappError:
                pass
            else:
                raise AssertionError(f"unsafe removal not rejected: {bad!r}")
        assert parse_apps(os.path.join(d, "no-such-dir")) == []

    one = isolate_plan("https://mail.example.com")
    two = isolate_plan("https://mail.example.com")
    assert one == two                                   # deterministic hash
    assert len(one["hash"]) == 12
    assert one["profile"].endswith(one["hash"])
    assert one["argv"][0] == "chromium" and "--app=https://mail.example.com" in one["argv"]
    other = isolate_plan("https://chat.example.com")
    assert other["hash"] != one["hash"]                 # per-site isolation
    try:
        isolate_plan("https://x.example.com", browser="netscape")
    except WebappError:
        pass
    else:
        raise AssertionError("unknown browser not rejected")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
