"""
E4: Custom exceptions for session workflows.
"""


class ThesisNotFoundError(Exception):
    """Raised when a thesis ID is not found in the database."""
    
    def __init__(self, thesis_id: str):
        self.thesis_id = thesis_id
        super().__init__(f"Thesis not found: {thesis_id}")

