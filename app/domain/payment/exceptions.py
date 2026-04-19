class DomainError(Exception):
    pass


class PaymentNotFoundError(DomainError):
    pass


class DuplicatePaymentError(DomainError):
    pass


class InvalidPaymentStateError(DomainError):
    pass


class InvalidMoneyError(DomainError):
    pass
