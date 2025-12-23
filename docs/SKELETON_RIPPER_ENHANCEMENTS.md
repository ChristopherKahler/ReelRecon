# Skeleton Ripper - Future Enhancements

Captured ideas for future development of the Content Skeleton Ripper feature.

---

## 1. Statistical Confidence Scoring

**Priority:** High
**Captured:** 2025-12-22

### Problem
Currently, skeleton templates are presented without indication of how statistically validated they are. Users who think in numbers want to see data-backed confidence.

### Proposed Solution
Utilize video stats (views, likes, comments, engagement rate) from fetched videos to generate confidence scores for each template.

**Data available per video:**
- Views
- Likes
- Comments
- Engagement rate (likes + comments / views)
- Video duration

**Possible calculations:**
```
Template Confidence Score =
  (frequency_in_dataset × 0.4) +
  (avg_views_of_videos_using_pattern × 0.3) +
  (avg_engagement_of_videos_using_pattern × 0.3)
```

**Enhanced output format:**
```
Hook Skeleton #1: [Curiosity Hook]
Template: "Here's how I [process] using [tool]"
Frequency: 12/15 videos (80%)
Avg Views: 45,000 (2.3x dataset average)
Avg Engagement: 4.2%
Confidence Score: 87/100 ← HIGH CONFIDENCE
```

### Implementation Notes
- Stats are already captured in skeleton extraction (views, likes stored per skeleton)
- Need to add aggregation logic in `aggregator.py` to compute per-pattern stats
- Update synthesis prompt to include stats context
- Consider weighting by recency (newer videos may indicate current algorithm preference)

### User Benefit
- Numbers-oriented users can quickly identify most validated patterns
- Separates "this worked once" from "this consistently performs"
- Enables data-driven template selection

---

## 2. [Future Enhancement Placeholder]

*Add new enhancement ideas below*

---

## Enhancement Request Format

When adding new enhancements, use this template:

```markdown
## N. Enhancement Title

**Priority:** High/Medium/Low
**Captured:** YYYY-MM-DD

### Problem
[What limitation or opportunity does this address?]

### Proposed Solution
[How would this work?]

### Implementation Notes
[Technical considerations]

### User Benefit
[Why does this matter?]
```
