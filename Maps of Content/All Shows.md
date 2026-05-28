# All Shows

```dataview
TABLE status, show_id, clip_count, curated_count, board_url AS "Board"
FROM "Shows"
WHERE type = "show"
SORT file.name
```
