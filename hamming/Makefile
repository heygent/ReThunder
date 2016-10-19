# Con compilatore MS: cl /LD $(SRC)/hamming.c

SRC=src
BIN=bin
OBJ=obj

ifeq ($(shell uname -o),Cygwin)
	CC=x86_64-w64-mingw32-gcc
	DEFAULT=$(BIN)/hamming.dll
else
	CC=gcc
	DEFAULT=$(BIN)/libhamming.so
endif

CFLAGS=-Wall -Wextra -Wpedantic -std=c99 -O3

COMPILE=$(CC) $(CFLAGS) -c
LINK=$(CC)


CFLAGS+=-I$(SRC)

all: $(DEFAULT)

$(BIN)/libhamming.so $(BIN)/hamming.dll: $(OBJ)/hamming.o | $(BIN)
	$(LINK) -shared -o $@ $^

$(OBJ)/%.o: | $(OBJ)
	$(COMPILE) $(SRC)/$*.c -o $@

$(BIN) $(OBJ):
	mkdir -p $@

clean:
	rm -rf $(BIN) $(OBJ)
