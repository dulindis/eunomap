import csv


class ExportBuilder:
    def __init__(self, notes):
        self.notes = notes  # list of Note objects

    def to_markdown(self, title="My Notes Collection"):
        md = f"# {title}\n\n"
        for note in self.notes:
            md += note.to_markdown() + "\n\n---\n\n"
        return md

    def to_json(self):
        return [note.to_json() for note in self.notes]

    def to_csv(self, filepath):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["Title", "Category", "Content", "Tags", "Timestamp", "Image"]
            )
            for note in self.notes:
                writer.writerow(
                    [
                        note.title,
                        note.category,
                        note.content,
                        ", ".join(note.tags),
                        note.timestamp,
                        note.image_path or "",
                    ]
                )
