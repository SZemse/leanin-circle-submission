# Lean In Circle Recommender

A deterministic, explainable Circle recommendation API built with **FastAPI, SQLAlchemy, and SQLite**.

## Requirements

Python 3.10+.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.seed_database
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/docs` for interactive API documentation.

Example request:

```bash
curl 'http://127.0.0.1:8000/api/v1/users/7/recommendations?limit=5'
```

Example response shape (scores are computed from the dataset):

```json
{
  "user_id": 7,
  "recommendations": [
    {
      "rank": 1,
      "circle_id": 1,
      "name": "The Elevation Circle",
      "relevance_score": 98.18,
      "explanation": "Matches your interest in leadership skills; this Circle has recent member activity.",
      "format": "in_person",
      "join_policy": "open"
    }
  ]
}
```

`GET /health` returns `{"status": "ok"}`. Nonexistent users return 404; invalid limits return 422. Query parameter `limit` accepts 1–40 (default 10).

## Tests

Seed the database, then run:

```bash
pytest -q
```

Tests cover cold start (user 42), obvious matches (7), duplicate Circles (15), full/inactive Circles (23), every user, and HTTP validation.

## Design notes

- Eligibility: exclude existing memberships, full, unlisted, and dormant Circles.
- Relevance: 70% topic match, 30% activity for members with topic interests.
- Cold start: activity, ease of participation, and information completeness; no invented interests.
- Activity: log-scaled posts and chat volume, recency, and feed engagement.
- Diversification: greedy reranking with pairwise topic/tag similarity and a maximum of two Circles per primary topic.
- Explanations: deterministic templates tied to actual scoring signals.
- **Time reference:** synthetic 30-day aggregates are evaluated relative to the latest Circle activity timestamp in the seed snapshot, not today's wall clock. This is for deterministic historical evaluation, not live production behavior.
- Geographic proximity is not scored because Circles do not provide meeting locations.

`DESIGN.md` contains the concise architectural and production tradeoffs. The returned `relevance_score` is the pre-diversification relevance score; final rank also accounts for redundancy penalties.
