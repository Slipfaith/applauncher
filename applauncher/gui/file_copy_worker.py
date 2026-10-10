"""Serialized background copies with explicit drop-payload lifetime."""
from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QRunnable, QThreadPool, Signal, Slot

from ..services.file_transfer_service import FileCopyError, FileCopySummary
from .drop_payload import DropFilePaths

DRAIN_WAIT_SLICE_MS = 10


class CopySignals(QObject):
    completed = Signal(object)


class CopyWorker(QRunnable):
    def __init__(self, service, payload: DropFilePaths, target: str):
        super().__init__()
        self.service, self.payload, self.target = service, payload, target
        self.signals = CopySignals()

    def run(self):
        try:
            summary = self.service.copy_files_to_folder(self.payload, self.target)
        except Exception as exc:
            summary = FileCopySummary(len(self.payload), 0, 0, len(self.payload), self.target,
                                      [FileCopyError("", str(exc))])
        finally:
            self.payload.cleanup()
        self.signals.completed.emit(summary)


class FileCopyQueue(QObject):
    completed = Signal(object)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.jobs = []
        self.accepting = True

    def submit(self, paths, target: str) -> None:
        payload = paths if isinstance(paths, DropFilePaths) else DropFilePaths(paths, [])
        if not self.accepting:
            payload.cleanup()
            return
        payload.claim()
        worker = CopyWorker(self.service, payload, target)
        worker.signals.completed.connect(self._completed)
        self.jobs.append(worker)
        self.pool.start(worker)

    @Slot(object)
    def _completed(self, summary):
        sender = self.sender()
        self.jobs = [job for job in self.jobs if job.signals is not sender]
        self.completed.emit(summary)

    def drain(self) -> None:
        self.accepting = False
        while True:
            finished = self.pool.waitForDone(DRAIN_WAIT_SLICE_MS)
            QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            if finished:
                return
