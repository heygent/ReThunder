#include <stdbool.h>
#include <hamming.h>

#ifndef __GNUC__
#  define __attribute__(x)
#endif

__attribute__((const, hot))
static bool bit_parity_is_odd(uint16_t data)
{
  // http://stackoverflow.com/a/21618038

  data ^= data >> 8;
  data ^= data >> 4;
  data ^= data >> 2;
  data ^= data >> 1;
  return data & 1;
}

static const uint16_t data_bits_masks[] =
{
  0x00FE, // 0000 0000 1111 1110
  0x0E00, // 0000 1110 0000 0000
  0x2000  // 0010 0000 0000 0000
};

static const int data_bits_masks_length = 3;

static const uint16_t parity_check_masks[] =
{
  0xAAAA, // 1010 1010 1010 1010
  0x6666, // 0110 0110 0110 0110
  0x1E1E, // 0001 1110 0001 1110
  0x01FE, // 0000 0001 1111 1110
};

static const int parity_check_masks_length = 4;

WINEXPORT
__attribute__((hot))
void hamming_encode(uint16_t message, uint16_t *encoded_message)
{
  *encoded_message = 0;

  // Inserisce i bit dei dati.
  // I bit dei dati sono i bit i cui indici NON sono potenze di due a partire
  // da sinistra.
  //
  //  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0
  //  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16
  //        D     D  D  D     D  D  D  D  D  D  D
  //
  // I bit dei dati sono gli stessi del messaggio originale, ordinati nello
  // stesso modo.

  for(int i = 0; i < data_bits_masks_length; i++)
  {
    message <<= 1;
    *encoded_message |= (message & data_bits_masks[i]);
  }

  // Calcola le parità.
  // I bit di parità sono i bit i cui indici sono potenze di due a partire
  // da sinistra.
  //
  //  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0
  //  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16
  //  P  P     P           P                       P
  //
  // Le maschere dei bit di parità sono in ordine rispetto alle parità da
  // controllare (parity_check_masks[0] controlla il bit 1,
  // parity_check_masks[1] il bit 2, parity_check_masks[2] il bit 4
  // eccetera).

  for(int i = 0; i < parity_check_masks_length; i++)
  {
    const uint16_t parity_to_check = parity_check_masks[i] & *encoded_message;

    if(bit_parity_is_odd(parity_to_check))
    {
      *encoded_message |= 1 << (16 - (1 << i));
    }
  }

  // L'ultimo bit è la parità totale

  if(bit_parity_is_odd(*encoded_message))
  {
    *encoded_message |= 1;
  }
}

WINEXPORT
__attribute__((hot))
hamming_error_t hamming_decode(uint16_t encoded_message, uint16_t *message)
{
  int error_position = 0;

  for(int i = 0; i < parity_check_masks_length; i++)
  {
    const uint16_t parity_to_check = parity_check_masks[i] & encoded_message;

    // Le posizioni dei bit di parità errati indicano dove si trova l'errore.
    // Esempio: se i bit di parità 1 e 4 da sinistra sono errati, l'errore è
    // nella posizione 5 da sinistra.

    if(bit_parity_is_odd(parity_to_check))
    {
      error_position |= (1 << i);
    }
  }

  // Se ci sono bit sbagliati, e la parità totale è pari, il messaggio è
  // illeggibile.
  // Se la parità totale è dispari ma non ci sono altre parità sbagliate,
  // è il bit di parità totale ad essere sbagliato.

  const bool total_parity_is_even = !bit_parity_is_odd(encoded_message);

  if(error_position != 0 && total_parity_is_even)
  {
    return hamming_unreadable;
  }
  else if(error_position == 0 && !total_parity_is_even)
  {
    error_position = 16;
  }

  encoded_message ^= (1 << (16 - error_position));
  *message = 0;

  for(int i = data_bits_masks_length - 1; i >= 0; i--)
  {
    *message |= (encoded_message & data_bits_masks[i]);
    *message >>= 1;
  }

  return error_position == 0 ? hamming_ok : hamming_one_error;
}
