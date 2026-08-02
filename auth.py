"""Email/password login for the Construction Work Journal.

Users and password hashes live in Streamlit secrets (not in Git):

    [auth]
    enabled = true

    [auth.credentials]
    "you@example.com" = "$2b$12$...."   # bcrypt hash

    [auth.names]
    "you@example.com" = "Your Name"

Generate a hash locally:
    python3 hash_password.py
"""

from __future__ import annotations

from typing import Any

import bcrypt
import streamlit as st


def auth_enabled() -> bool:
    """If secrets are missing or auth.enabled is false, treat as open (local only)."""
    try:
        auth = st.secrets.get("auth", {})
    except Exception:
        return False
    if not auth:
        return False
    # Default to enabled when [auth] exists
    return bool(auth.get("enabled", True))


def _credentials() -> dict[str, str]:
    """Map email (lowercase) -> bcrypt password hash."""
    try:
        creds = st.secrets["auth"]["credentials"]
    except Exception:
        return {}
    # Streamlit AttrDict / dict-like
    out: dict[str, str] = {}
    for key, value in creds.items():
        out[str(key).strip().lower()] = str(value).strip()
    return out


def _display_names() -> dict[str, str]:
    try:
        names = st.secrets["auth"]["names"]
    except Exception:
        return {}
    return {str(k).strip().lower(): str(v) for k, v in names.items()}


def list_allowed_emails() -> list[str]:
    return sorted(_credentials().keys())


def verify_password(plain: str, password_hash: str) -> bool:
    if not plain or not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def is_logged_in() -> bool:
    return bool(st.session_state.get("auth_user"))


def current_user() -> dict[str, Any] | None:
    return st.session_state.get("auth_user")


def logout() -> None:
    for key in ("auth_user",):
        if key in st.session_state:
            del st.session_state[key]


def try_login(email: str, password: str) -> tuple[bool, str]:
    email_norm = (email or "").strip().lower()
    password = password or ""
    if not email_norm or not password:
        return False, "Enter email and password."

    creds = _credentials()
    if not creds:
        return False, "No users configured. Add accounts in Streamlit Secrets."

    password_hash = creds.get(email_norm)
    if not password_hash:
        return False, "Invalid email or password."

    if not verify_password(password, password_hash):
        return False, "Invalid email or password."

    names = _display_names()
    st.session_state["auth_user"] = {
        "email": email_norm,
        "name": names.get(email_norm, email_norm.split("@")[0]),
    }
    return True, "OK"


def require_login() -> bool:
    """
    Gate the app. Returns True if the user may continue.
    Shows a login form when not authenticated.
    """
    if not auth_enabled():
        # No secrets configured — allow local use without login
        return True

    if is_logged_in():
        return True

    st.title("🏗️ Construction Work Journal")
    st.caption("Sign in to continue. Access is limited to invited people.")

    creds = _credentials()
    if not creds:
        st.error(
            "Login is enabled but **no users** are configured yet.\n\n"
            "In Streamlit Cloud: **Manage app → Settings → Secrets**, "
            "add `[auth.credentials]` emails and bcrypt password hashes. "
            "See `secrets.example.toml` in the repo."
        )
        return False

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="you@company.com", autocomplete="username")
        password = st.text_input(
            "Password",
            type="password",
            placeholder="••••••••",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if submitted:
        ok, message = try_login(email, password)
        if ok:
            st.rerun()
        else:
            st.error(message)

    st.info("Contact your admin if you need an account.")
    return False


def render_user_sidebar() -> None:
    """Show who is signed in + logout (when auth is on)."""
    if not auth_enabled():
        st.sidebar.caption("Login not configured (open access).")
        return

    user = current_user()
    if not user:
        return

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Signed in as**  \n{user['name']}  \n`{user['email']}`")
    if st.sidebar.button("Sign out", use_container_width=True):
        logout()
        st.rerun()
