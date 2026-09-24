# TABLE-4: Token

## **This table contains short-lived tokens assigned by the server during authentication**

### **1. Description**

The `token` table manages active, short-lived authentication sessions (e.g., access tokens, refresh tokens, password reset tokens) generated upon login. It supports dual identity types, accommodating sessions for both **Organizations** (acting as Super Admins) and **Admins** (organization employees).

---

### **2. Schema Structure & Column Specifications**

| Column Name           | Data Type      | Nullable | Constraints & Defaults                       | Description                                                                      |
| --------------------- | -------------- | -------- | -------------------------------------------- | -------------------------------------------------------------------------------- |
| **`id`**              | `UUID`         | **NO**   | `PRIMARY KEY`, `default=uuid.uuid4`          | Unique record identifier for the token session.                                  |
| **`token`**           | `VARCHAR(512)` | **NO**   | `UNIQUE`, `INDEXED`, Length limit: 512 chars | Hashed or raw token string issued to the client. Indexed for quick verification. |
| **`token_type`**      | `VARCHAR(20)`  | **NO**   | `DEFAULT: "bearer"`, Length limit: 20 chars  | Category of token (e.g., `access`, `refresh`, `password_reset`).                 |
| **`user_type`**       | `VARCHAR(20)`  | **NO**   | Length limit: 20 chars                       | Identifies entity role (`organization` or `admin`) for authorization logic.      |
| **`organization_id`** | `UUID`         | **YES**  | `FOREIGN KEY("organization.id")`, `INDEXED`  | Points to `organization.id` if an Organization/Super Admin logs in.              |
| **`admin_id`**        | `UUID`         | **YES**  | `FOREIGN KEY("admin.id")`, `INDEXED`         | Points to `admin.id` if an Admin/Employee logs in.                               |
| **`is_revoked`**      | `BOOLEAN`      | **NO**   | `DEFAULT: False`                             | Status flag used to manually invalidate/black-list tokens before expiration.     |
| **`expires_at`**      | `TIMESTAMPTZ`  | **NO**   | None                                         | Expiration UTC timestamp set by the server. Used to reject expired logins.       |
| **`created_at`**      | `TIMESTAMPTZ`  | **NO**   | `server_default: NOW()`                      | UTC timestamp recording when the session token was issued.                       |

---

### **3. Table Constraints**

- **`check_token_owner` Constraint**:
- Enforces that **either** `organization_id` **or** `admin_id` is populated, but **never both** and **never neither**.
- Guarantees database-level integrity so tokens are strictly associated with a single identity per session.

---

### **4. Model Relationships**

- **`organization`**
- **Type:** Many-to-One (`N : 1`)
- **Target Model:** `Organization`
- **Cascade:** `ondelete="CASCADE"` (Tokens are purged if the organization account is deleted).

- **`admin`**
- **Type:** Many-to-One (`N : 1`)
- **Target Model:** `Admin`
- **Cascade:** `ondelete="CASCADE"` (Tokens are purged if the admin account is deleted).
