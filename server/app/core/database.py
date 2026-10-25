"""Database access for request handlers, background jobs and scripts: MongoDB unit-of-work sessions.

``get_db`` is the request dependency and ``session_scope`` the context manager used outside requests (background
jobs, streaming responses that outlive the request). See app.core.mongo for how a Session works.
"""

from app.core.mongo import Session, get_mongo_db, init_mongo, mongo_session, retry_transient

get_db = get_mongo_db
session_scope = mongo_session

__all__ = ["Session", "get_db", "init_mongo", "retry_transient", "session_scope"]
