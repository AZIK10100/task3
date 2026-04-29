import json
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import Card, StatusChoices, Transfer, TransferState


class TransferRpcTests(TestCase):
    rpc_url = "/rpc/"
    sender_card_number = "4111111111111111"
    receiver_card_number = "4000000000000002"

    @classmethod
    def setUpTestData(cls):
        call_command("populate")

        cls.sender_card = Card.objects.create(
            card_number=cls.sender_card_number,
            phone="+998901234567",
            balance=Decimal("50000.00"),
            status=StatusChoices.ACTIVE,
            expire_date=timezone.datetime(2026, 12, 1).date(),
        )
        cls.receiver_card = Card.objects.create(
            card_number=cls.receiver_card_number,
            phone="+998909876543",
            balance=Decimal("1000.00"),
            status=StatusChoices.ACTIVE,
            expire_date=timezone.datetime(2027, 1, 1).date(),
        )

    def rpc_call(self, payload):
        response = self.client.post(
            self.rpc_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        return response, json.loads(response.content.decode("utf-8"))

    def create_payload(self, ext_id="tr-001"):
        return {
            "id": 1,
            "method": "transfer.create",
            "params": {
                "ext_id": ext_id,
                "sender_card_number": self.sender_card_number,
                "sender_card_expiry": "12/26",
                "receiver_card_number": self.receiver_card_number,
                "sending_amount": 15000,
                "currency": 643,
            },
        }

    def create_transfer_with_rpc(self, ext_id="tr-001"):
        response, payload = self.rpc_call(self.create_payload(ext_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["result"]["state"], TransferState.CREATED)
        return Transfer.objects.get(ext_id=ext_id)

    def wrong_otp(self, correct_otp):
        return "000000" if correct_otp != "000000" else "999999"

    def test_transfer_create_success(self):
        response, payload = self.rpc_call(self.create_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["result"]["ext_id"], "tr-001")
        self.assertEqual(payload["result"]["state"], TransferState.CREATED)
        self.assertTrue(payload["result"]["otp_sent"])

        transfer = Transfer.objects.get(ext_id="tr-001")
        self.assertEqual(transfer.sender_card_number, self.sender_card_number)
        self.assertEqual(transfer.receiver_card_number, self.receiver_card_number)
        self.assertEqual(transfer.receiving_amount, Decimal("2100000.00"))
        self.assertEqual(len(transfer.otp), 6)

    def test_transfer_create_duplicate_ext_id(self):
        self.create_transfer_with_rpc(ext_id="tr-duplicate")

        response, payload = self.rpc_call(self.create_payload(ext_id="tr-duplicate"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["error"]["code"], 32701)

    def test_transfer_confirm_with_wrong_otp(self):
        transfer = self.create_transfer_with_rpc(ext_id="tr-wrong-otp")

        response, payload = self.rpc_call(
            {
                "id": 2,
                "method": "transfer.confirm",
                "params": {
                    "ext_id": transfer.ext_id,
                    "otp": self.wrong_otp(transfer.otp),
                },
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["error"]["code"], 32712)

        transfer.refresh_from_db()
        self.assertEqual(transfer.try_count, 1)
        self.assertEqual(transfer.state, TransferState.CREATED)

    def test_transfer_confirm_blocks_after_three_wrong_attempts(self):
        transfer = self.create_transfer_with_rpc(ext_id="tr-block")
        wrong_otp = self.wrong_otp(transfer.otp)

        for _ in range(2):
            response, payload = self.rpc_call(
                {
                    "id": 3,
                    "method": "transfer.confirm",
                    "params": {"ext_id": transfer.ext_id, "otp": wrong_otp},
                }
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["error"]["code"], 32712)

        response, payload = self.rpc_call(
            {
                "id": 3,
                "method": "transfer.confirm",
                "params": {"ext_id": transfer.ext_id, "otp": wrong_otp},
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["error"]["code"], 32711)

        transfer.refresh_from_db()
        self.assertEqual(transfer.try_count, 3)

    def test_transfer_cancel(self):
        transfer = self.create_transfer_with_rpc(ext_id="tr-cancel")

        response, payload = self.rpc_call(
            {
                "id": 4,
                "method": "transfer.cancel",
                "params": {"ext_id": transfer.ext_id},
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["result"]["state"], TransferState.CANCELLED)

        transfer.refresh_from_db()
        self.assertEqual(transfer.state, TransferState.CANCELLED)
        self.assertIsNotNone(transfer.cancelled_at)

    def test_transfer_state(self):
        transfer = Transfer.objects.create(
            ext_id="tr-state",
            sender_card_number=self.sender_card_number,
            receiver_card_number=self.receiver_card_number,
            sender_card_expiry="12/26",
            sender_phone=self.sender_card.phone,
            receiver_phone=self.receiver_card.phone,
            sending_amount=Decimal("15000.00"),
            currency=643,
            receiving_amount=Decimal("2100000.00"),
            state=TransferState.CONFIRMED,
            confirmed_at=timezone.now(),
        )

        response, payload = self.rpc_call(
            {
                "id": 5,
                "method": "transfer.state",
                "params": {"ext_id": transfer.ext_id},
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["result"]["ext_id"], "tr-state")
        self.assertEqual(payload["result"]["state"], TransferState.CONFIRMED)

    def test_transfer_history(self):
        today = timezone.now().date().isoformat()

        confirmed_transfer = Transfer.objects.create(
            ext_id="tr-history-1",
            sender_card_number=self.sender_card_number,
            receiver_card_number=self.receiver_card_number,
            sender_card_expiry="12/26",
            sender_phone=self.sender_card.phone,
            receiver_phone=self.receiver_card.phone,
            sending_amount=Decimal("15000.00"),
            currency=643,
            receiving_amount=Decimal("2100000.00"),
            state=TransferState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        Transfer.objects.create(
            ext_id="tr-history-2",
            sender_card_number=self.sender_card_number,
            receiver_card_number=self.receiver_card_number,
            sender_card_expiry="12/26",
            sender_phone=self.sender_card.phone,
            receiver_phone=self.receiver_card.phone,
            sending_amount=Decimal("5000.00"),
            currency=643,
            receiving_amount=Decimal("700000.00"),
            state=TransferState.CANCELLED,
            cancelled_at=timezone.now(),
        )

        response, payload = self.rpc_call(
            {
                "id": 6,
                "method": "transfer.history",
                "params": {
                    "card_number": self.sender_card_number,
                    "start_date": today,
                    "end_date": today,
                    "status": TransferState.CONFIRMED,
                },
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["result"]), 1)
        self.assertEqual(payload["result"][0]["ext_id"], confirmed_transfer.ext_id)
