# from sqlalchemy.orm import Session
# from models import Tag
# from db import SessionLocal
# import json

# with open("hierarchy.json", "r", encoding="utf-8") as f:
#     hierarchy = json.load(f)


# def add_tags(node, db: Session, parent=None):
#     """
#     Recursively insert tags from hierarchy.json.
#     Ensures all names are lowercase + trimmed.
#     Commits once at the end.
#     """

#     # Cache existing tags to avoid repeated queries
#     existing = {t.name: t for t in db.query(Tag).all()}

#     def _walk(subnode, parent_tag=None):
#         if isinstance(subnode, dict):
#             for raw_name, children in subnode.items():
#                 name = normalize(raw_name)

#                 tag = existing.get(name)
#                 if not tag:
#                     tag = Tag(name=name, parent=parent_tag)
#                     db.add(tag)
#                     existing[name] = tag

#                 _walk(children, parent_tag=tag)

#         elif isinstance(subnode, list):
#             for raw_child in subnode:
#                 name = normalize(raw_child)

#                 if name not in existing:
#                     child = Tag(name=name, parent=parent_tag)
#                     db.add(child)
#                     existing[name] = child

#     _walk(node, parent)
#     db.commit()


# db: Session = SessionLocal()
# add_tags(hierarchy, db=db)
# db.close()

# print("✅ Tags populated (trimmed + lowercase)")
