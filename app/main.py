import os
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import (
    FastAPI,
    Request,
    Form,
    File,
    UploadFile,
    HTTPException,
)

from pydantic import ValidationError

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from jose import JWTError, jwt

from app.services.auth_service import (
    register_user,
    authenticate_user,
    get_user_by_email,
    user_public,
)

from app.services.recommendation_service import (
    generate_home_recommendations,
    generate_party_recommendations,
    generate_jewelry_recommendations,
)

from app.services.history_service import (
    save_history,
    get_history,
)

from app.models.schemas import (
    HomePlannerInput,
    PartyPlannerInput,
    JewelryPlannerInput,
)


# ============================================================
# BASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="PocketSmart AI",
    version="1.0.0",
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SESSION CONFIGURATION
# ============================================================

SESSION_SECRET = os.getenv(
    "SESSION_SECRET",
    "change-this-secret",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=60 * 60 * 24 * 7,
)


# ============================================================
# JWT CONFIGURATION
# ============================================================

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    SESSION_SECRET,
)

JWT_ALGORITHM = "HS256"

try:
    JWT_EXPIRE_MINUTES = int(
        os.getenv(
            "JWT_EXPIRE_MINUTES",
            "0",
        )
    )
except ValueError:
    JWT_EXPIRE_MINUTES = 0


# ============================================================
# UPLOAD CONFIGURATION
# ============================================================

UPLOAD_DIR = (
    BASE_DIR
    / "static"
    / "uploads"
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=BASE_DIR / "static"
    ),
    name="static",
)

app.mount(
    "/uploads",
    StaticFiles(
        directory=UPLOAD_DIR
    ),
    name="uploads",
)


# ============================================================
# JINJA TEMPLATES
# ============================================================

templates = Jinja2Templates(
    directory=BASE_DIR / "templates"
)


# ============================================================
# AUTHENTICATION HELPERS
# ============================================================

def current_user(request: Request):
    """
    Return the currently logged-in user
    from the browser session.
    """

    email = request.session.get(
        "user_email"
    )

    if not email:
        return None

    return get_user_by_email(email)


def require_user(request: Request):
    """
    Require an authenticated browser session.
    """

    user = current_user(request)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    return user


# ============================================================
# JWT HELPERS
# ============================================================

def create_access_token(email: str) -> str:
    """
    Create a JWT access token.

    JWT_EXPIRE_MINUTES = 0
    means the token has no expiration claim.

    JWT_EXPIRE_MINUTES > 0
    means the token expires after the
    configured number of minutes.
    """

    payload = {
        "sub": email,
    }

    if JWT_EXPIRE_MINUTES > 0:

        expire = (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=JWT_EXPIRE_MINUTES
            )
        )

        payload["exp"] = expire

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def get_email_from_token(
    token: str,
) -> str | None:
    """
    Decode a JWT token and return
    the user's email.
    """

    try:

        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        email = payload.get("sub")

        if not email:
            return None

        return str(email).strip().lower()

    except JWTError:

        return None


# ============================================================
# HOME
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
async def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "user": current_user(request),
        },
    )


# ============================================================
# TESTIMONIALS
# ============================================================

@app.get(
    "/testimonials",
    response_class=HTMLResponse,
)
async def testimonials(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="testimonials.html",
        context={
            "request": request,
            "user": current_user(request),
        },
    )


# ============================================================
# REGISTER PAGE
# ============================================================

@app.get(
    "/register",
    response_class=HTMLResponse,
)
async def register_page(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "request": request,
            "user": current_user(request),
        },
    )


# ============================================================
# REGISTER USER
# ============================================================

@app.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):

    clean_name = name.strip()
    clean_email = email.strip().lower()

    ok, message = register_user(
        clean_name,
        clean_email,
        password,
    )

    if not ok:

        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "request": request,
                "error": message,
                "user": current_user(request),
            },
            status_code=400,
        )

    request.session[
        "user_email"
    ] = clean_email

    return RedirectResponse(
        "/dashboard",
        status_code=303,
    )


