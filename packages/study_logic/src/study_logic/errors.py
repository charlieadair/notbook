class StudyError(Exception):
    def __init__(self, code: str, status: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message

    def to_json(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


def topics_unconfirmed(message: str = "Topic map is not confirmed") -> StudyError:
    return StudyError("TopicsUnconfirmed", 409, message)


def insufficient_evidence(message: str = "Vault is empty or has no citable chunks") -> StudyError:
    return StudyError("InsufficientEvidence", 422, message)


def not_found(message: str) -> StudyError:
    return StudyError("NotFound", 404, message)


def bad_request(message: str) -> StudyError:
    return StudyError("BadRequest", 400, message)
