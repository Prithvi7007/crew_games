#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path.cwd()
weekly = root / "app" / "weekly_email.py"
template = root / "app" / "templates" / "emails" / "weekly_kickoff.html"
tests = root / "tests" / "test_weekly_email.py"

for p in (weekly, template, tests):
    if not p.exists():
        print("ERROR: Run this from the crew_games repository root.")
        print(f"Missing: {p}")
        sys.exit(1)

def apply(path, replacements):
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new, label in replacements:
        if old in text:
            text = text.replace(old, new, 1)
        elif new in text:
            print(f"UNCHANGED {path.relative_to(root)} - {label} already applied")
        else:
            print(f"ERROR: Expected text not found for: {label}")
            print(f"File: {path.relative_to(root)}")
            sys.exit(1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"UPDATED {path.relative_to(root)}")

apply(weekly, [
    (
        'return f"CREW Weekly | Week {context[\'current_week_number_label\']} is Live"',
        'return f"CREW Games Weekly | Week {context[\'current_week_number_label\']} is Live"',
        "subject"
    ),
    (
        '"CREW WEEKLY",',
        '"CREW GAMES WEEKLY",',
        "plain-text heading"
    ),
])

apply(template, [
    (
        "<title>CREW Weekly</title>",
        "<title>CREW Games Weekly</title>",
        "HTML title"
    ),
    (
        'CREW<span style="color:#0a84ff;">+</span> WEEKLY',
        'CREW<span style="color:#0a84ff;">+</span>',
        "masthead WEEKLY removal"
    ),
    (
        '''              <div style="font-size:12px;font-weight:800;letter-spacing:1.6px;color:#0a84ff;text-transform:uppercase;">
                Week {{ current_week_number_label }}
              </div>
''',
        "",
        "duplicate blue Week number"
    ),
    (
        '<div class="hero-title" style="padding-top:8px;font-size:42px;line-height:48px;font-weight:800;letter-spacing:-1px;color:#10243b;">',
        '<div class="hero-title" style="padding-top:0;font-size:42px;line-height:48px;font-weight:800;letter-spacing:-1px;color:#10243b;">',
        "hero spacing"
    ),
])

apply(tests, [
    (
        'assert rendered["subject"] == "CREW Weekly | Week 02 is Live"',
        'assert rendered["subject"] == "CREW Games Weekly | Week 02 is Live"',
        "subject test"
    ),
])

print()
print("Header cleanup applied.")
print("Next:")
print("  git diff --check")
print("  git status --short")
