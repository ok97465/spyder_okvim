"""Worker capacity belongs to the application service, not popup sessions."""

from threading import Event, Lock

import pytest

from spyder_okvim.spyder.picker_work import PickerWorkService


@pytest.mark.parametrize("lane", PickerWorkService.LANES)
def test_active_slot_waits_for_cancelled_work_and_only_latest_runs(qtbot, lane):
    service = PickerWorkService()
    entered, release = Event(), Event()
    lock = Lock()
    running = 0
    maximum = 0
    executed = []
    delivered = []
    service.completed.connect(lambda *result: delivered.append(result))

    def operation(number, blocked=False):
        def run(cancel):
            nonlocal running, maximum
            with lock:
                running += 1
                maximum = max(maximum, running)
            executed.append(number)
            try:
                if blocked:
                    entered.set()
                    release.wait(5)
                return number
            finally:
                with lock:
                    running -= 1

        return run

    service.submit(lane, 1, operation(1, blocked=True))
    try:
        qtbot.waitUntil(entered.is_set)
        original = service.active[lane]
        service.submit(lane, 2, operation(2))
        service.submit(lane, 3, operation(3))
        assert service.active[lane] is original
        assert original.cancelled.is_set()
        assert service.pending[lane].token == 3
        assert executed == [1]
    finally:
        release.set()
    qtbot.waitUntil(lambda: bool(delivered))
    assert delivered == [(lane, 3, 3)]
    assert executed == [1, 3]
    assert maximum == 1
    assert service.active[lane] is None and service.pending[lane] is None
    service.close()


def test_backend_exception_releases_lane_for_following_request(qtbot):
    service = PickerWorkService()
    delivered = []
    service.completed.connect(lambda *result: delivered.append(result))

    def failing(cancel):
        raise OSError("unavailable filesystem")

    service.submit("content", "failure", failing)
    qtbot.waitUntil(lambda: bool(delivered))
    assert isinstance(delivered[0][2], OSError)
    assert service.active["content"] is None
    service.submit("content", "next", lambda cancel: "recovered")
    qtbot.waitUntil(lambda: len(delivered) == 2)
    assert delivered[-1] == ("content", "next", "recovered")
    assert service.active["content"] is None
    service.close()


def test_blocked_collection_does_not_occupy_search_lane(qtbot):
    service = PickerWorkService()
    entered, release = Event(), Event()
    delivered = []
    service.completed.connect(lambda *result: delivered.append(result))

    def collect(cancel):
        entered.set()
        release.wait(5)
        return "candidates"

    service.submit("collect", 1, collect)
    try:
        qtbot.waitUntil(entered.is_set)
        service.submit("search", 2, lambda cancel: "query result")
        qtbot.waitUntil(lambda: bool(delivered))
        assert delivered == [("search", 2, "query result")]
        assert service.active["collect"] is not None
        service.cancel()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not any(service.active.values()))
    assert delivered == [("search", 2, "query result")]
    service.close()


def test_close_discards_clients_and_pending_without_freeing_running_slot(qtbot):
    service = PickerWorkService()
    entered, release = Event(), Event()
    delivered = []
    service.completed.connect(lambda *result: delivered.append(result))

    def collect(cancel):
        entered.set()
        release.wait(5)
        return "late"

    service.submit("collect", "active", collect)
    try:
        qtbot.waitUntil(entered.is_set)
        original = service.active["collect"]
        service.submit("collect", "pending", lambda cancel: "never")
        service.close()
        service.close()
        assert service.active["collect"] is original
        assert service.pending["collect"] is None
        assert original.cancelled.is_set()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not any(service.active.values()))
    assert not delivered
