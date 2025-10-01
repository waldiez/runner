# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Legacy bcrypt hash verifier for backward compatibility (verify-only)."""

import bcrypt


# pylint: disable=too-few-public-methods
class BcryptVerifier:
    """Bcrypt verifier for legacy hashes (verify only, never hash)."""

    @staticmethod
    def verify(plain: str, stored: str) -> bool:
        """Verify password against bcrypt hash.

        Parameters
        ----------
        plain : str
            The plain secret to verify.
        stored : str
            The stored hash.

        Returns
        -------
        bool
            True if verified, False if not.
        """
        if not stored.startswith(("$2a$", "$2b$", "$2y$")):
            return False
        try:
            # Explicitly truncate to 72 bytes for compatibility
            # ref (src):
            #  bcrypt originally suffered from a wraparound bug:
            #  http://www.openwall.com/lists/oss-security/2012/01/02/4
            # This bug was corrected in the OpenBSD source by truncating
            # inputs to 72 bytes on the updated prefix $2b$,
            # but leaving $2a$ unchanged for compatibility.
            # However, pyca/bcrypt 2.0.0 *did* correctly truncate inputs
            # on $2a$, so we do it here to preserve compatibility with 2.0.0
            # let password = &password[..password.len().min(72)];
            password_bytes = plain.encode("utf-8")[:72]
            return bcrypt.checkpw(password_bytes, stored.encode("utf-8"))
        except Exception:  # pylint: disable=broad-exception-caught
            return False


__all__ = ["BcryptVerifier"]
