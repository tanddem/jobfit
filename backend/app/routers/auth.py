"""Register, log in, log out, and read the signed-in account."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import AfterValidator, BaseModel, EmailStr, StringConstraints

from app.auth import (
    COOKIE_NAME,
    MAX_PASSWORD_BYTES,
    CurrentUser,
    Db,
    check_password,
    create_session,
    delete_session,
    hash_password,
)

router = APIRouter(prefix="/api/auth")


def fits_bcrypt(password):
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")
    return password


BcryptPassword = Annotated[str, AfterValidator(fits_bcrypt)]
Password = Annotated[BcryptPassword, StringConstraints(min_length=8)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RegisterRequest(BaseModel):
    email: EmailStr
    name: Name
    password: Password


class LoginRequest(BaseModel):
    email: EmailStr
    password: BcryptPassword


class Account(BaseModel):
    id: int
    email: str
    name: str


def sign_in(request, response, db, user_id):
    """Start a session for the user and set its cookie."""
    token, max_age = create_session(db, user_id)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.cookie_secure,
    )


@router.post("/register", response_model=Account, status_code=201)
def register(body: RegisterRequest, request: Request, response: Response, db: Db):
    """Create an account and sign it in. The email is unique regardless of case."""
    try:
        with db:
            user_id = db.execute(
                "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                (body.email, body.name, hash_password(body.password)),
            ).lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists.")
    sign_in(request, response, db, user_id)
    return Account(id=user_id, email=body.email, name=body.name)


@router.post("/login", response_model=Account)
def login(body: LoginRequest, request: Request, response: Response, db: Db):
    """Sign in with email and password."""
    row = db.execute("SELECT id, email, name, password_hash FROM users WHERE email = ?", (body.email,)).fetchone()
    if not check_password(body.password, row["password_hash"] if row else None):
        raise HTTPException(401, "Email or password is incorrect.")
    sign_in(request, response, db, row["id"])
    return Account(id=row["id"], email=row["email"], name=row["name"])


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Db):
    """End the current session, if any."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        delete_session(db, token)
    response.delete_cookie(COOKIE_NAME)


@router.get("/me", response_model=Account)
def me(user: CurrentUser):
    """The signed-in account."""
    return Account(id=user["id"], email=user["email"], name=user["name"])
