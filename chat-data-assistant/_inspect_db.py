from db.connection import make_engine
from sqlalchemy import text

engine = make_engine(
    host='47.121.180.232',
    port=18012,
    dbname='digital-hydrogen',
    user='read_only',
    password='read-only'
)
with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    ))
    tables = [row[0] for row in result]
    print(f"Total tables: {len(tables)}")

    for t in tables:
        result2 = conn.execute(text(
            f"SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_name = '{t}' AND table_schema = 'public' ORDER BY ordinal_position"
        ))
        cols = [(row[0], row[1]) for row in result2]
        col_str = ", ".join(f"{c[0]}({c[1]})" for c in cols[:8])
        if len(cols) > 8:
            col_str += f", ... +{len(cols)-8} more"
        print(f"  {t}: {col_str}")
