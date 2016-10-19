import ctypes
import platform
import enum
from os.path import dirname, abspath, sep

os_name = platform.system()

libname = 'hamming.dll' if os_name == 'Windows' else 'libhamming.so'
this_dir = dirname(abspath(__file__))

libpath = sep.join((this_dir, 'bin', libname))

try:
    hamming_lib = ctypes.cdll.LoadLibrary(libpath)
except OSError as e:
    raise FileNotFoundError(
        'Shared library for hamming module not found. You need to compile '
        'the library before using this module. See documentation for '
        'details.') from e


class HammingError(enum.Enum):
    """
    Rappresenta lo stato di un messaggio decodificato.

        no_errors   Il messaggio non è stato alterato dal momento della
                    codifica.

        one_error   Un bit del messaggio è stato modificato dalla codifica
                    ed è stato corretto nella fase di decodifica.

        unreadable  Più di un bit è stato alterato. La decodifica non ha
                    avuto successo e il messaggio restituito non è corretto.
    """
    no_errors = 0
    one_error = 1
    unreadable = 2


def encode(to_encode: int) -> int:
    """
    Codifica 11 bit secondo Hamming 15-11 SECDED, restituendo quindi un
    messaggio codificato di 16 bit.

    :param to_encode: Il messaggio da codificare.
    :return: Il messaggio codificato.
    :raises ValueError: se il messaggio da codificare è più grande di 11 bit.
    """

    if to_encode.bit_length() > 11:
        raise ValueError('Trying to encode an int longer than 11 bits')

    to_encode = ctypes.c_uint16(to_encode)
    hamming_lib.hamming_encode(to_encode, ctypes.byref(to_encode))

    return to_encode.value


def decode(to_decode: int) -> (HammingError, int):
    """
    Decodifica 16 bit secondo Hamming 15-11 SECDED, restituendo un codice di
    errore di tipo HammingError e un messaggio decodificato di 11 bit.

    :param to_decode: Il messaggio da decodificare.
    :return: Il messaggio decodificato.
    :raises ValueError: se il messaggio da decodificare è più grande di 16 bit.
    """

    if to_decode.bit_length() > 16:
        raise ValueError('Trying to decode an int longer than 16 bits')

    to_decode = ctypes.c_uint16(to_decode)
    errcode = hamming_lib.hamming_decode(to_decode, ctypes.byref(to_decode))

    return HammingError(errcode), to_decode.value
