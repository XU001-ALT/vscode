import pandas as pd


def execute_sql(engine, sql_text):
    try:
        df = pd.read_sql(sql_text, engine)
        return df, None
    except Exception as e:
        return None, str(e)
