import psycopg2

try:
    conn = psycopg2.connect(
        host="ep-little-cherry-e33eeo1e.database.westus.azuredatabricks.net",
        port=5432,
        dbname="databricks_postgres",
        user="app_admin",
        password="tE$T_pwd_some_%%11_sft",
        sslmode="require"
    )

    print("\nSUCCESS: Connected to Lakebase!\n")

    cur = conn.cursor()

    cur.execute("SELECT current_timestamp;")

    result = cur.fetchone()

    print("Database Time:", result)

    cur.close()
    conn.close()

except Exception as e:

    print("\nCONNECTION FAILED\n")
    print(type(e))
    print(e)
