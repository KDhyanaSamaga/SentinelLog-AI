# TABLE-2: Admin

## **The organization assigns some employee/workers to perform the respective task**

### **1. Description**

The `admin` table stores details about administrative personnel and workers associated with an organization. It manages login authentication, personal identifiers (e.g., employee ID, contact details), status flags, and links directly to the parent `organization` via a foreign key relationship.

---

### **2. Schema Structure & Column Specifications**

| Column Name                 | Data Type      | Nullable | Constraints & Defaults                       | Description                                                                                   |
| --------------------------- | -------------- | -------- | -------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **`id`**                    | `UUID`         | **NO**   | `PRIMARY KEY`, `default=uuid.uuid4`          | Unique primary key for each admin record.                                                     |
| **`admin_name`**            | `VARCHAR(255)` | **NO**   | Length limit: 255 chars                      | Full name of the administrative employee/worker.                                              |
| **`admin_email`**           | `VARCHAR(320)` | **NO**   | `UNIQUE`, `INDEXED`, Length limit: 320 chars | Primary work email address used for login and notifications. Indexed for performance.         |
| **`admin_phone`**           | `VARCHAR(15)`  | **NO**   | `UNIQUE`, Length limit: 15 chars             | Direct phone number of the admin (must be unique across all admin entries).                   |
| **`admin_hashed_password`** | `VARCHAR(255)` | **NO**   | Length limit: 255 chars                      | Encrypted/hashed password for security authentication.                                        |
| **`admin_employee_id`**     | `VARCHAR(50)`  | **NO**   | Length limit: 50 chars                       | Internal employee or worker identification code assigned by the organization.                 |
| **`admin_organization_id`** | `UUID`         | **NO**   | `FOREIGN KEY("organization.id")`, `INDEXED`  | References `id` in the `organization` table to link the admin to their specific organization. |
| **`is_active`**             | `BOOLEAN`      | **NO**   | `DEFAULT: True`                              | Tracks whether the admin account is active or deactivated.                                    |
| **`is_verified`**           | `BOOLEAN`      | **NO**   | `DEFAULT: False`                             | Tracks whether the admin's account credentials or email have been verified.                   |
| **`created_at`**            | `TIMESTAMPTZ`  | **NO**   | `server_default: NOW()`                      | Record creation timestamp (stored with timezone).                                             |
| **`updated_at`**            | `TIMESTAMPTZ`  | **NO**   | `server_default: NOW()`, `onupdate: NOW()`   | Automatic timestamp updated whenever the record is altered.                                   |

### **3. Inactive / Commented Out Columns**

- **`role`**:
- **Type:** `VARCHAR(50)`
- **Status:** Currently commented out in code.
- **Intended Constraints:** `DEFAULT: "admin"`, `NOT NULL`.
- **Purpose:** Designed to differentiate permissions or authorization levels (e.g., super admin, manager, supervisor) once granular Role-Based Access Control (RBAC) is implemented.

---

### **4. Model Relationships**

- **`organization`**
- **Type:** Many-to-One (`N : 1`)
- **Target Model:** `Organization`
- **Back-Populates:** `users`
- **Behavior:** Establishes the relationship back to the parent `Organization` model using `admin_organization_id` as the foreign key constraint.

---
