"""Deterministic, explainable rankings from the seeded community snapshot."""
import math
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models import Activity, Circle, User, Membership

# Heuristic parameters are explicit so they can be reviewed and calibrated.
MAX_INACTIVE_DAYS = 90
POST_VOLUME_NORMALIZER = 20
CHAT_VOLUME_NORMALIZER = 215
RECENCY_DECAY_DAYS = 21
DIVERSITY_PENALTY_WEIGHT = 0.24
MAX_CIRCLES_PER_PRIMARY_TOPIC = 2


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def clamp(value):
    return max(0.0, min(1.0, value))


def circle_tags(circle):
    return {tag.tag for tag in circle.tags}


def eligible(circle, joined, snapshot):
    age = (snapshot - aware(circle.last_activity_at)).total_seconds() / 86400
    return (circle.id not in joined and circle.access == 'public'
            and (circle.max_members is None or circle.member_count < circle.max_members)
            and age <= MAX_INACTIVE_DAYS
            and not (circle.feed_posts_30d == 0 and circle.chat_messages_30d <= 3))


def activity_score(circle, engagement, snapshot):
    posts = clamp(math.log1p(circle.feed_posts_30d) / math.log1p(POST_VOLUME_NORMALIZER))
    chat = clamp(math.log1p(circle.chat_messages_30d) / math.log1p(CHAT_VOLUME_NORMALIZER))
    days = max(0, (snapshot - aware(circle.last_activity_at)).total_seconds() / 86400)
    recency = math.exp(-days / RECENCY_DECAY_DAYS)
    values = engagement.get(circle.id, [])
    interactions = clamp((sum(values) / len(values)) / 22) if values else 0.0
    return .35 * posts + .25 * chat + .25 * recency + .15 * interactions


def topic_score(interests, circle):
    if circle.topic_slug in interests:
        return 1.0, circle.topic_slug, 'primary'
    matching = sorted(interests & circle_tags(circle))
    if matching:
        return .65, matching[0], 'tag'
    return 0.0, None, None


def similarity(a, b):
    a_tags, b_tags = circle_tags(a), circle_tags(b)
    if a.topic_slug and a.topic_slug == b.topic_slug:
        return .85 + .15 * len(a_tags & b_tags) / max(1, len(a_tags | b_tags))
    aa = a_tags | ({a.topic_slug} if a.topic_slug else set())
    bb = b_tags | ({b.topic_slug} if b.topic_slug else set())
    return .25 * len(aa & bb) / max(1, len(aa | bb))


def explain(circle, matched, match_type, activity, cold_start, labels):
    if matched:
        label = labels.get(matched, matched.replace('-', ' ')).lower()
        if match_type == 'primary':
            return f'Matches your interest in {label}; this Circle has recent member activity.'
        return f'Explores {label}, one of your interests, and has recent member activity.'
    if cold_start:
        topic = labels.get(circle.topic_slug, '').lower() if circle.topic_slug else ''
        if topic:
            return f'An active community focused on {topic} that you can explore.'
        return 'A community with recent discussions that you can explore.'
    if activity >= .6:
        return 'An active community with recent conversations you may find useful.'
    return 'A community you may want to explore.'


def recommend(session: Session, user_id: int, limit: int = 10, reference_time=None):
    user = session.scalar(select(User).options(selectinload(User.interests)).where(User.id == user_id))
    if user is None:
        return None
    circles = list(session.scalars(select(Circle).options(selectinload(Circle.tags), selectinload(Circle.topic)).order_by(Circle.id)))
    if not circles:
        return []
    joined = set(session.scalars(select(Membership.circle_id).where(Membership.user_id == user_id)))
    snapshot = aware(reference_time) if reference_time else max(aware(c.last_activity_at) for c in circles)
    posts = session.scalars(select(Activity)).all()
    engagement = defaultdict(list)
    for post in posts:
        age = (snapshot - aware(post.created_at)).total_seconds() / 86400
        if 0 <= age <= 30:
            engagement[post.circle_id].append(post.reaction_count + 2 * post.comment_count + post.save_count)
    interests = {interest.topic_slug for interest in user.interests}
    labels = {c.topic_slug: c.topic.label for c in circles if c.topic is not None}
    cold_start = not interests
    remaining = []
    for circle in circles:
        if not eligible(circle, joined, snapshot):
            continue
        a = activity_score(circle, engagement, snapshot)
        t, matched, match_type = topic_score(interests, circle)
        if cold_start:
            accessibility = {'virtual': 1.0, 'hybrid': .8, 'in_person': .5}[circle.format]
            entry = 1.0 if circle.join_policy == 'open' else .8
            completeness = 1.0 if circle.topic_slug or circle.description or circle.tags else 0.0
            base = .70 * a + .15 * (.7 * accessibility + .3 * entry) + .15 * completeness
        else:
            base = .70 * t + .30 * a
        remaining.append({'circle': circle, 'base': base, 'activity': a,
                          'matched': matched, 'match_type': match_type})
    selected = []
    while remaining and len(selected) < limit:
        available = [item for item in remaining if not item['circle'].topic_slug or sum(
            s['circle'].topic_slug == item['circle'].topic_slug for s in selected) < MAX_CIRCLES_PER_PRIMARY_TOPIC]
        if not available:
            break
        for item in available:
            penalty = DIVERSITY_PENALTY_WEIGHT * max(
                (similarity(item['circle'], s['circle']) for s in selected), default=0.0
            )
            item['adjusted'] = item['base'] - penalty
        best = max(available, key=lambda x: (x['adjusted'], x['base'], -x['circle'].id))
        selected.append(best)
        remaining.remove(best)
    return [dict(rank=i, circle_id=x['circle'].id, name=x['circle'].name,
                 relevance_score=round(100*x['base'], 2),
                 explanation=explain(x['circle'], x['matched'], x['match_type'], x['activity'], cold_start, labels),
                 format=x['circle'].format, join_policy=x['circle'].join_policy)
            for i, x in enumerate(selected, 1)]