# ============================================================
# LOGIN PAGE
# ============================================================

@app.get(
    "/login",
    response_class=HTMLResponse,
)
async def login_page(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "user": current_user(request),
        },
    )


# ============================================================
# LOGIN
# ============================================================

@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):

    clean_email = email.strip().lower()

    user = authenticate_user(
        clean_email,
        password,
    )

    if not user:

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "error": "Invalid email or password.",
                "user": current_user(request),
            },
            status_code=401,
        )

    request.session[
        "user_email"
    ] = user["email"]

    return RedirectResponse(
        "/dashboard",
        status_code=303,
    )


# ============================================================
# LOGOUT
# ============================================================

@app.get("/logout")
async def logout(
    request: Request,
):

    request.session.clear()

    return RedirectResponse(
        "/login",
        status_code=303,
    )


# ============================================================
# TOKEN API
# ============================================================

@app.post("/token")
async def token(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):

    clean_email = email.strip().lower()

    user = authenticate_user(
        clean_email,
        password,
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    access_token = create_access_token(
        user["email"]
    )

    request.session[
        "user_email"
    ] = user["email"]

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": (
            None
            if JWT_EXPIRE_MINUTES == 0
            else JWT_EXPIRE_MINUTES * 60
        ),
        "user": user_public(user),
    }


# ============================================================
# SESSION INFO API
# ============================================================

@app.get("/session-info")
async def session_info(
    request: Request,
):

    user = current_user(request)

    return {
        "logged_in": bool(user),
        "session_active": bool(user),
        "user": (
            user_public(user)
            if user
            else None
        ),
    }


# ============================================================
# SESSION DATA API
# ============================================================

@app.get("/session-data")
async def session_data(
    request: Request,
):

    user = require_user(request)

    history = get_history(
        user["email"]
    )

    return {
        "user": user_public(user),
        "history_count": len(history),
        "history": history,
    }


# ============================================================
# DASHBOARD
# ============================================================

@app.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def dashboard(
    request: Request,
):

    user = require_user(request)

    history = get_history(
        user["email"]
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "user": user,
            "history": history[-6:][::-1],
        },
    )


# ============================================================
# HOME PLANNER PAGE
# ============================================================

@app.get(
    "/home-planner",
    response_class=HTMLResponse,
)
async def home_planner(
    request: Request,
):

    user = require_user(request)

    return templates.TemplateResponse(
        request=request,
        name="home_planner.html",
        context={
            "request": request,
            "user": user,
        },
    )


# ============================================================
# PARTY PLANNER PAGE
# ============================================================

@app.get(
    "/party-planner",
    response_class=HTMLResponse,
)
async def party_planner(
    request: Request,
):

    user = require_user(request)

    return templates.TemplateResponse(
        request=request,
        name="party_planner.html",
        context={
            "request": request,
            "user": user,
        },
    )


# ============================================================
# JEWELRY PLANNER PAGE
# ============================================================

@app.get(
    "/jewelry-planner",
    response_class=HTMLResponse,
)
async def jewelry_planner(
    request: Request,
):

    user = require_user(request)

    return templates.TemplateResponse(
        request=request,
        name="jewelry_planner.html",
        context={
            "request": request,
            "user": user,
        },
    )


# ============================================================
# HOME RECOMMENDATIONS
# ============================================================

