"""本地管线测试：模拟 LLM 输出并使用 SQLite 内存数据库执行 SQL"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from db import executor
from db.connection import db_manager
import ai.text_to_sql as t2s
from config import config


def setup_sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT)"))
        conn.execute(text("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')"))
        conn.execute(text("INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')"))
        conn.commit()
    return engine


def main():
    print("=" * 50)
    print("本地管线测试 (模拟 LLM + SQLite)")
    print("=" * 50)

    # 准备内存 SQLite
    engine = setup_sqlite_engine()
    # 注入到 db_manager 单例以让其他模块使用
    db_manager._engine = engine

    # 模拟 LLM 生成 SQL（直接替换 text_to_sql 的 call_llm）
    def fake_call(prompt):
        return "SELECT id, name, email FROM users WHERE name = 'Alice';"

    t2s.call_llm = fake_call
    config.LLM_PROVIDER = 'local'

    schema_summary = "Table users:\n  id integer\n  name text\n  email text"
    chat_history = []
    user_query = "查找名字为 Alice 的用户"

    print("生成 SQL...")
    sql = t2s.to_sql(schema_summary, chat_history, user_query)
    print("SQL:\n", sql)

    print("执行 SQL...")
    df, err = executor.execute_sql_safe(sql)
    if err:
        print("执行出错:", err)
    else:
        print("结果:", df.to_dict(orient='records'))

    print("测试完成")


if __name__ == '__main__':
    main()
