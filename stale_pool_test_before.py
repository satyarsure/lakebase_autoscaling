from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
import time

# ======================================================
# CONNECTION INFO
# ======================================================

USERNAME = "app_admin"

PASSWORD = "tE$T_pwd_some_%%11_sft"

HOST = "ep-little-cherry-e33eeo1e.database.westus.azuredatabricks.net"

DATABASE = "databricks_postgres"

# ======================================================

connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username=USERNAME,
    password=PASSWORD,
    host=HOST,
    port=5432,
    database=DATABASE,
    query={
        "sslmode": "require"
    }
)

print("\nCreating SQLAlchemy engine...\n")

engine = create_engine(
    connection_url,

    # connection pool settings
    pool_size=5,
    max_overflow=2,

    # intentionally LONGER than Lakebase scale-to-zero timeout
    pool_recycle=3600,

    # DISABLED initially to reproduce stale connection issue
    pool_pre_ping=False,

    echo=True
)

print("Engine created successfully.\n")

while True:

    print("\n==============================")
    print("Executing query...")
    print("==============================\n")

    try:

        start = time.time()

        with engine.connect() as conn:

            result = conn.execute(
                text("SELECT current_timestamp")
            )

            ts = result.scalar()

        elapsed = round(time.time() - start, 2)

        print("\nSUCCESS")
        print("Timestamp:", ts)
        print("Elapsed:", elapsed, "seconds")

    except Exception as e:

        print("\nERROR OCCURRED")
        print(type(e))
        print(e)

    input("\nPress ENTER to test again...")
