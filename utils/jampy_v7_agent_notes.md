# Jam.py v7 — AI Agent Notes

> These notes are intended to give an AI assistant enough context to write
> correct Jam.py v7 code. They capture not just the API, but the flow,
> the gotchas, and the deprecated-but-still-used exceptions that only
> come from real experience with the framework.

---

## 1. Core Concepts

### CRUD is already there
Jam.py provides full CRUD out of the box — forms, save/delete/edit buttons,
the whole lifecycle. Do **not** write CRUD from scratch. The correct mental
model is:

> "The app works already. I need to add ____ behaviour at ____ point in the lifecycle."

### The client/server boundary
Jam.py has two parallel event systems that must not be confused:

| Side | Language | Purpose |
|------|----------|---------|
| Client | JavaScript | UI behaviour, reacting to user input |
| Server | Python | Database operations, validation, calculations |

### Events extend built-in behaviour, not replace it
Jam.py handles CRUD automatically. Events let you add your own logic at
specific points in that lifecycle — before or after the framework does its
work. You define the event function; Jam.py calls it at the right moment.

---

## 2. The Event Lifecycle

### Open lifecycle (Python — server side)

| Event | When it fires | Use it for |
|-------|--------------|------------|
| `on_before_open` | Before the SQL request executes | Validate the request, add extra filters |
| `on_after_open` | After SQL executes, before data sent to client | Modify the dataset before the client receives it |
| `on_open` | Override or extend the standard fetch procedure | Any item, or at task level for all items (see below) |

#### on_open — execution order

The framework processes `on_open` in this order:

```
task.on_open → item.on_open → default SQL select
```

Each step only runs if the previous returned `None`.

#### on_open — use cases

**1. Filter records based on session data (task level)**

Declared in the task server module — applies globally to every item that
has a `user_id` field (multi-tenancy example):

```python
def on_open(item, params):
    if item.field_by_name('user_id'):
        if item.session:
            user_id = item.session['user_info']['user_id']
            if user_id:
                params['__filters'].append(['user_id', item.task.consts.FILTER_EQ, user_id])
```

**2. Filter records for a specific item (item level)**

Same pattern but in the item's own server module:

```python
def on_open(item, params):
    if item.session:
        user_id = item.session['user_info']['user_id']
        if user_id:
            params['__filters'].append(['user_id', item.task.consts.FILTER_EQ, user_id])
```

**3. External database connections (item level)**

```python
import pyodbc
from jam.db.access_db import db
from jam.items import QueryData

def on_open(item, params):
    connection = item.task.create_connection_ex(
        db,
        database=r"C:\Users\dba\Downloads\arab\arab.accdb",
    )
    try:
        query_data = QueryData(params)
        sql, sql_params = db.get_select_query(item, query_data)
        rows = item.task.select(sql, connection, db, sql_params)
    finally:
        connection.close()
    return rows, ''
```

Key points for external connections:
- `QueryData` wraps the client's request params for the query builder
- `get_select_query()` builds SQL that respects filters/sorting set on the client
- Return value is `rows, ''` — second element is an error string, empty if successful
- Always close external connections in a `finally` block

> **Common AI mistake:** Describing `on_open` as deprecated or as being
> for external databases only. It is a general-purpose override for the
> fetch procedure, usable at both item and task level.

### Apply lifecycle (Python — server side)

| Event | When it fires | Use it for |
|-------|--------------|------------|
| `on_before_apply_record` | Before SQL save executes | Data validation, calculations (like `on_before_post` on the client) |
| `on_after_apply_record` | After SQL save, primary key is set | Additional DB changes in the same connection |
| `on_apply` | Override or extend the standard save procedure | Any item, or at task level for all items (see below) |

#### on_apply — execution order

The framework processes `on_apply` in this order:

```
task.on_apply → item.on_apply → apply_delta (default)
```

Each step only runs if the previous returned `None`. So:
- If `task.on_apply` returns a result, `item.on_apply` and `apply_delta` are skipped
- If `item.on_apply` returns `None`, `apply_delta` still runs automatically
- `apply_delta` is the default save — it generates and executes the SQL

#### on_apply — use cases

**1. Modify delta before saving (item level)**

Useful for setting server-side values like timestamps before the record is written:

```python
import datetime

def on_apply(item, delta, params, connection):
    for d in delta:
        d.edit()
        d.date.value = datetime.datetime.now()
        d.post()
    # returns None, so apply_delta runs automatically after
```

**2. Cross-table calculations in one transaction (item level)**

```python
def on_apply(item, delta, params, connection):
    if not delta.rec_deleted():
        calc_invoice(delta, connection)
    # returns None, so apply_delta still runs
```

