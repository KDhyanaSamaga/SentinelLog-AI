# TABLE-1: Organization

## **This table contain the information of the organization that is registered in this application\***

### **1. Description**

The `organization` table serves as the primary entity for managing tenant/company accounts within the application. It stores core organization identity details, authentication credentials, account status flags, auditing timestamps, and establishes a one-to-many relationship with registered users.

---

### **2. Schema Structure & Column Specifications**

| Column Name                        | Data Type      | Nullable | Constraints & Defaults                       | Description                                                                            |
| ---------------------------------- | -------------- | -------- | -------------------------------------------- | -------------------------------------------------------------------------------------- |
| **`id`**                           | `UUID`         | **NO**   | `PRIMARY KEY`, `default=uuid.uuid4`          | Unique identifier for each organization record.                                        |
| **`organization_name`**            | `VARCHAR(255)` | **NO**   | Length limit: 255 chars                      | The legal or trade name of the registered organization.                                |
| **`organization_email`**           | `VARCHAR(320)` | **NO**   | `UNIQUE`, `INDEXED`, Length limit: 320 chars | Primary contact and login email address for the organization. Indexed for fast lookup. |
| **`organization_phone`**           | `VARCHAR(15)`  | **NO**   | Length limit: 15 chars                       | Primary contact phone number (formatted according to E.164 standards).                 |
| **`organization_hashed_password`** | `VARCHAR(255)` | **NO**   | Length limit: 255 chars                      | Securely hashed password string for organization authentication.                       |
| **`is_active`**                    | `BOOLEAN`      | **NO**   | `DEFAULT: True`                              | Indicates whether the organization account is currently active or suspended.           |
| **`is_verified`**                  | `BOOLEAN`      | **NO**   | `DEFAULT: False`                             | Indicates whether the organization's email or identity has been verified.              |
| **`created_at`**                   | `TIMESTAMPTZ`  | **NO**   | `server_default: NOW()`                      | UTC timestamp indicating when the organization record was created.                     |
| **`updated_at`**                   | `TIMESTAMPTZ`  | **NO**   | `server_default: NOW()`, `onupdate: NOW()`   | UTC timestamp automatically updated whenever any column in the record is modified.     |

---

### **3. Inactive / Commented Out Columns**

- **`subscription_plan`**:
- **Type:** `VARCHAR(50)`
- **Status:** Currently disabled in code.
- **Intended Constraints:** `DEFAULT: "free"`, `NOT NULL`.
- **Purpose:** Designed to track subscription tiers (e.g., free, pro, enterprise) once billing/subscription modules are enabled.

---

### **4. Model Relationships**

- **`users`**
- **Type:** One-to-Many (`1 : N`)
- **Target Model:** `Users`
- **Back-Populates:** `organization`
- **Cascade Rule:** `cascade="all, delete-orphan"`
- **Behavior:** An organization can have multiple associated users. If an organization record is deleted, all child user records linked to that organization are automatically deleted from the database.
