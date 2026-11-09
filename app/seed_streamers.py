from app.database import Base, engine, SessionLocal
from app.models.streamer import Streamer, StreamerAccount

INITIAL_STREAMERS = [
    {"name": "Kai Cenat", "slug": "kai-cenat", "priority": 10},
    {"name": "IShowSpeed", "slug": "ishowspeed", "priority": 10},
    {"name": "Adin Ross", "slug": "adin-ross", "priority": 9},
    {"name": "xQc", "slug": "xqc", "priority": 9},
    {"name": "Jynxzi", "slug": "jynxzi", "priority": 9},
    {"name": "YourRAGE", "slug": "yourrage", "priority": 9},
    {"name": "Cinna", "slug": "cinna", "priority": 8},
    {"name": "Lacy", "slug": "lacy", "priority": 8},
    {"name": "Marlon", "slug": "marlon", "priority": 8},
    {"name": "JasonTheWeen", "slug": "jasontheween", "priority": 8},
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        added = 0

        for item in INITIAL_STREAMERS:
            exists = db.query(Streamer).filter(
                Streamer.slug == item["slug"]
            ).first()

            if exists:
                continue

            db.add(Streamer(**item))
            added += 1

        db.commit()

        total = db.query(Streamer).count()
        print(f"New streamers added: {added}")
        print(f"Total streamers in database: {total}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()