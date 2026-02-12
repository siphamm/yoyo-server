import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import engine, Base
from app.middleware import CTKMiddleware
from app.ratelimit import limiter
from app.routes import trips, members, expenses, settlements, exchange, users

load_dotenv()

app = FastAPI(title="Splitwaiser API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Creator-Token"],
)
app.add_middleware(CTKMiddleware)

# Create tables (use Alembic in production)
Base.metadata.create_all(bind=engine)

# Routes
app.include_router(trips.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(settlements.router, prefix="/api")
app.include_router(exchange.router, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
