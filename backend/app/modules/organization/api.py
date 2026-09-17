from fastapi import FastAPI

app = FastAPI(title="Organization API")


# =========================
# Authentication
# =========================

@app.post("/auth/register")
def register_organization():
    ...


@app.post("/auth/login")
def login_organization():
    ...


@app.post("/auth/logout")
def logout_organization():
    ...


@app.post("/auth/change-password")
def change_organization_password():
    ...


@app.post("/auth/forgot-password")
def forgot_password():
    ...


@app.post("/auth/reset-password")
def reset_password():
    ...


# =========================
# Organization
# =========================

@app.get("/organization")
def get_organization_profile():
    ...


@app.patch("/organization")
def update_organization():
    ...


@app.delete("/organization")
def delete_organization():
    ...


# =========================
# Organization Admins
# =========================

@app.post("/organization/admins")
def create_admin():
    ...


@app.get("/organization/admins")
def list_admins():
    ...


@app.get("/organization/admins/{admin_id}")
def get_admin():
    ...


@app.patch("/organization/admins/{admin_id}")
def update_admin():
    ...


@app.delete("/organization/admins/{admin_id}")
def delete_admin():
    ...