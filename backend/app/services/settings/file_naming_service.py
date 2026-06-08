import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_naming_rule import FileNamingRule


DEFAULT_FOLDER_STRUCTURE_PATTERN = "{CandidateID}_{FirstName}_{Date}"
DEFAULT_FILE_RENAME_PATTERN = "{CandidateID}_{FirstName}_{DocType}"
DEFAULT_EXAMPLE_OUTPUT = "BVA-0042_Ravi_20260530/BVA-0042_Ravi_Aadhaar.pdf"


class FileNamingRuleService:
    @staticmethod
    async def get_active_rule(db: AsyncSession) -> FileNamingRule:
        result = await db.execute(
            select(FileNamingRule)
            .where(FileNamingRule.is_active.is_(True))
            .order_by(FileNamingRule.updated_at.desc())
        )
        existing = result.scalars().first()
        if existing:
            return existing

        rule = FileNamingRule(
            folder_structure_pattern=DEFAULT_FOLDER_STRUCTURE_PATTERN,
            file_rename_pattern=DEFAULT_FILE_RENAME_PATTERN,
            example_output=DEFAULT_EXAMPLE_OUTPUT,
            is_active=True,
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return rule

    @staticmethod
    async def save_rule(
        db: AsyncSession,
        folder_structure_pattern: str,
        file_rename_pattern: str,
    ) -> FileNamingRule:
        active_rule = await FileNamingRuleService.get_active_rule(db)

        normalized_folder_pattern = folder_structure_pattern.strip()
        normalized_file_pattern = file_rename_pattern.strip()

        active_rule.folder_structure_pattern = normalized_folder_pattern
        active_rule.file_rename_pattern = normalized_file_pattern
        active_rule.example_output = FileNamingRuleService.build_example_output(
            normalized_folder_pattern,
            normalized_file_pattern,
        )
        active_rule.is_active = True

        await db.commit()
        await db.refresh(active_rule)
        return active_rule

    @staticmethod
    def build_example_output(folder_pattern: str, file_pattern: str) -> str:
        sample_values = {
            "{CandidateID}": "BVA-0042",
            "{FirstName}": "Ravi",
            "{Date}": "20260530",
            "{DocType}": "Aadhaar",
        }

        folder = folder_pattern
        filename = file_pattern
        for token, value in sample_values.items():
            folder = folder.replace(token, value)
            filename = filename.replace(token, value)

        return f"{folder}/{filename}.pdf"

    @staticmethod
    def resolve_folder_name(
        pattern: str,
        candidate_id: str,
        candidate_name: str,
        batch_date: datetime | None = None,
    ) -> str:
        """Resolve folder name pattern with actual candidate/batch values."""
        if not pattern:
            pattern = DEFAULT_FOLDER_STRUCTURE_PATTERN

        first_name = candidate_name.split()[0] if candidate_name else "Unknown"
        date_str = (batch_date or datetime.now(timezone.utc)).strftime("%Y%m%d")

        replacements = {
            "{CandidateID}": candidate_id or "UNKNOWN",
            "{FirstName}": first_name,
            "{Date}": date_str,
            "{DocType}": "",  # Not applicable for folder names
        }

        resolved = pattern
        for token, value in replacements.items():
            resolved = resolved.replace(token, value)

        # Sanitize for filesystem/Drive safety
        resolved = re.sub(r'[<>:"/\\|?*]', "-", resolved).strip(" .-")
        return resolved or f"{candidate_id}_{first_name}_{date_str}"

    @staticmethod
    def resolve_file_name(
        pattern: str,
        candidate_id: str,
        candidate_name: str,
        document_type: str,
        original_filename: str,
    ) -> str:
        """Resolve file name pattern with actual candidate/document values."""
        if not pattern:
            pattern = DEFAULT_FILE_RENAME_PATTERN

        first_name = candidate_name.split()[0] if candidate_name else "Unknown"
        # Preserve original file extension
        extension = Path(original_filename).suffix.lower() or ".pdf"

        replacements = {
            "{CandidateID}": candidate_id or "UNKNOWN",
            "{FirstName}": first_name,
            "{DocType}": document_type or "Document",
            "{Date}": datetime.now(timezone.utc).strftime("%Y%m%d"),
        }

        resolved = pattern
        for token, value in replacements.items():
            resolved = resolved.replace(token, value)

        # Sanitize for filesystem/Drive safety
        resolved = re.sub(r'[<>:"/\\|?*]', "-", resolved).strip(" .-")
        if not resolved:
            resolved = Path(original_filename).stem

        return f"{resolved}{extension}"
