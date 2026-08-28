import unittest

from werkzeug.security import generate_password_hash

from app import verify_password


class VerifyPasswordTests(unittest.TestCase):
    def test_accepts_plaintext_passwords_for_existing_users(self):
        self.assertTrue(verify_password("12345", "12345"))

    def test_accepts_hashed_passwords(self):
        hashed = generate_password_hash("secret123")
        self.assertTrue(verify_password(hashed, "secret123"))


if __name__ == "__main__":
    unittest.main()
