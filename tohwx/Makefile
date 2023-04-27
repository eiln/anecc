
TARGET = tohwx

CC = clang
CFLAGS = -Wall -O2
FRAMEWORKS = -framework CoreML -framework Foundation \
	-F /System/Library/PrivateFrameworks -framework ANECompiler -framework Espresso

all: ${TARGET}.o
	${CC} -o ${TARGET} $^ ${FRAMEWORKS}
format:
	clang-format -i *.m
install: all
	install ${TARGET} /usr/local/bin/
clean:
	rm -f *.o ${TARGET}
