"""
AI-Powered Criminal Network Analysis System - Main Application
"""
import os

# Load .env file if present
try:
    from dotenv import load_dotenv
    _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_backend_dir, '.env'))
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base, SessionLocal
from app.routers import auth, cases, entities, graph, ingestion, alerts, admin, reports
from app.routers import case_linkage
from app.models.models import User, DetectionRule, UserRole
from app.auth import get_password_hash

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Criminal Network Analysis System",
    description="AI-Powered Criminal Network Analysis for Law Enforcement",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(entities.router)
app.include_router(graph.router)
app.include_router(ingestion.router)
app.include_router(alerts.router)
app.include_router(admin.router)
app.include_router(reports.router)
app.include_router(case_linkage.router)


@app.get("/api/v1/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}


@app.on_event("startup")
def seed_data():
    """Seed initial data on startup."""
    db = SessionLocal()
    try:
        # Check if admin user exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            # Create default admin
            admin = User(
                username="admin",
                email="admin@lawenforcement.gov",
                full_name="System Administrator",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.SYSTEM_ADMIN,
            )
            db.add(admin)

            # Create default analyst
            analyst = User(
                username="analyst",
                email="analyst@lawenforcement.gov",
                full_name="Crime Analyst",
                hashed_password=get_password_hash("analyst123"),
                role=UserRole.CRIME_ANALYST,
            )
            db.add(analyst)

            # Create default IO
            io_user = User(
                username="officer",
                email="officer@lawenforcement.gov",
                full_name="Investigating Officer",
                hashed_password=get_password_hash("officer123"),
                role=UserRole.INVESTIGATING_OFFICER,
            )
            db.add(io_user)

            db.commit()

        # Ensure detection rules exist with lower thresholds
        from app.services.pattern_detection import ensure_detection_rules
        ensure_detection_rules(db)

        # Create a demo case if no cases exist
        from app.models.models import Case, CaseAssignment
        case_count = db.query(Case).count()
        if case_count == 0:
            demo_case = Case(
                case_number="FIR-2026-001",
                name="Operation Blacknet - Cybercrime Ring",
                description="Investigation into an organized cybercrime network operating across multiple states.",
                jurisdiction="National Capital Region",
                created_by=admin.id if admin else None,
            )
            db.add(demo_case)
            db.flush()

            # Assign all users to demo case
            for user in [admin, analyst, io_user]:
                if user:
                    db.add(CaseAssignment(user_id=user.id, case_id=demo_case.id))

            db.commit()

        db.close()
    except Exception as e:
        print(f"Seed data error: {e}")
        db.close()


# Serve uploaded files
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
