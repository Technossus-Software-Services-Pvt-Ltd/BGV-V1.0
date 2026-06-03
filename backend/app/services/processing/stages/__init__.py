"""Pipeline stages package.

Each stage encapsulates one processing step of the document pipeline.
Stages are stateless and receive all dependencies + context via their constructor.
"""

from app.services.processing.stages.context import PipelineContext
from app.services.processing.stages.normalization_stage import NormalizationStage
from app.services.processing.stages.ocr_stage import OCRStage
from app.services.processing.stages.classification_stage import ClassificationStage
from app.services.processing.stages.validation_stage import ValidationStage
from app.services.processing.stages.persistence_stage import PersistenceStage

__all__ = [
    "PipelineContext",
    "NormalizationStage",
    "OCRStage",
    "ClassificationStage",
    "ValidationStage",
    "PersistenceStage",
]
