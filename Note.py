class Note:
    def __init__(
        self,
        title,
        content,
        category,
        tags=None,
        image_path=None,
        timestamp=None,
        db_id=None,
    ):
        self.title = title
        self.content = content
        self.category = category
        self.tags = tags or []
        self.image_path = image_path
        self.timestamp = timestamp or datetime.now().isoformat()
        self.db_id = db_id

    def to_markdown(self):
        tags_str = " ".join(f"#{t}" for t in self.tags)
        md = f"### {self.title}\n- Date: {self.timestamp}\n- Tags: {tags_str}\n\n{self.content}"
        if self.image_path:
            md += f"\n\n![]({self.image_path})"
        return md

    def to_json(self):
        return {
            "id": self.db_id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "image": self.image_path,
            "timestamp": self.timestamp,
        }
