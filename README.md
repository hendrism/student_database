# Student Database

This Flask application manages student data and related records.

## Configuration via Environment Variables

The application reads several settings from environment variables. If a variable is
not provided, a sensible default is used.

| Variable      | Purpose                                        | Default                        |
|---------------|------------------------------------------------|--------------------------------|
| `DATABASE_URL`| SQLAlchemy database URI                        | Local file `student_database.db`|
| `SECRET_KEY`  | Secret key used for Flask sessions             | `dev-secret-key`               |
| `FLASK_DEBUG` | Enable Flask debug mode (`1`, `true`, etc.)    | `0` (disabled)                 |

Define these variables in your environment before starting the server if you
need different values.
