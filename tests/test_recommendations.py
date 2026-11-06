from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.services.recommender import recommend

client = TestClient(app)

def ids(user_id, limit=10):
    with SessionLocal() as db:
        return [r['circle_id'] for r in recommend(db,user_id,limit)]

def test_obvious_matches():
    top = ids(7, 5)
    assert 5 in top[:3] and 6 in top[:3]

def test_duplicate_diversity():
    top = ids(15)
    assert sum(i in top for i in (10,11,12)) <= 2
    assert 13 in top[:5]

def test_full_inactive():
    top = ids(23)
    assert top[0] == 22
    assert 20 not in top and 21 not in top

def test_cold_start():
    top = ids(42)
    assert len(top) == 10 and len(set(top)) == 10

def test_every_user_has_results_and_no_ineligible():
    from sqlalchemy import select
    from app.models import Circle, Membership
    with SessionLocal() as db:
        cs = {c.id:c for c in db.scalars(select(Circle))}
        pairs = set(db.execute(select(Membership.user_id,Membership.circle_id)).all())
        for uid in range(1,101):
            result = recommend(db,uid)
            assert result,uid
            assert len({r['circle_id'] for r in result})==len(result)
            assert [r['rank'] for r in result] == list(range(1,len(result)+1))
            for r in result:
                c = cs[r['circle_id']]
                assert (uid,c.id) not in pairs
                assert c.access == 'public'
                assert c.max_members is None or c.member_count < c.max_members
                assert r['explanation']

def test_api():
    response=client.get('/api/v1/users/7/recommendations?limit=3')
    assert response.status_code==200
    data=response.json()
    assert data['user_id']==7 and len(data['recommendations'])==3
    assert all('explanation' in r and 'relevance_score' in r for r in data['recommendations'])

def test_invalid_requests():
    assert client.get('/api/v1/users/9999/recommendations').status_code==404
    assert client.get('/api/v1/users/7/recommendations?limit=0').status_code==422
    assert client.get('/api/v1/users/7/recommendations?limit=41').status_code==422
    assert client.get('/api/v1/users/abc/recommendations').status_code==422
