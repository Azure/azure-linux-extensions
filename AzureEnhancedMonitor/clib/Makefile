CC := gcc
SRCDIR := src
LIBDIR := lib
INCDIR := include
BUILDDIR := build
TARGET := $(LIBDIR)/libazureperf.so

SRCEXT := c
SOURCES := $(shell find $(SRCDIR) -type f -name *.$(SRCEXT))
OBJECTS := $(patsubst $(SRCDIR)/%,$(BUILDDIR)/%,$(SOURCES:.$(SRCEXT)=.o))
CFLAGS := -g -fPIC
LDFLAGS := -shared
INC := -I $(INCDIR)
LIB := -L $(LIBDIR)

all : $(TARGET)

$(TARGET): $(OBJECTS)
	@echo "Linking..."
	$(CC) $^ $(LDFLAGS) -o $(TARGET) $(LIB)

$(BUILDDIR)/%.o: $(SRCDIR)/%.$(SRCEXT)
	@mkdir -p $(BUILDDIR)
	@echo "Compiling..."
	$(CC) $(CFLAGS) $(INC) -c -o $@ $<

clean:
	@echo "Cleaning..."
	$(RM) -r $(BUILDDIR) $(TARGET)

test: $(OBJECTS)
	@echo "Run test"
	$(CC) test/runtest.c $^ $(INC) -L $(LIBDIR) -lazureperf -o bin/runtest
	bin/runtest

install:
	cp $(TARGET) /usr/lib
	cp $(INCDIR)/azureperf.h /usr/include

.PHONY: clean test
