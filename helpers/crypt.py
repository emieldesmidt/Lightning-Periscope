import secrets
import hashlib
import time


class Crypt:

    def __init__(self):
        # Create a 32 bit preimage, and the accompanying hash for invoiceless transaction
        self.preimage = secrets.token_bytes(32)
        self.phash = hashlib.sha256(self.preimage).digest()


    def crypt_pair_generator(self):
        while True:
            preimage = secrets.token_bytes(32)
            phash = hashlib.sha256(preimage).digest()
            yield preimage, phash


