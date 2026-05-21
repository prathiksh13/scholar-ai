from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import FIREBASE_CREDENTIALS_PATH, FIREBASE_PROJECT_ID, SKIP_AUTH

security = HTTPBearer(auto_error=False)

_firebase_app = None


def _init_firebase():
    global _firebase_app
    if _firebase_app or SKIP_AUTH:
        return
    if not FIREBASE_PROJECT_ID:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials

        if FIREBASE_CREDENTIALS_PATH:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            _firebase_app = firebase_admin.initialize_app()
    except Exception:
        pass


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if SKIP_AUTH:
        return {"uid": "demo", "email": "demo@scholarai.local"}

    _init_firebase()

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = credentials.credentials

    try:
        from firebase_admin import auth as firebase_auth

        decoded = firebase_auth.verify_id_token(token)
        return {"uid": decoded.get("uid"), "email": decoded.get("email")}
    except Exception:
        if SKIP_AUTH:
            return {"uid": "demo", "email": "demo@scholarai.local"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
