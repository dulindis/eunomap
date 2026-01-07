# # from utils import normalize, normalize_hierarchy
import json
from utils.hierarchy_utils import normalize_hierarchy, compress_hierarchy

# # test_strings = [
# #     "COVID-19",  # hyphen should stay
# #     "Hello, world!",  # punctuation removed
# #     "foo_bar!",  # underscore removed
# #     "multi   space",  # multiple spaces collapsed
# #     "   Leading and trailing   ",  # spaces trimmed
# #     "C++ programming",  # plus signs removed
# #     "co--op",  # hyphen preserved
# #     "end.",  # punctuation removed
# #     "UPPERCASE",  # converted to lowercase
# #     "numbers123",  # numbers preserved
# #     "special@#$%^&*chars",  # special chars removed
# #     "deep_learning",  # underscore removed
# #     "hyphen-underscore_",  # hyphen preserved, underscore removed
# #     "emoji 😊 test",  # emoji removed
# #     "Mac&CHEESE",  # ampersand preserved
# # ]

# # test_strings = [
# #     "COVID-19",
# #     "C++ programming",
# #     "Mac&CHEESE",
# #     "co--op",
# #     "C#",
# #     "special@#$%^&*chars",
# #     "foo   bar",
# #     "deep_learning",
# #     "AI/ml",
# # ]
# # for s in test_strings:
# #     print(f"Original: '{s}' => Normalized: '{normalize(s)}'")


# def normalize_hierarchy(node, max_depth):
#     print(f"node={node} max_depth={max_depth}")

#     if max_depth == 0:
#         raise RuntimeError("Max depth reached")

#     next_max_depth = max_depth - 1

#     if isinstance(node, dict):
#         return {k: normalize_hierarchy(v, next_max_depth) for (k, v) in node.items()}
#     elif isinstance(node, list):
#         n = len(node)
#         i = 0
#         dst = {}
#         while i < n:
#             x = node[i]
#             if isinstance(x, str):
#                 if i < n - 1 and (
#                     isinstance(node[i + 1], list) or isinstance(node[i + 1], dict)
#                 ):
#                     dst[x] = normalize_hierarchy(node[i + 1], next_max_depth)
#                     i += 2
#                 else:
#                     dst[x] = {}
#                     i += 1
#             else:
#                 raise RuntimeError("Syntax error B")
#         return dst
#     else:
#         raise RuntimeError("Syntax error C")


# test_hierarchy = {
#     "Languages": ["English", "Spanish"],
#     "Health": {
#         "Doctors": ["Cardiologists", "Dermatologist"],
#         "Nutrition": ["Diet", "Supplements", "covid-19"],
#     },
#     "Pets": ["Dogs", "Cats", "Health"],
#     "Fitness": ["Workout", "Yoga", "Health"],
#     "Travel": {
#         "Food": ["Restaurants", "Cafes", "Tips & Tricks"],
#         "Health": ["Travel Insurance"],
#     },
#     "Wellness": ["Meditation", "Mindfulness", " breathing Exercises "],
#     "Technology": {
#         "General": ["Technology", "Web Development", "AI/ML", "Equipment", "C#"]
#     },
#     "Others": [],
# }
file_path = "hierarchy.json"
with open(file_path, "r", encoding="utf-8") as f:
    hierarchy = json.load(f)

hierarchy = normalize_hierarchy(hierarchy, 5)

with open("normed_hierarchy_normalized.json", "w", encoding="utf-8") as f:
    json.dump(compress_hierarchy(hierarchy), f, indent=2)
