# --- Utility functions ---
from Note import Note

import json, os


def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)


def append_md(path, md_text):
    with open(path, "a", encoding="utf-8") as f:
        f.write(md_text + "\n\n---\n\n")


def save_json(path, note_json):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []
    data.append(note_json)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_note(note: Note, data_dir):
    cat_dir = os.path.join(data_dir, note.category)
    ensure_folder(cat_dir)
    md_path = os.path.join(cat_dir, f"{note.category}.md")
    json_path = os.path.join(cat_dir, f"{note.category}.json")

    # Save Markdown
    append_md(md_path, note.to_markdown())
    # Save JSON
    save_json(json_path, note.to_json())


def flatten(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from flatten(value)

    elif isinstance(obj, list):
        for element in obj:
            if isinstance(element, (dict, list)):
                yield from flatten(element)
            else:
                yield element
