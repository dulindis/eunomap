from utils import normalize

# test_strings = [
#     "COVID-19",  # hyphen should stay
#     "Hello, world!",  # punctuation removed
#     "foo_bar!",  # underscore removed
#     "multi   space",  # multiple spaces collapsed
#     "   Leading and trailing   ",  # spaces trimmed
#     "C++ programming",  # plus signs removed
#     "co--op",  # hyphen preserved
#     "end.",  # punctuation removed
#     "UPPERCASE",  # converted to lowercase
#     "numbers123",  # numbers preserved
#     "special@#$%^&*chars",  # special chars removed
#     "deep_learning",  # underscore removed
#     "hyphen-underscore_",  # hyphen preserved, underscore removed
#     "emoji 😊 test",  # emoji removed
#     "Mac&CHEESE",  # ampersand preserved
# ]

# test_strings = [
#     "COVID-19",
#     "C++ programming",
#     "Mac&CHEESE",
#     "co--op",
#     "C#",
#     "special@#$%^&*chars",
#     "foo   bar",
#     "deep_learning",
#     "AI/ml",
# ]
# for s in test_strings:
#     print(f"Original: '{s}' => Normalized: '{normalize(s)}'")
