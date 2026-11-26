
import json
import sqlite3

import pytest

from app import create_app, init_db, export_tasks


@pytest.fixture
def resources(tmp_path):
    db_path = tmp_path / "tasks.db"
    export_path = tmp_path / "tasks.json"
    app = create_app(db_path, export_path)
    return app.test_client(), db_path, export_path


def test_create_task(resources):
    client, db_path, export_path = resources

    response = client.post("/tasks", json={"title": "Вивчити pytest"})

    assert response.status_code == 201
    assert response.get_json()["title"] == "Вивчити pytest"

    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT title FROM tasks").fetchone()

    assert row == ("Вивчити pytest",)
    assert json.loads(
        export_path.read_text(encoding="utf-8")
    )[0]["title"] == "Вивчити pytest"


def test_get_tasks(resources):
    client, _, _ = resources

    client.post("/tasks", json={"title": "Перше завдання"})
    client.post("/tasks", json={"title": "Друге завдання"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == [
        "Перше завдання",
        "Друге завдання",
    ]


def test_create_task_requires_title(resources):
    client, _, export_path = resources

    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert not export_path.exists()


def test_database_table_creation(tmp_path):
    db_path = tmp_path / "tasks.db"

    init_db(db_path)

    with sqlite3.connect(db_path) as connection:
        result = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='tasks'"
        ).fetchone()

    assert result == ("tasks",)


def test_export_tasks(resources):
    client, db_path, export_path = resources

    client.post("/tasks", json={"title": "Тест JSON"})

    export_tasks(db_path, export_path)

    data = json.loads(export_path.read_text(encoding="utf-8"))

    assert len(data) == 1
    assert data[0]["title"] == "Тест JSON"


def test_create_two_tasks(resources):
    client, _, _ = resources

    first = client.post("/tasks", json={"title": "Перше"})
    second = client.post("/tasks", json={"title": "Друге"})

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get("/tasks")

    assert len(response.get_json()) == 2


def test_delete_task(resources):
    client, db_path, export_path = resources

    created = client.post("/tasks", json={"title": "Видалити мене"})
    task_id = created.get_json()["id"]

    response = client.delete(f"/tasks/{task_id}")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Завдання видалено"

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT * FROM tasks").fetchall()

    assert rows == []

    data = json.loads(export_path.read_text(encoding="utf-8"))
    assert data == []


def test_delete_nonexistent_task(resources):
    client, _, _ = resources

    response = client.delete("/tasks/999")

    assert response.status_code == 404


def test_export_empty_database(resources):
    _, db_path, export_path = resources

    export_tasks(db_path, export_path)

    assert json.loads(
        export_path.read_text(encoding="utf-8")
    ) == []


def test_export_corrupted_json(resources):
    _, _, export_path = resources

    export_path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        json.loads(export_path.read_text(encoding="utf-8"))
