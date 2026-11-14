"""The model line gives the front process the model, one at a time."""

from kernel.scheduler.llm_scheduler.book import Book


def test_one_process_holds_the_model() -> None:
    book = Book()
    book.admit("a")
    book.admit("b")
    assert book.grant() == "a"
    assert book.grant() is None
    assert book.model_busy


def test_a_waiting_task_lets_the_next_task_ask() -> None:
    book = Book()
    book.admit("41.1")
    book.admit("42.1")
    assert book.grant() == "41.1"
    book.begin_wait("41.1")
    assert book.model_busy is False
    assert book.grant() == "42.1"


def test_a_wait_lets_the_next_process_ask() -> None:
    book = Book()
    book.admit("a")
    book.admit("b")
    assert book.grant() == "a"
    book.begin_wait("a")
    assert book.model_busy is False
    assert book.grant() == "b"


def test_ready_tasks_take_whichever_core_becomes_free() -> None:
    book = Book()
    book.admit("41")
    book.admit("42")
    book.admit("43")

    assert book.grant(0) == "41"
    assert book.grant(1) == "42"
    assert book.grant(0) is None

    book.begin_wait("41")
    assert book.grant(0) == "43"
    assert book.core_for("43") == 0
    assert book.core_for("42") == 1


def test_a_finished_wait_stands_at_the_back() -> None:
    book = Book()
    book.admit("b")
    book.admit("a")
    assert book.grant() == "b"
    book.begin_wait("b")
    assert book.grant() == "a"
    book.finish_wait("b")
    book.finish("a")
    assert book.grant() == "b"
