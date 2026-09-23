# Used Alembic Migration to Entire project

## Advantage of using it

**Alembic migrations act like Git for your database schema — every structural change (adding a column, renaming a table, etc.) is captured as a versioned, tracked script rather than a manual SQL command. This gives you safe upgrades and rollbacks (so a bad change can be reverted with one command), environment consistency (dev, staging, and production all apply the same migration history in the same order), and team collaboration (migration files live in your codebase alongside your code, so anyone can clone the repo and reproduce the exact database state). It also supports autogeneration from your SQLAlchemy models, reducing manual SQL work and the risk of human error, and integrates cleanly into CI/CD pipelines for automated, predictable deployments**

---

## Setup of the Migration

### Step 1: Initilize the migration

```bash
alembic init name_of_the_migration
```

### Step 2: Commit the migration

```bash
alembic revision --autogenerate -m "the commit message"
```

### Step 3: Apply the migration

```bash
alembic upgrade head
```

---

## Note

**Once the initilization is done go to alembic/env.py and change the following in the code**
**replace `bash target_metadata = target ` to `bash target_metadata = Base.metadata`**
**and import all the tables to that respective file with the class**

**Also when new table is being created or been added follow from the Step2 with proper commit message**

## Additional Information

### For Down grade

```bash

```
