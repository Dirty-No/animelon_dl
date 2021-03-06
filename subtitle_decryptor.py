from Crypto.Cipher import AES
import base64
from Crypto.Protocol.KDF import PBKDF2

from Crypto import Random
from Crypto.Cipher import AES
import base64
from hashlib import md5
import sys

class SubtitleDecryptor:
    """    Python reimplementation of Animelon's unencryption of it's subtitle files.
              ASS.fromString = function(raw, type) {
                return void 0 === type && (type = misc_5.Format.ASS),
                "d(^-^" === raw.slice(-5) ? ASS.fromStream(new parser.StringStream(ASS.parseString(raw)), type) : ASS.fromStream(new parser.StringStream(raw), type)
            }
            ,
            ASS.parseString = function(s) {
                return CryptoJS.AES.decrypt(s.substring(8, s.length - 5), s.substring(0, 8).split("").reverse().join("")).toString(CryptoJS.enc.Utf8).replace(/undefined/g, "")
            }
    """
    def pad(self, data):
        '''
        Pads the data for AES encryption/decryption.
            Parameters:
                data (bytes): The data to pad.
            Returns:
                (bytes): The padded data.
        '''
        length = 16 - (len(data) % 16)
        return data + (chr(length)*length).encode()
    
    def unpad(self, data):
        '''
        Unpads the data for AES encryption/decryption.
            Parameters:
                data (bytes): The data to unpad.
            Returns:
                (bytes): The unpadded data.
        '''
        return data[:-(data[-1] if type(data[-1]) == int else ord(data[-1]))]
    
    def bytes_to_key(self, data, salt, output=48):
        '''
        Derive a key from a password using the PBKDF2 algorithm.
            Parameters:
                data (bytes): The password to derive the key from.
                salt (bytes): Salt for the password.
                output (int): The length of the key to return.
            Returns:
                (bytes): The derived key.
        '''
        # extended from https://gist.github.com/gsakkis/4546068
        assert len(salt) == 8, len(salt)
        data += salt
        key = md5(data).digest()
        final_key = key
        while len(final_key) < output:
            key = md5(key + data).digest()
            final_key += key
        return final_key[:output]
    
    def encrypt(self, message, passphrase):
        '''
        Encrypts the message using the passphrase.
            Parameters:
                message (bytes): The message to encrypt.
                passphrase (bytes): The passphrase to use for encryption.
            Returns:
                (bytes): The encrypted message.
        '''
        salt = Random.new().read(8)
        key_iv = self.bytes_to_key(passphrase, salt, 32+16)
        key = key_iv[:32]
        iv = key_iv[32:]
        aes = AES.new(key, AES.MODE_CBC, iv)
        return base64.b64encode(b"Salted__" + salt + aes.encrypt(self.pad(message)))
    
    def decrypt(self, encrypted:bytes, passphrase:bytes):
        '''
        Decrypts the message using the passphrase.
            Parameters:
                encrypted (bytes): The encrypted message.
                passphrase (bytes): The passphrase to use for decryption.
            Returns:
                (bytes): The decrypted message.
        '''
        encrypted = base64.b64decode(encrypted)
        encrypted = self.pad(encrypted)
        assert encrypted[0:8] == b"Salted__"
        salt = encrypted[8:16]
        key_iv = self.bytes_to_key(passphrase, salt, 32+16)
        key = key_iv[:32]
        iv = key_iv[32:]
        aes = AES.new(key, AES.MODE_CBC, iv)
        return self.unpad(aes.decrypt(encrypted[16:]))

    def decrypt_subtitle(self, encryptedSubtitle:str):
        '''
        Decrypts the encrypted subtitles
            Parameters:
                encryptedSubtitle (str): The encrypted subtitle in base64
            Returns:
                (bytes): The decrypted subtitle as a byte string
        '''
        encryptedSubtitle = bytes(encryptedSubtitle, 'utf-8')
        key = encryptedSubtitle[0:8][::-1]
        data = encryptedSubtitle[8:-5]
        encrypted = data
        decryptor = SubtitleDecryptor()
        uncrypted = decryptor.decrypt(encrypted, key)
        return uncrypted

if __name__ == "__main__":
    s = "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(^-^"
    uncrypted = SubtitleDecryptor().decrypt_subtitle(s)
    sys.stdout.buffer.write(uncrypted)