**3. External database connections (item level)**

```python
def on_apply(item, delta, params, con):
    connection = item.task.create_connection_ex(
        db,
        database=r"C:\Users\dba\Downloads\arab\arab.accdb",
    )
    try:
        result = delta.apply_delta(delta, params, connection, db)
        connection.commit()
    finally:
        connection.close()
    return result
```

Key points for external connections:
- `connection.commit()` must be called explicitly — it is not automatic
- Always close the connection in a `finally` block
- Return `result` so the client receives confirmation of the applied changes

**4. Task-level on_apply — applies globally to all items**

Declared in the *task* server module, not an item module. Useful for
app-wide rules such as multi-tenancy — automatically stamping a `user_id`
on every insert across the whole application:

```python
def on_apply(item, delta, params, connection):
    if item.field_by_name('user_id'):
        if item.session:
            user_id = item.session['user_info']['user_id']
            if user_id:
                for d in delta:
                    if d.rec_inserted():
                        d.edit()
                        d.user_id.value = user_id
                        d.post()
                    elif d.rec_modified():
                        if d.user_id.old_value != user_id:
                            raise Exception('You are not allowed to change record.')
                    elif d.rec_deleted():
                        if d.user_id.old_value != user_id:
                            raise Exception('You are not allowed to delete record.')
```

> **Common AI mistake:** Describing `on_apply` as deprecated or as being
> for external databases only. It is a general-purpose override for the
> save procedure, usable at both item and task level.

#### Master-detail apply order
When a record has details, the apply lifecycle cascades in a specific order:

**Forward pass (`on_before_apply_record`):**
1. Master
2. Details
3. Sub-details (and so on)

**Reverse pass (`on_after_apply_record`):**
1. Sub-details
2. Details
3. Master

> The entire document (master + all details) saves as a unit, even if only
> a detail record was changed.

### Client-side events (JavaScript)

| Event | Use it for |
|-------|------------|
| `on_field_changed` | React to a field value changing in the UI |
| `on_before_post` | Validate before record is posted locally |
| `on_edit_form_created` | Customise the edit form after it appears |
| `on_view_form_created` | Customise the view form after it appears |

---

## 3. Correct Patterns

### Adding a button to the view form
Use `add_view_button()` inside `on_view_form_created`:

```javascript
function on_view_form_created(item) {
    var my_btn = item.add_view_button('Do Something', {image: 'bi bi-gear'});
    my_btn.click(function() {
        // your logic here
    });
}
```

### Adding a button to the edit form
Use `add_edit_button()` inside `on_edit_form_created`:

```javascript
function on_edit_form_created(item) {
    if (!item.lookup_field) {
        var my_btn = item.add_edit_button('Do Something', {image: 'bi bi-gear'});
        my_btn.click(function() {
            // your logic here
        });
    }
}
```

> **Important:** The `if (!item.lookup_field)` guard prevents the button
> appearing when the form is opened as a lookup selector from another item.
> Always include it unless you have a specific reason not to.

> **Common AI mistake:** Do not manually construct and append jQuery button
> elements to `.modal-footer`. Always use `add_edit_button()` /
> `add_view_button()`.

### Triggering a save from the client
Use `item.apply()` — this is the JS→Python bridge. It saves the record
and automatically fires the server-side apply lifecycle events:

```javascript
item.apply();
```

This in turn fires on the server:
```python
def on_after_apply_record(item, delta, params, connection):
    # e.g. recalculate totals
    pass
```

> **Common AI mistake:** Do not use `item.server()` for saving/recalculating.
> `item.server()` is for calling *arbitrary* Python functions outside the
> apply lifecycle. `item.apply()` is the correct bridge for saves.

---

## 4. Deprecated Events — Quick Reference

| Deprecated | Replacement | Exception |
|------------|-------------|-----------|
| `on_open` | `on_before_open` / `on_after_open` | Still correct for overriding/extending the fetch procedure at item or task level |
| `on_apply` | `on_before_apply_record` / `on_after_apply_record` | Still correct for overriding/extending the save procedure at item or task level |

---

## 5. Further Resources

- Full v7 documentation: https://jampy-docs-v7.readthedocs.io/
- LLM context file (concise): https://jampy-docs-v7.readthedocs.io/en/latest/llms.txt
- LLM context file (full): https://jampy-docs-v7.readthedocs.io/en/latest/llms-full.txt
- Application design tips: https://jampy-application-design-tips.readthedocs.io/

---

*These notes were compiled from a guided conversation with corrections from
an experienced Jam.py developer. They should be treated as a living document
— corrections and additions from real-world usage are the most valuable
contributions.*
