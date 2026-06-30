import unittest
from datetime import date, datetime, timezone

from app.routes.kyc_routes import make_json_safe


class KycJsonSerializationTests(unittest.TestCase):
    def test_make_json_safe_converts_datetime_and_date_values(self):
        payload = {
            "verifiedAt": datetime(2026, 6, 30, 7, 45, tzinfo=timezone.utc),
            "createdAt": date(2026, 6, 30),
            "identityVerification": {
                "updatedAt": datetime(2026, 6, 30, 8, 15, tzinfo=timezone.utc),
            },
        }

        encoded = make_json_safe(payload)

        self.assertIsInstance(encoded["verifiedAt"], str)
        self.assertIsInstance(encoded["createdAt"], str)
        self.assertIsInstance(encoded["identityVerification"]["updatedAt"], str)


if __name__ == "__main__":
    unittest.main()