@app.post("/generate-home")
async def generate_home(
    request: Request,
):

    user = require_user(request)

    form = await request.form()

    try:

        data = HomePlannerInput(
            budget=float(
                form.get(
                    "budget",
                    0,
                )
            ),
            room_type=str(
                form.get(
                    "room_type",
                    "",
                )
            ),
            quantity=int(
                form.get(
                    "quantity",
                    1,
                )
            ),
            style=str(
                form.get(
                    "style",
                    "",
                )
            ),
            needs=str(
                form.get(
                    "needs",
                    "",
                )
            ),
        )

    except (
        ValueError,
        TypeError,
    ):

        raise HTTPException(
            status_code=422,
            detail=(
                "Please enter valid values "
                "for all Home Planner fields."
            ),
        )

    except ValidationError as exc:

        raise HTTPException(
            status_code=422,
            detail=exc.errors(),
        )

    result = (
        await generate_home_recommendations(
            data
        )
    )

    save_history(
        user["email"],
        "Home",
        data.model_dump(),
        result,
    )

    return templates.TemplateResponse(
        request=request,
        name="recommendations.html",
        context={
            "request": request,
            "user": user,
            "category": "Home",
            "result": result,
            "input_data": data.model_dump(),
        },
    )


# ============================================================
# PARTY RECOMMENDATIONS
# ============================================================

@app.post("/generate-party")
async def generate_party(
    request: Request,
):

    user = require_user(request)

    form = await request.form()

    try:

        data = PartyPlannerInput(
            budget=float(
                form.get(
                    "budget",
                    0,
                )
            ),
            guest_count=int(
                form.get(
                    "guest_count",
                    1,
                )
            ),
            event_type=str(
                form.get(
                    "event_type",
                    "",
                )
            ),
            venue=str(
                form.get(
                    "venue",
                    "",
                )
            ),
            preferences=str(
                form.get(
                    "preferences",
                    "",
                )
            ),
        )

    except (
        ValueError,
        TypeError,
    ):

        raise HTTPException(
            status_code=422,
            detail=(
                "Please enter valid values "
                "for all Party Planner fields."
            ),
        )

    except ValidationError as exc:

        raise HTTPException(
            status_code=422,
            detail=exc.errors(),
        )

    result = (
        await generate_party_recommendations(
            data
        )
    )

    save_history(
        user["email"],
        "Party",
        data.model_dump(),
        result,
    )

    return templates.TemplateResponse(
        request=request,
        name="recommendations.html",
        context={
            "request": request,
            "user": user,
            "category": "Party",
            "result": result,
            "input_data": data.model_dump(),
        },
    )


# ============================================================
# JEWELRY RECOMMENDATIONS
# ============================================================

