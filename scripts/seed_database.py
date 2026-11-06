"""Run from repository root: python -m scripts.seed_database"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from sqlalchemy import delete, func, select
from app.database import Base, SessionLocal, engine
from app.models import Activity, Circle, CircleTag, Membership, Topic, User, UserInterest

DATA = Path(__file__).resolve().parents[1] / 'data'

def read(name):
    return json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))

def dt(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))

def seed():
    topics, users, circles = read('topics'), read('users'), read('circles')
    memberships, activity = read('memberships'), read('activity')
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as session:
        # Idempotent import. Delete children before parents to preserve foreign keys.
        for model in (Activity, Membership, CircleTag, UserInterest, Circle, User, Topic):
            session.execute(delete(model))
        session.add_all(Topic(**x) for x in topics)
        session.flush()
        session.add_all(User(**{**{k:v for k,v in x.items() if k!='topic_interests'}, 'joined_at':dt(x['joined_at'])}) for x in users)
        session.add_all(Circle(**{**{k:v for k,v in x.items() if k not in ('topic','tags')},
                        'topic_slug':x['topic'],
                        'created_at':dt(x['created_at']), 'last_activity_at':dt(x['last_activity_at'])}) for x in circles)
        session.flush()
        session.add_all(UserInterest(user_id=x['id'],topic_slug=t)
                        for x in users for t in set(x['topic_interests']))
        session.add_all(CircleTag(circle_id=x['id'],tag=t)
                        for x in circles for t in set(x['tags']))
        session.add_all(Membership(**{**x,'joined_at':dt(x['joined_at'])}) for x in memberships)
        session.add_all(Activity(**{**x,'created_at':dt(x['created_at'])}) for x in activity)
    with SessionLocal() as session:
        tables = {name: session.scalar(select(func.count()).select_from(model)) for name,model in
                  [('topics',Topic),('users',User),('circles',Circle),('memberships',Membership),('activity',Activity),('user_interests',UserInterest),('circle_tags',CircleTag)]}
        expected_counts = {
            'topics': len(topics),
            'users': len(users),
            'circles': len(circles),
            'memberships': len(memberships),
            'activity': len(activity),
        }
        for name, expected in expected_counts.items():
            assert tables[name] == expected, f'{name}: imported {tables[name]}, expected {expected}'
        actual_members = dict(session.execute(select(Membership.circle_id,func.count()).group_by(Membership.circle_id)).all())
        for c in circles:
            assert actual_members.get(c['id'],0)==c['member_count'],f"Circle {c['id']} count mismatch"
        assert session.scalar(select(func.count()).select_from(CircleTag)) == sum(len(set(c['tags'])) for c in circles)
    print('Import validated:',tables)

if __name__ == '__main__':
    seed()
