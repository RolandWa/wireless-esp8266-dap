# Host unit tests for the VTarget calibration logic (no ESP-IDF needed).
#
#   make -C tests/unit test        # build + run (gcc; on Windows run it in WSL)
#   make -C tests/unit clean
#
# See tests/README.md ("Unit tests").

CC      ?= gcc
CFLAGS  ?= -std=c99 -O1 -g -Wall -Wextra -Werror -pedantic
MAIN    := ../../main
SRCS    := test_vtarget_cal.c $(MAIN)/vtarget_cal.c $(MAIN)/vtarget_cal_boards.c
BIN     := test_vtarget_cal

$(BIN): $(SRCS) $(MAIN)/vtarget_cal.h
	$(CC) $(CFLAGS) -I$(MAIN) -o $@ $(SRCS) -lm

.PHONY: test clean
test: $(BIN)
	./$(BIN) ../test_results

clean:
	rm -f $(BIN)
