"""查询与会话接口。"""
from fastapi import APIRouter
from pydantic import BaseModel

import api.sessions as sessions
from api.errors import classify_error
from api.pipeline import run_query
from api.state import get_schema

router = APIRouter(prefix="/api")


class QueryRequest(BaseModel):
    session_id: str | None = None
    question: str


@router.post("/session")
def create_session():
    return {"session_id": sessions.create()}


@router.post("/query")
def query(req: QueryRequest):
    question = req.question.strip()
    if not question:
        return {"ok": False, "error_code": "empty_question", "error": "问题不能为空",
                "sql": None, "columns": [], "rows": [], "row_count": 0,
                "recommendation": None}

    session_id = req.session_id or sessions.create()
    schema_summary, _ = get_schema()
    if not schema_summary.strip():
        return {"ok": False, "error_code": "no_schema",
                "error": "数据库表结构尚未就绪，系统正在连接数据库，请稍后重试",
                "sql": None, "columns": [], "rows": [], "row_count": 0,
                "recommendation": None}

    history = sessions.get_history(session_id)
    session_llm = sessions.get(session_id)["llm"]

    try:
        result = run_query(schema_summary, history, question, session_llm)
    except Exception as e:
        from core.secrets import sanitize_error
        detail = sanitize_error(str(e))
        result = {"sql": None, "error": detail, "columns": [],
                  "rows": [], "row_count": 0, "recommendation": None}

    error = result.get("error")
    result["ok"] = error is None
    result["error_code"] = classify_error(error) if error else None
    result["session_id"] = session_id

    # 写入会话上下文（多轮 prompt 需要；前端不展示聊天气泡）
    sessions.append_message(session_id, "user", question)
    if result.get("sql"):
        content = (f"返回 {result['row_count']} 行数据。"
                   if not error else f"查询失败：{error}")
        sessions.append_message(session_id, "assistant", content, sql=result["sql"])

    return result
