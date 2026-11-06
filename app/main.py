"""Circle recommendation HTTP API."""
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.recommender import recommend

app = FastAPI(title='Lean In Circle Recommender', version='1.0.0')

class Recommendation(BaseModel):
    rank: int
    circle_id: int
    name: str
    relevance_score: float
    explanation: str
    format: str
    join_policy: str

class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: list[Recommendation]


def get_db():
    with SessionLocal() as session:
        yield session

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/api/v1/users/{user_id}/recommendations', response_model=RecommendationResponse)
def get_recommendations(user_id: int, limit: int = Query(default=10, ge=1, le=40),
                        db: Session = Depends(get_db)):
    result = recommend(db, user_id, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail='User not found')
    return {'user_id': user_id, 'recommendations': result}
