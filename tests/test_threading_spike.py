"""Regression test for the empirical pynetdicom threading result."""

from __future__ import annotations

import pytest

from scripts.spikes.pynetdicom_threading import observe


@pytest.mark.dicom
@pytest.mark.slow
def test_c_store_handler_runs_off_the_calling_thread() -> None:
    observation = observe()

    assert observation.store_thread_differs_from_main
    assert observation.handler_completed_before_send_return
