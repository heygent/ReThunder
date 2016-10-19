#ifndef HAMMING_H
#define HAMMING_H

#include <stdint.h>

#ifdef _WIN32
#define WINEXPORT __stdcall __declspec(dllexport)
#else
#define WINEXPORT
#endif

#ifdef __cplusplus
extern "C" {
#endif

enum hamming_error
{
  hamming_ok = 0, hamming_one_error, hamming_unreadable
};

typedef enum hamming_error hamming_error_t;

WINEXPORT
void            hamming_encode(uint16_t message, uint16_t *encoded_message);

WINEXPORT
hamming_error_t hamming_decode(uint16_t message, uint16_t *decoded_message);

#ifdef __cplusplus
}
#endif

#endif // HAMMING_H
