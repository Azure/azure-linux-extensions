CC := gcc
SRCDIR := src
LIBDIR := lib
BINDIR := bin
INCDIR := include
BUILDDIR := build
TARGET := $(BINDIR)/safefreeze

SRCEXT := c
SOURCES := $(shell find $(SRCDIR) -type f -name *.$(SRCEXT))
OBJECTS := $(patsubst $(SRCDIR)/%,$(BUILDDIR)/%,$(SOURCES:.$(SRCEXT)=.o))
CFLAGS := -g

LDFLAGS := -static -static-libgcc
INC := -I $(INCDIR)
LIB := -L $(LIBDIR)

all : $(TARGET)

$(TARGET): $(OBJECTS)
	@echo "Linking..."
	@mkdir -p $(BINDIR)
	$(CC) $^ $(LDFLAGS) -o $(TARGET) $(LIB)

$(BUILDDIR)/%.o: $(SRCDIR)/%.$(SRCEXT)
	@mkdir -p $(BUILDDIR)
	@echo "Compiling..."
	$(CC) $(CFLAGS) $(INC) -c -o $@ $<

clean:
	@echo "Cleaning..."
	$(RM) -r $(BUILDDIR) $(BINDIR)

.PHONY: clean
