from collections.abc import Sequence

from sqlmodel import select

from katiu.core.repository import Repository
from katiu.payments.models import PackPurchase, Payment


class PaymentRepository(Repository[Payment]):
    model = Payment

    def for_student(self, student_id: int) -> Sequence[Payment]:
        return self.session.exec(select(Payment).where(Payment.student_id == student_id)).all()


class PackPurchaseRepository(Repository[PackPurchase]):
    model = PackPurchase
