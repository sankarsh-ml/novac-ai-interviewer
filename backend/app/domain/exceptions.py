class DomainError(Exception):
    pass


class ValidationError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class ExternalServiceError(DomainError):
    pass


class QuestionGenerationError(ExternalServiceError):
    pass


class IdentityVerificationError(ExternalServiceError):
    pass