@app.post("/generate-jewelry")
async def generate_jewelry(
    request: Request,
    budget: float = Form(...),
    occasion: str = Form(...),
    style: str = Form(...),
    outfit_notes: str = Form(""),
    outfit_image: UploadFile | None = File(None),
):

    user = require_user(request)

    image_path: Path | None = None

    # --------------------------------------------------------
    # CLEAN TEXT INPUTS
    # --------------------------------------------------------

    clean_occasion = occasion.strip()
    clean_style = style.strip()
    clean_outfit_notes = outfit_notes.strip()

    # --------------------------------------------------------
    # OPTIONAL OUTFIT IMAGE
    # --------------------------------------------------------

    if (
        outfit_image is not None
        and outfit_image.filename
    ):

        original_name = Path(
            outfit_image.filename
        ).name

        suffix = Path(
            original_name
        ).suffix.lower()

        # ----------------------------------------------------
        # EXTENSION VALIDATION
        # ----------------------------------------------------

        if (
            suffix
            not in ALLOWED_IMAGE_EXTENSIONS
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Only JPG, JPEG, PNG and WEBP "
                    "images are supported."
                ),
            )

        # ----------------------------------------------------
        # CONTENT TYPE VALIDATION
        # ----------------------------------------------------

        content_type = (
            outfit_image.content_type
            or ""
        ).lower()

        if (
            content_type
            and content_type
            not in ALLOWED_IMAGE_CONTENT_TYPES
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid image content type. "
                    "Please upload a JPG, PNG or WEBP image."
                ),
            )

        # ----------------------------------------------------
        # READ IMAGE BYTES
        # ----------------------------------------------------

        image_bytes = (
            await outfit_image.read()
        )

        if not image_bytes:

            raise HTTPException(
                status_code=400,
                detail="The uploaded image is empty.",
            )

        # ----------------------------------------------------
        # IMAGE SIZE VALIDATION
        # ----------------------------------------------------

        if len(image_bytes) > MAX_IMAGE_SIZE:

            raise HTTPException(
                status_code=413,
                detail=(
                    "Image size must be 5 MB or less."
                ),
            )

        # ----------------------------------------------------
        # UNIQUE SAFE FILENAME
        # ----------------------------------------------------

        safe_original_name = (
            original_name
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )

        unique_name = (
            f"{user['id']}_"
            f"{uuid.uuid4().hex}_"
            f"{safe_original_name}"
        )

        image_path = (
            UPLOAD_DIR
            / unique_name
        )

        # ----------------------------------------------------
        # SAVE IMAGE
        # ----------------------------------------------------

        try:

            image_path.write_bytes(
                image_bytes
            )

        except OSError as exc:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Unable to save uploaded image: {exc}"
                ),
            )

    # --------------------------------------------------------
    # VALIDATE JEWELRY INPUT
    # --------------------------------------------------------

    try:

        data = JewelryPlannerInput(
            budget=budget,
            occasion=clean_occasion,
            style=clean_style,
            outfit_notes=clean_outfit_notes,
            image_path=(
                str(image_path)
                if image_path
                else None
            ),
        )

    except ValidationError as exc:

        if (
            image_path
            and image_path.exists()
        ):

            image_path.unlink()

        raise HTTPException(
            status_code=422,
            detail=exc.errors(),
        )

    # --------------------------------------------------------
    # GENERATE JEWELRY RECOMMENDATIONS
    # --------------------------------------------------------

    try:

        result = (
            await generate_jewelry_recommendations(
                data
            )
        )

    except Exception:

        # ----------------------------------------------
        # Remove temporary uploaded image if generation
        # fails unexpectedly.
        # ----------------------------------------------

        if (
            image_path
            and image_path.exists()
        ):

            image_path.unlink()

        raise

    # --------------------------------------------------------
    # SAVE HISTORY
    # --------------------------------------------------------

    history_data = data.model_dump(
        exclude={
            "image_path"
        }
    )

    save_history(
        user["email"],
        "Jewelry",
        history_data,
        result,
    )

    # --------------------------------------------------------
    # SHOW RESULT
    # --------------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="recommendations.html",
        context={
            "request": request,
            "user": user,
            "category": "Jewelry",
            "result": result,
            "input_data": history_data,
        },
    )


# ============================================================
# RECOMMENDATION DETAILS API
# ============================================================

@app.get(
    "/recommendations-details"
)
async def recommendation_details(
    request: Request,
    recommendation_id: str | None = None,
):

    user = require_user(request)

    history = get_history(
        user["email"]
    )

    if not history:

        return {
            "found": False,
            "message": (
                "No recommendation "
                "history found."
            ),
            "recommendation": None,
        }

    if recommendation_id:

        for item in history:

            item_id = str(
                item.get(
                    "id",
                    "",
                )
            )

            if (
                item_id
                == str(recommendation_id)
            ):

                return {
                    "found": True,
                    "recommendation": item,
                }

    latest = history[-1]

    return {
        "found": True,
        "recommendation": latest,
    }


# ============================================================
# HISTORY PAGE
# ============================================================

@app.get(
    "/history",
    response_class=HTMLResponse,
)
async def history_page(
    request: Request,
):

    user = require_user(request)

    history = get_history(
        user["email"]
    )

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "request": request,
            "user": user,
            "history": history[::-1],
        },
    )


# ============================================================
# HISTORY API
# ============================================================

@app.get("/api/history")
async def history_api(
    request: Request,
):

    user = require_user(request)

    return {
        "items": get_history(
            user["email"]
        )[::-1]
    }


# ============================================================
# STARTUP STATUS
# ============================================================

@app.get("/startup")
async def startup_status():

    return {
        "status": "ok",
        "service": "PocketSmart AI",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health():

    return {
        "status": "healthy"
    }


# ============================================================
# DIRECT SERVER START
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )