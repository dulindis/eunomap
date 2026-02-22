# Tag Resolution Engine Specification

## 1. Resolution States

TagResolveOutput.status:

- unique_match
- multiple_matches
- not_found

---

## 2. Resolution Algorithm Order

Given input label:

1. Normalize input
2. Exact match by key + parent
3. If single result → unique_match
4. If multiple → rank
5. If none → not_found

---

## 3. Ranking Rules

Priority tiers:

Tier 1: Exact key match
Tier 2: Starts-with match
Tier 3: Contains match
Tier 4: Trending score boost
Tier 5: Context note_tags boost

Scoring must be deterministic.

---

## 4. Creation Rule

If not_found:

- can_create = True
- Default parent = /others (if none specified)
- Creation must use canonical normalized form

---

## 5. Safety Rules

Never:

- Attach ambiguous match automatically
- Create raw unnormalized tag
- Bypass TagProcessor