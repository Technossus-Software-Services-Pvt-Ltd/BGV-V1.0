from fastapi import HTTPException, status


class BGVBaseException(Exception):
    def __init__(self, message: str, correlation_id: str = None):
        self.message = message
        self.correlation_id = correlation_id
        super().__init__(message)


class OCRProcessingError(BGVBaseException):
    pass


class AIClassificationError(BGVBaseException):
    pass


class ValidationError(BGVBaseException):
    pass


class DocumentNotFoundError(BGVBaseException):
    pass


class CandidateNotFoundError(BGVBaseException):
    pass


class FileStorageError(BGVBaseException):
    pass


class OllamaConnectionError(BGVBaseException):
    pass


class ProcessingTimeoutError(BGVBaseException):
    pass
