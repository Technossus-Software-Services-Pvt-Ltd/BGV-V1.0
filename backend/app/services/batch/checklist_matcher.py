"""Pure logic for matching document types against the required document checklist."""

import re


class ChecklistMatcher:
    """Stateless helper for document type matching against required document rules."""

    @staticmethod
    def normalize_doc_type(doc_type: str) -> str:
        """Normalize a document type string for comparison.

        Strips spaces, underscores, hyphens and lowercases for matching
        AI classification output (e.g. 'pan_card') against checklist names (e.g. 'PAN Card').
        """
        return re.sub(r'[\s_\-]+', '', doc_type.lower().strip())

    @staticmethod
    def doc_type_matches_checklist(normalized_type: str, mandatory_doc_names: set[str]) -> bool:
        """Check if a normalized doc type matches any entry in the mandatory checklist.

        Uses substring matching: 'aadhaar' matches 'aadhaarcard' and vice versa.
        """
        for rule_name in mandatory_doc_names:
            if normalized_type in rule_name or rule_name in normalized_type:
                return True
        return False

    @staticmethod
    def get_matched_mandatory(
        uploaded_doc_types: set[str], mandatory_doc_names: set[str]
    ) -> tuple[set[str], set[str]]:
        """Return (matched, missing) mandatory doc names based on substring matching."""
        matched = set()
        for rule_name in mandatory_doc_names:
            for uploaded in uploaded_doc_types:
                if uploaded in rule_name or rule_name in uploaded:
                    matched.add(rule_name)
                    break
        missing = mandatory_doc_names - matched
        return matched, missing
