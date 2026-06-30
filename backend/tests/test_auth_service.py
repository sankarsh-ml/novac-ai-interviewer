import unittest

from app.services.auth_service import hash_password, verify_password


class AuthServiceTests(unittest.TestCase):
    def test_password_hash_is_salted_and_verifiable(self):
        password = "correct horse battery staple"
        first_hash = hash_password(password)
        second_hash = hash_password(password)

        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(first_hash.startswith("pbkdf2_sha256$"))
        self.assertTrue(verify_password(password, first_hash))
        self.assertFalse(verify_password("wrong password", first_hash))


if __name__ == "__main__":
    unittest.main()
