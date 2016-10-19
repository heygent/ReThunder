"""
Questo package contiene le funzioni per codificare e decodificare messaggi
in Hamming 15-11 SECDED.

Un messaggio codificato in Hamming può decodificato anche se ha un bit
alterato. La codifica 15-11 usa 15 bit per codificare 11 bit di informazioni.
Le codifiche SECDED, usando un bit in più, permettono oltre alla correzione
di un errore la rilevazione di due errori (senza correzione).

Le funzioni sono scritte in C, è necessario quindi che prima dell'uso queste
siano compilate e linkate in una libreria condivisa.
Per compilare i file necessari si può utilizzare il makefile allegato, con i
seguenti comandi:

    ```make bin/libhamming.so``` su Linux e su Mac (non testato)

    ```make bin/hamming.dll`` su Windows con toolchain MinGW

"""

from hamming.wrappers import encode, decode, HammingError

no_errors = HammingError.no_errors
one_error = HammingError.one_error
unreadable = HammingError.unreadable
