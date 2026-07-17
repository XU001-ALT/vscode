from sqlalchemy import create_engine


def make_engine(host, port, dbname, user, password):
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    engine = create_engine(url, pool_pre_ping=True)
    return engine
